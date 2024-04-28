from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from bunker import schemas
from bunker.db import models
from bunker.exceptions import NotFoundError

async def create_integration_config(
        db: AsyncSession,
        params: schemas.IntegrationConfigParams,
):
    db_integration = models.Integration(
        **params.model_dump(),
        integration_type=params.integration_type # may be ClassVar
    )
    db.add(db_integration)

    # Get integration ID
    await db.flush()
    await db.refresh(db_integration)

    return db_integration


async def update_integration_config(
        db: AsyncSession,
        config: schemas.IntegrationConfig,
):
    stmt = update(models.Integration).values(
        **config.model_dump(),
        integration_type=config.integration_type # may be ClassVar
    ).where(
        models.Integration.id == config.id
    ).returning(models.Integration)
    db_integration = await db.scalar(stmt)

    if not db_integration:
        raise NotFoundError("Integration does not exist")

    return db_integration
