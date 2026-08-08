from barricade import schemas
from barricade.enums import Emojis, IntegrationType
from barricade.integrations.custom import CustomIntegration, is_websocket_enabled
from barricade.integrations.integration import IntegrationMetaData, is_enabled
from barricade.utils import async_ttl_cache


class BifrostIntegration(
    CustomIntegration,
):
    meta = IntegrationMetaData(
        name="Bifrost",
        config_cls=schemas.BifrostIntegrationConfig,
        type=IntegrationType.BIFROST,
        emoji=Emojis.BIFROST,
    )

    def __init__(self, config: schemas.BifrostIntegrationConfigParams) -> None:
        super().__init__(config)
        self.config: schemas.BifrostIntegrationConfigParams  # type: ignore

    def get_api_url(self):
        return self.config.api_url + "/api"

    def get_ws_url(self):
        return self.config.api_url + "/ws/barricade"

    # --- Abstract method implementations

    @async_ttl_cache(size=9999, seconds=60 * 10)
    async def get_instance_name(self) -> str:
        # TODO: Get Bifrost instance name
        return "Bifrost"

    def get_instance_url(self) -> str | None:
        return "https://dashboard.bifrostgaming.com/"

    # async def validate(self, community: schemas.Community) -> set[str]:
    #     await super().validate(community)
    #     return set()

    @is_enabled
    @is_websocket_enabled
    async def synchronize(self):
        pass

    # --- Bifrost API wrappers
