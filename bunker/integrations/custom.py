from typing import Sequence
import aiohttp
from cachetools import TTLCache
import discord

from bunker import schemas
from bunker.crud.communities import get_community_by_id
from bunker.crud.reports import is_player_reported
from bunker.crud.responses import get_pending_responses, get_reports_for_player_with_no_community_response
from bunker.db import session_factory
from bunker.discord.communities import get_forward_channel
from bunker.discord.reports import get_alert_embed
from bunker.enums import IntegrationType
from bunker.exceptions import (
    IntegrationBanError, IntegrationCommandError, NotFoundError,
    AlreadyBannedError, IntegrationValidationError
)
from bunker.forwarding import send_or_edit_report_management_message, send_or_edit_report_review_message
from bunker.integrations.integration import Integration, IntegrationMetaData
from bunker.integrations.websocket import (
    BanPlayersRequestConfigPayload, BanPlayersRequestPayload, ClientRequestType,
    UnbanPlayersRequestPayload, Websocket, WebsocketRequestHandler
)

class IntegrationRequestHandler(WebsocketRequestHandler):
    __is_player_reported = TTLCache[str, bool](maxsize=9999, ttl=60*10)

    def __init__(self, ws: Websocket, integration: 'Integration'):
        super().__init__(ws)
        self.integration = integration
    
    async def scan_players(self, payload: dict | None) -> dict | None:
        reported_player_ids: list[str] = []

        # Go over all players to check whether they have been reported
        player_ids: list[str] = payload["player_ids"]
        async with session_factory() as db:
            for player_id in player_ids:
                # First look for a cached response, otherwise fetch from DB
                cache_hit = self.__is_player_reported.get(player_id)
                if cache_hit is not None:
                    if cache_hit:
                        reported_player_ids.append(player_id)
                else:
                    is_reported = await is_player_reported(db, player_id)
                    self.__is_player_reported[player_id] = is_reported
                    if is_reported:
                        reported_player_ids.append(player_id)
        
            if reported_player_ids:
                # There are one or more players that have reports
                community_id = self.integration.config.community_id
                
                db_community = await get_community_by_id(db, community_id)
                community = schemas.CommunityRef.model_validate(db_community)

                channel = get_forward_channel(community)
                if not channel:
                    # We have nowhere to send the alert, so we just ignore
                    return

                for player_id in reported_player_ids:
                    # For each player, get all reports that this community has not yet responded to
                    db_reports = await get_reports_for_player_with_no_community_response(
                        db, player_id, community_id
                    )

                    messages: list[discord.Message] = []
                    sorted_reports = sorted(
                        (schemas.ReportWithToken.model_validate(db_report) for db_report in db_reports),
                        key=lambda x: x.created_at
                    )

                    # Locate all the messages, resending as necessary, and updating them with the most
                    # up-to-date details.
                    for report in sorted_reports:
                        if report.token.community_id == community_id:
                            message = await send_or_edit_report_management_message(report)
                        else:
                            community = await get_community_by_id(db, community.id)
                            responses = await get_pending_responses(db, community, report.players)
                            message = await send_or_edit_report_review_message(report, responses, community)
                        
                        if message:
                            # Remember the message
                            messages.append(message)

                    if not messages:
                        # No messages were located, so we don't have any reports to point the user at.
                        continue

                    # Get the most recent PlayerReport for the most up-to-date name
                    player = next(
                        pr for pr in sorted_reports[-1].players
                        if pr.player_id == player_id
                    )

                    # TODO: Use admin role
                    content = f"<@&123> a potentially dangerous player has joined your server!"
                    embed = get_alert_embed(
                        report_urls=list(reversed(zip(sorted_reports, (message.jump_url for message in messages)))),
                        player=player
                    )

                    await channel.send(content=content, embed=embed)

class CustomIntegration(Integration):
    meta = IntegrationMetaData(
        name="Custom",
        config_cls=schemas.CustomIntegrationConfig,
        type=IntegrationType.CUSTOM,
        emoji="💭",
    )

    def __init__(self, config: schemas.CustomIntegrationConfigParams) -> None:
        super().__init__(config)
        self.config: schemas.CustomIntegrationConfigParams
        self.ws = Websocket(
            address=self.get_ws_url(),
            token=config.api_key,
            request_handler_factory=lambda ws: IntegrationRequestHandler(ws, self)
        )

    def get_ws_url(self):
        return self.config.api_url

    # --- Extended parent methods

    def start_connection(self):
        self.ws.start()
    
    def stop_connection(self):
        self.ws.stop()
    
    def update_connection(self):
        self.ws.address = self.config.api_url
        self.ws.token = self.config.api_key
        self.ws.update_connection()

    # --- Abstract method implementations

    async def get_instance_name(self) -> str:
        return "Custom"
    
    def get_instance_url(self) -> str:
        return self.config.api_url

    async def validate(self, community: schemas.Community):
        if community.id != self.config.community_id:
            raise IntegrationValidationError("Communities do not match")

    async def ban_player(self, response: schemas.Response):
        async with session_factory.begin() as db:
            player_id = response.player_report.player_id
            db_ban = await self.get_ban(db, player_id)
            if db_ban is not None:
                raise AlreadyBannedError(player_id, "Player is already banned")

            try:
                await self.add_ban(
                    player_id=player_id,
                    reason=self.get_ban_reason(response.community)
                )
            except Exception as e:
                raise IntegrationBanError(player_id, "Failed to ban player") from e

            await self.set_ban_id(db, player_id, player_id)

    async def unban_player(self, response: schemas.Response):
        async with session_factory.begin() as db:
            player_id = response.player_report.player_id
            db_ban = await self.get_ban(db, player_id)
            if db_ban is None:
                raise NotFoundError("Ban does not exist")

            await db.delete(db_ban)
            await db.flush()

            try:
                await self.remove_ban(db_ban.remote_id)
            except Exception as e:
                raise IntegrationBanError(player_id, "Failed to unban player") from e
    
    async def bulk_ban_players(self, responses: Sequence[schemas.Response]):
        ban_ids: list[tuple[str, str]] = []
        try:
            async for ban in self.add_multiple_bans(
                player_ids={
                    response.player_report.player_id: self.get_ban_reason(response.community)
                    for response in responses
                }
            ):
                ban_ids.append(ban)

        finally:
            if ban_ids:
                async with session_factory.begin() as db:
                    await self.set_multiple_ban_ids(db, ban_ids)

    async def bulk_unban_players(self, responses: Sequence[schemas.Response]):
        async with session_factory() as db:
            player_ids: dict[str, str] = {}
            for response in responses:
                player_id = response.player_report.player_id
                ban = await self.get_ban(db, player_id)
                player_ids[ban.remote_id] = player_id

        successful_player_ids: list[str] = []
        try:
            async for ban_id in self.remove_multiple_bans(ban_ids=player_ids.keys()):
                successful_player_ids.append(player_ids[ban_id])
        finally:
            if successful_player_ids:
                async with session_factory.begin() as db:
                    await self.discard_multiple_ban_ids(db, successful_player_ids)

    async def synchronize(self):
        pass

    # --- Websocket API wrappers

    async def _make_request(self, method: str, endpoint: str, data: dict = None) -> dict:
        """Make an API request.

        Parameters
        ----------
        method : str
            One of GET, POST, PATCH, DELETE
        endpoint : str
            The resource to query, gets prepended with the API root URL.
            For example, `/login` queries `http://<api>:<port>/api/login`.
        data : dict, optional
            Additional data to include in the request, by default None

        Returns
        -------
        dict
            The response from the server

        Raises
        ------
        Exception
            Doom and gloom
        """
        url = self.config.api_url + endpoint
        headers = {"Authorization": f"Bearer {self.config.api_key}"}
        async with aiohttp.ClientSession(headers=headers) as session:
            if method in {"POST", "PATCH"}:
                kwargs = {"json": data}
            else:
                kwargs = {"params": data}

            async with session.request(method=method, url=url, **kwargs) as r:
                r.raise_for_status()
                content_type = r.headers.get('content-type', '')

                if 'json' in content_type:
                    response = await r.json()
                elif "text/html" in content_type:
                    response = (await r.content.read()).decode()
                else:
                    raise Exception(f"Unsupported content type: {content_type}")

        return response

    async def add_multiple_bans(self, player_ids: dict[str, str | None], *, partial_retry: bool = True):
        try:
            response = await self.ws.execute(ClientRequestType.BAN_PLAYERS, BanPlayersRequestPayload(
                player_ids=player_ids,
                config=BanPlayersRequestConfigPayload(
                    banlist_id=self.config.banlist_id,
                    reason="Banned via shared HLL Bunker report.",
                )
            ))
        except IntegrationCommandError as e:
            if e.response.get("error") != "Could not ban all players":
                raise

            successful_ids = e.response["player_ids"]
            for player_id, ban_id in successful_ids.items():
                yield (player_id, ban_id)
            
            if not partial_retry:
                raise

            # Retry for failed player IDs
            missing_player_ids = {k: v for k, v in player_ids.items() if k not in successful_ids}
            async for (player_id, ban_id) in self.add_multiple_bans(missing_player_ids, partial_retry=False):
                yield player_id, ban_id
        else:
            for player_id, ban_id in response["player_ids"]:
                yield player_id, ban_id

    async def remove_multiple_bans(self, ban_ids: Sequence[str], *, partial_retry: bool = True):
        try:
            response = await self.ws.execute(ClientRequestType.UNBAN_PLAYERS, UnbanPlayersRequestPayload(
                ban_ids=ban_ids,
                config=BanPlayersRequestConfigPayload(
                    banlist_id=self.config.banlist_id,
                )
            ))
        except IntegrationCommandError as e:
            if e.response.get("error") != "Could not unban all players":
                raise

            successful_ids = e.response["ban_ids"]
            for ban_id in successful_ids:
                yield ban_id
            
            if not partial_retry:
                raise

            # Retry for failed ban IDs
            missing_ban_ids = list(set(ban_ids) - set(successful_ids))
            async for ban_id in self.remove_multiple_bans(missing_ban_ids, partial_retry=False):
                yield ban_id
        else:
            for ban_id in response["ban_ids"]:
                yield ban_id

    async def add_ban(self, player_id: str, reason: str | None = None):
        return await anext(self.add_multiple_bans({player_id: reason}))

    async def remove_ban(self, ban_id: str):
        return await anext(self.remove_multiple_bans([ban_id]))