from typing import TYPE_CHECKING

from sqlalchemy.orm import Mapped, mapped_column, relationship

from barricade.db import ModelBase
from barricade.enums import PlayerPlatform

if TYPE_CHECKING:
    from .player_ban import PlayerBan
    from .player_report import PlayerReport
    from .player_watchlist import PlayerWatchlist


class Player(ModelBase):
    __tablename__ = "players"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    steam_id: Mapped[str | None] = mapped_column(index=True, unique=True)
    xplay_id: Mapped[str | None] = mapped_column(index=True, unique=True)
    bm_rcon_url: Mapped[str | None]
    hll_eos_id: Mapped[str | None]
    hllv_eos_id: Mapped[str | None] = mapped_column(index=True, unique=True)
    platform: Mapped[PlayerPlatform | None]

    reports: Mapped[list["PlayerReport"]] = relationship(back_populates="player")
    bans: Mapped[list["PlayerBan"]] = relationship(back_populates="player")
    watchlists: Mapped[list["PlayerWatchlist"]] = relationship(back_populates="player")
