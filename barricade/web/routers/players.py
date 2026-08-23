from typing import Annotated

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Security, status

from barricade import schemas
from barricade.crud import players
from barricade.db import DatabaseDep, models
from barricade.web import schemas as web_schemas
from barricade.web.paginator import PaginatedResponse, PaginatorDep
from barricade.web.scopes import Scopes
from barricade.web.security import get_active_token

router = APIRouter(prefix="", tags=["Players"])


def get_player_dependency(load_token: bool):
    async def inner(db: DatabaseDep, player_id: int):
        result = await players.get_player(db, player_id, load_relations=load_token)
        if result is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Player not found"
            )
        return result

    return inner


PlayerDep = Annotated[models.Player, Depends(get_player_dependency(False))]
PlayerWithRelationsDep = Annotated[models.Player, Depends(get_player_dependency(True))]

PLAYER_READ_SCOPE = Scopes.COMMUNITY_READ | Scopes.REPORT_READ | Scopes.BAN_READ


@router.get("/players", response_model=PaginatedResponse[schemas.PlayerRef])
async def get_players(
    db: DatabaseDep,
    paginator: PaginatorDep,
    token: Annotated[
        web_schemas.TokenWithHash,
        Security(get_active_token, scopes=PLAYER_READ_SCOPE.to_list()),
    ],
    player_game_id: str | None = None,
):
    if player_game_id:
        db_player = await players.get_player_by_any_game_id(db, player_game_id)
        db_players = [db_player] if db_player is not None else []
    else:
        db_players = await players.get_all_players(
            db, limit=paginator.limit, offset=paginator.offset
        )

    return paginator.paginate(db_players)


@router.get("/players/{player_id}", response_model=schemas.Player)
async def get_player(
    db: DatabaseDep,
    token: Annotated[
        web_schemas.TokenWithHash,
        Security(get_active_token, scopes=PLAYER_READ_SCOPE.to_list()),
    ],
    player: PlayerWithRelationsDep,
):
    return player


def setup(app: FastAPI):
    app.include_router(router)
