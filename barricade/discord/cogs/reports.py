from typing import TYPE_CHECKING

import discord
from discord import Interaction, app_commands
from discord.ext import commands

from barricade import schemas
from barricade.crud.communities import get_admin_by_id, get_community_by_guild_id
from barricade.crud.players import get_player_by_any_game_id
from barricade.crud.reports import get_reports_for_player
from barricade.db import session_factory
from barricade.discord.communities import (
    assert_has_any_admin_role,
)
from barricade.discord.utils import CustomException
from barricade.discord.views.report_paginator import PaginatedReportsView

if TYPE_CHECKING:
    from barricade.discord.bot import Bot


class ReportsCog(commands.Cog):
    def __init__(self, bot: "Bot"):
        self.bot = bot

    @app_commands.command(
        name="reports", description="See all Barricade reports made against a player"
    )
    @app_commands.rename(player_game_id="player_id")
    async def get_reports(self, interaction: Interaction, player_game_id: str):
        async with session_factory() as db:
            access_denied_exc = CustomException(
                "Access denied!",
                "Only admins of verified servers can use this command.",
            )

            db_admin = await get_admin_by_id(db, discord_id=interaction.user.id)
            if db_admin and db_admin.community:
                db_community = db_admin.community
                if not db_community:
                    raise access_denied_exc
                community = schemas.CommunityRef.model_validate(db_community)

            else:
                db_community = await get_community_by_guild_id(
                    db,
                    guild_id=interaction.guild_id,  # type: ignore
                )
                if not db_community:
                    raise access_denied_exc

                community = schemas.CommunityRef.model_validate(db_community)
                assert_has_any_admin_role(interaction.user, community)

            error_embed = discord.Embed(color=discord.Color.dark_theme()).set_author(
                name="There are no reports made against this player!"
            )

            # Find
            db_player = await get_player_by_any_game_id(db, player_game_id)
            if not db_player:
                await interaction.response.send_message(
                    embed=error_embed,
                    ephemeral=True,
                )
                return

            db_reports = await get_reports_for_player(
                db, player_id=db_player.id, load_token=True
            )
            if not db_reports:
                await interaction.response.send_message(
                    embed=error_embed,
                    ephemeral=True,
                )
                return

            reports = [
                schemas.ReportWithToken.model_validate(db_report)
                for db_report in db_reports
            ]

            view = PaginatedReportsView(community, reports)
            await view.send(interaction)


async def setup(bot: "Bot"):
    await bot.add_cog(ReportsCog(bot))
