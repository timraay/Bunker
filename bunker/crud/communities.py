from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy.exc import IntegrityError

from bunker import schemas
from bunker.constants import MAX_ADMIN_LIMIT
from bunker.db import models
from bunker.discord import bot
from bunker.exceptions import (
    AdminNotAssociatedError, AlreadyExistsError, AdminOwnsCommunityError,
    TooManyAdminsError, NotFoundError
)

async def get_admin_by_id(db: AsyncSession, discord_id: int, load_relations: bool = False):
    """Look up an admin by their discord ID.

    Parameters
    ----------
    db : AsyncSession
        An asynchronous database session
    discord_id : int
        The discord ID of the admin
    load_relations : bool, optional
        Whether to also load relational properties, by default False

    Returns
    -------
    Admin | None
        The admin model, or None if it does not exist
    """
    if load_relations:
        options = (selectinload("*"),)
    else:
        options = (selectinload(models.Admin.community), selectinload(models.Admin.owned_community))

    return await db.get(models.Admin, discord_id, options=options)

async def get_community_by_id(db: AsyncSession, community_id: int, load_relations: bool = False):
    """Look up a community by its ID.

    Parameters
    ----------
    db : AsyncSession
        An asynchronous database session
    community_id : int
        The ID of the community
    load_relations : bool, optional
        Whether to also load relational properties, by default False

    Returns
    -------
    Community | None
        The community model, or None if it does not exist
    """
    if load_relations:
        options = (selectinload("*"),)
    else:
        options = (selectinload(models.Community.admins), selectinload(models.Community.owner), selectinload(models.Community.integrations))

    return await db.get(models.Community, community_id, options=options)
    
async def create_new_community(
        db: AsyncSession,
        community: schemas.CommunityCreateParams
):
    """Create a new community.

    Parameters
    ----------
    db : AsyncSession
        An asyncronous database session
    community : schemas.CommunityCreate
        Payload

    Returns
    -------
    Community
        The community model

    Raises
    ------
    AlreadyExistsError
        The owner already belongs to a community
    """
    # Look if the owner exists already
    db_owner = await get_admin_by_id(db, community.owner_id)
    if not db_owner:
        # If no record exists, create new Admin record
        # Add the community_id later once the Community is created
        owner = schemas.AdminCreateParams(
            discord_id=community.owner_id,
            community_id=None,
            name=community.owner_name,
        )
        db_owner = await create_new_admin(db, owner)
    elif db_owner.community_id:
        # Owner is already part of a community
        raise AlreadyExistsError
    elif db_owner.name != community.owner_name:
        # Update saved name of owner
        db_owner.name = community.owner_name
    
    # Create the Community
    db_community = models.Community(**community.model_dump(exclude={"owner_name"}))
    db.add(db_community)
    # Flush and refresh to fetch the community's ID
    await db.flush()
    await db.refresh(db_community)

    # Update the owner's community
    db_owner.community_id = db_community.id
    await db.commit()
    await db.refresh(db_community)
    
    return db_community

async def create_new_admin(db: AsyncSession, admin: schemas.AdminCreateParams):
    """Create a new admin.

    Parameters
    ----------
    db : AsyncSession
        An asynchronous database session
    admin : schemas.AdminCreate
        Payload

    Returns
    -------
    Admin
        The admin model

    Raises
    ------
    AlreadyExistsError
        This admin already exists
    TooManyAdminsError
        The community is not allowed any more admins
    NotFoundError
        No community with the given ID exists
    """
    if await get_admin_by_id(db, admin.discord_id):
        raise AlreadyExistsError
    
    if admin.community_id:
        db_community = await get_community_by_id(db, admin.community_id)
        if not db_community:
            raise NotFoundError("Community does not exist")
        elif len(db_community.admins) >= MAX_ADMIN_LIMIT:
            raise TooManyAdminsError

    db_admin = models.Admin(**admin.model_dump())
    db.add(db_admin)
    await db.commit()
    await db.refresh(db_admin)
    return db_admin

async def admin_leave_community(db: AsyncSession, admin: models.Admin):
    """Remove an admin from a community.

    Parameters
    ----------
    db : AsyncSession
        An asynchronous database session
    admin : models.Admin
        The admin to remove

    Returns
    -------
    Admin
        The admin

    Raises
    ------
    AdminOwnsCommunityError
        The admin is a community owner
    """
    if admin.community_id is None:
        return admin
    
    owned_community = await admin.awaitable_attrs.owned_community
    if owned_community:
        raise AdminOwnsCommunityError(admin)

    admin.community_id = None
    await db.commit()
    await db.refresh(admin)

    await bot.revoke_admin_roles(admin.discord_id)

    return admin

async def admin_join_community(db: AsyncSession, admin: models.Admin, community: models.Community):
    """Add an admin to a community.

    Parameters
    ----------
    db : AsyncSession
        An asynchronous database session
    admin : models.Admin
        The admin to add
    community_id : int
        The community to add the admin to

    Returns
    -------
    Admin
        The admin

    Raises
    ------
    AlreadyExistsError
        The admin is already part of a community
    TooManyAdminsError
        The community is not allowed any more admins
    NotFoundError
        No community exists for the given ID
    """
    if admin.community_id:
        if admin.community_id == community.id:
            return admin
        else:
            raise AlreadyExistsError(admin)
        
    if len(await community.awaitable_attrs.admins) >= MAX_ADMIN_LIMIT:
        raise TooManyAdminsError
        
    admin.community_id = community.id
    try:
        await db.commit()
    except IntegrityError:
        raise NotFoundError(admin)
    await db.refresh(admin)

    await bot.grant_admin_role(admin.discord_id)

    return admin

async def transfer_ownership(db: AsyncSession, community: models.Community, admin: models.Admin):
    """Transfer ownership of a community.

    Parameters
    ----------
    db : AsyncSession
        An asynchronous database session
    community : models.Community
        The community
    admin : models.Admin
        The admin to transfer ownership to

    Returns
    -------
    bool
        Whether something was changed

    Raises
    ------
    AdminNotAssociatedError
        The admin does not belong to the community
    """
    if community.owner_id == admin.discord_id:
        return False
    
    if admin.community_id != community.id:
        raise AdminNotAssociatedError(admin, community)
    
    old_owner_id = community.owner_id
    community.owner_id = admin.discord_id
    await db.commit()
    await db.refresh(community)

    await bot.grant_admin_role(old_owner_id)
    await bot.grant_owner_role(community.owner_id)

    return True


async def create_integration_config(
        db: AsyncSession,
        params: schemas._IntegrationConfigBase,
):
    db_integration = models.Integration(
        **params.model_dump(),
        integration_type=params.integration_type # may be ClassVar
    )
    db.add(db_integration)
    await db.commit()
    # await db.refresh(db_integration)
    return db_integration

async def update_integration_config(
        db: AsyncSession,
        config: schemas.BasicIntegrationConfig,
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
    
    await db.commit()    
    return db_integration