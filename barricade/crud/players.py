import logging

from sqlalchemy import and_, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from barricade import schemas
from barricade.db import models
from barricade.enums import Game
from barricade.exceptions import NotFoundError
from barricade.utils import game_switch, is_steam_id


async def get_player(db: AsyncSession, player_id: int):
    """Look up a player.

    Parameters
    ----------
    db : AsyncSession
        An asynchronous database session
    player_id : int
        The ID of the player

    Returns
    -------
    Player | None
        The player model, or None if it does not exist
    """
    return await db.get(models.Player, player_id)


async def get_player_by_game_id(db: AsyncSession, player_game_id: str, game: Game):
    """Look up a player by their game ID.

    Parameters
    ----------
    db : AsyncSession
        An asynchronous database session
    player_game_id : str
        The game ID of the player
    game : Game
        The game for which to look up the player

    Returns
    -------
    Player | None
        The player model, or None if it does not exist
    """
    stmt = game_switch(
        game,
        select(models.Player).where(
            models.Player.steam_id == player_game_id
            if is_steam_id(player_game_id)
            else models.Player.xplay_id == player_game_id
        ),
        select(models.Player).where(models.Player.hllv_eos_id == player_game_id),
    )

    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def get_player_by_any_game_id(db: AsyncSession, player_game_id: str):
    """Look up a player by their game ID, without the game being known.

    Parameters
    ----------
    db : AsyncSession
        An asynchronous database session
    player_game_id : str
        A game ID of the player

    Returns
    -------
    Player | None
        The player model, or None if it does not exist
    """
    stmt = select(models.Player).where(
        or_(
            (
                models.Player.steam_id == player_game_id
                if is_steam_id(player_game_id)
                else models.Player.xplay_id == player_game_id
            ),
            models.Player.hllv_eos_id == player_game_id,
        )
    )

    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def get_player_by_game_ids(db: AsyncSession, player: schemas.PlayerCreateParams):
    conds = []
    if player.steam_id or player.xplay_id:
        conds.append(
            and_(
                models.Player.steam_id == player.steam_id,
                models.Player.xplay_id == player.xplay_id,
            )
        )
    if player.hllv_eos_id:
        conds.append(models.Player.hllv_eos_id == player.hllv_eos_id)

    if not conds:
        return []

    stmt = select(models.Player).where(or_(*conds)).limit(len(conds))
    result = await db.execute(stmt)
    return result.scalars().all()


async def create_player(db: AsyncSession, player: schemas.PlayerCreateParams):
    db_player = models.Player(**player.model_dump())
    db.add(db_player)
    await db.flush()
    return db_player


async def merge_players(
    db: AsyncSession, player_a: models.Player, player_b: models.Player
):
    """Merge player b into player a.

    Parameters
    ----------
    db : AsyncSession
        An asynchronous database session
    player_a : models.Player
        The first player to merge
    player_b : models.Player
        The second player to merge

    Returns
    -------
    models.Player
        The merged player model

    Raises
    ------
    ValueError
        If the players have conflicting game IDs
    """
    if (
        (
            player_a.steam_id
            and player_b.steam_id
            and player_a.steam_id != player_b.steam_id
        )
        or (
            player_a.xplay_id
            and player_b.xplay_id
            and player_a.xplay_id != player_b.xplay_id
        )
        or (
            player_a.hllv_eos_id
            and player_b.hllv_eos_id
            and player_a.hllv_eos_id != player_b.hllv_eos_id
        )
    ):
        raise ValueError("Cannot merge players with conflicting game IDs")

    # Merge attributes, preferring non-null values from player_a
    for field in schemas.PlayerCreateParams.model_fields:
        value_a = getattr(player_a, field)
        value_b = getattr(player_b, field)
        if not value_a and value_b:
            setattr(player_a, field, value_b)

    # Reassign all PlayerReport entries from player_b to player_a
    stmt = (
        update(models.PlayerReport)
        .values(player_id=player_a.id)
        .where(models.PlayerReport.player_id == player_b.id)
    )
    await db.execute(stmt)

    # Reassign all PlayerBan entries from player_b to player_a
    stmt = (
        update(models.PlayerBan)
        .values(player_id=player_a.id)
        .where(models.PlayerBan.player_id == player_b.id)
    )
    await db.execute(stmt)

    # Reassign all PlayerWatchlist entries from player_b to player_a
    stmt = (
        update(models.PlayerWatchlist)
        .values(player_id=player_a.id)
        .where(models.PlayerWatchlist.player_id == player_b.id)
    )
    await db.execute(stmt)

    # Delete the second player
    await db.delete(player_b)
    await db.flush()

    return player_a


async def _edit_player(
    db: AsyncSession, db_player: models.Player, player: schemas.PlayerCreateParams
) -> bool:
    dirty = False

    # Iterate over all fields and update if changed.
    for field_name in schemas.PlayerCreateParams.model_fields:
        new_value = getattr(player, field_name)
        old_value = getattr(db_player, field_name)
        if new_value and new_value != old_value:
            if old_value:
                logging.warning(
                    "Overwriting %s for player %s. Old: %r - New: %r",
                    field_name,
                    db_player.id,
                    old_value,
                    new_value,
                )
            setattr(db_player, field_name, new_value)
            dirty = True

    # Only flush if there were changes to avoid unnecessary database writes.
    if dirty:
        await db.flush()

    return dirty


async def edit_player(db: AsyncSession, player: schemas.PlayerEditParams):
    """Edit a player.

    Parameters
    ----------
    db : AsyncSession
        An asynchronous database session
    player : schemas.PlayerEditParams
        The player to update

    Returns
    -------
    models.Player
        The updated player model
    """
    db_player = await get_player(db, player.id)
    if not db_player:
        raise NotFoundError(f"Player with ID {player.id} does not exist")

    await _edit_player(db, db_player, player)

    return db_player


async def get_or_upsert_player(db: AsyncSession, player: schemas.PlayerCreateParams):
    """Look up a player, inserting if it does not exist, and updating all relevant fields.

    Parameters
    ----------
    db : AsyncSession
        An asynchronous database session
    player : schemas.PlayerCreateParams
        Payload

    Returns
    -------
    tuple[Player, bool]
        The player model and a boolean indicating whether it was created or not
    """
    db_players = await get_player_by_game_ids(db, player)

    if not db_players:
        return (await create_player(db, player), True)

    if len(db_players) == 1:
        db_player = db_players[0]

    if len(db_players) == 2:
        db_player = await merge_players(db, db_players[0], db_players[1])

    else:
        raise RuntimeError("Unexpected number of players returned")

    await _edit_player(db, db_player, player)

    return db_player, True
