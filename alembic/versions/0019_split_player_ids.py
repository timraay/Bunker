"""Split player IDs

Revision ID: 9da79cb1c027
Revises: 029504e67ec2
Create Date: 2026-08-05 12:19:30.612373

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "9da79cb1c027"
down_revision: str | None = "029504e67ec2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PlayerPlatform = postgresql.ENUM(
    "STEAM",
    "EPIC",
    "XBOX",
    "PLAYSTATION",
    name="playerplatform",
    create_type=False,
)

Game = postgresql.ENUM("HLL", "HLLV", name="game", create_type=False)


def _reset_sequence(sequence_name: str, table_name: str) -> None:
    op.execute(
        sa.text(
            f"SELECT setval('{sequence_name}', COALESCE((SELECT MAX(id) FROM {table_name}), 1), (SELECT COUNT(*) > 0 FROM {table_name}))"
        )
    )


"""
Previously, the `player.id` PK was the player's Steam ID or XPlay ID, which was a string. This migration
changes the `player.id` PK to be an autoincrementing integer, with the old Steam ID being stored in new
`player.steam_id` and `player.xplay_id` columns. The `player_bans`, `player_reports`, and `player_watchlists`
tables are updated to use the new integer `player.id` autoincrementing PK as a foreign key instead of the old
string.
"""


def upgrade() -> None:
    # We'll create new tables with integer PKs, copy data across, and swap them in.
    # Create new players table with an integer autoincrement PK and new id columns.
    op.create_table(
        "players_new",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("steam_id", sa.String(), nullable=True),
        sa.Column("xplay_id", sa.String(), nullable=True),
        sa.Column("bm_rcon_url", sa.String(), nullable=True),
        sa.Column("hll_eos_id", sa.String(), nullable=True),
        sa.Column("hllv_eos_id", sa.String(), nullable=True),
        sa.Column("platform", PlayerPlatform, nullable=True),
        sa.PrimaryKeyConstraint("id", name="players_new_pkey"),
    )

    # Copy existing players into the new table. The old `players.id` held the Steam ID string;
    # store it in `steam_id` on the new table so we can map foreign keys.
    op.execute(
        """
        INSERT INTO players_new (steam_id, xplay_id, bm_rcon_url, hll_eos_id, hllv_eos_id, platform)
        SELECT id AS steam_id, NULL AS xplay_id, bm_rcon_url, hll_eos_id, hllv_eos_id, platform
        FROM players
        """
    )

    # Create new dependent tables that reference the integer PK on players_new
    op.create_table(
        "player_bans_new",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("player_id", sa.Integer(), nullable=False),
        sa.Column("integration_id", sa.Integer(), nullable=False),
        sa.Column("remote_id", sa.String(), nullable=False),
        sa.Column("game", Game, nullable=False, server_default="HLL"),
        sa.ForeignKeyConstraint(
            ["integration_id"], ["integrations.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["player_id"], ["players_new.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("player_id", "integration_id"),
    )

    op.create_table(
        "player_reports_new",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("player_id", sa.Integer(), nullable=False),
        sa.Column("report_id", sa.Integer(), nullable=False),
        sa.Column("player_name", sa.String(), nullable=False),
        sa.ForeignKeyConstraint(["player_id"], ["players_new.id"]),
        sa.ForeignKeyConstraint(["report_id"], ["reports.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "player_watchlists_new",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("player_id", sa.Integer(), nullable=False),
        sa.Column("community_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["community_id"], ["communities.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["player_id"], ["players_new.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("player_id", "community_id"),
    )

    # Populate dependent tables by mapping the old string player id to the new integer id
    op.execute(
        """
        INSERT INTO player_bans_new (id, player_id, integration_id, remote_id, game)
        SELECT pb.id, pn.id, pb.integration_id, pb.remote_id, pb.game
        FROM player_bans pb
        JOIN players p ON p.id = pb.player_id
        JOIN players_new pn ON pn.steam_id = p.id
        """
    )

    op.execute(
        """
        INSERT INTO player_reports_new (id, player_id, report_id, player_name)
        SELECT pr.id, pn.id, pr.report_id, pr.player_name
        FROM player_reports pr
        JOIN players p ON p.id = pr.player_id
        JOIN players_new pn ON pn.steam_id = p.id
        """
    )

    op.execute(
        """
        INSERT INTO player_watchlists_new (id, player_id, community_id)
        SELECT pw.id, pn.id, pw.community_id
        FROM player_watchlists pw
        JOIN players p ON p.id = pw.player_id
        JOIN players_new pn ON pn.steam_id = p.id
        """
    )

    # So far we assumed `players.id` was the Steam ID. It can also be the XPlay ID instead.
    # Update all player rows where `steam_id` is not actually a Steam ID.
    op.execute(
        """
        UPDATE players_new
        SET xplay_id = steam_id,
            steam_id = NULL
        WHERE LENGTH(steam_id) != 17
        """
    )

    # Update the FK constraint on player_report_responses to reference the new integer PK on player_reports_new
    op.drop_constraint(
        "player_report_responses_pr_id_fkey",
        "player_report_responses",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "player_report_responses_pr_id_fkey",
        "player_report_responses",
        "player_reports_new",
        ["pr_id"],
        ["id"],
    )

    # Drop old tables and rename the new ones into place
    op.drop_table("player_watchlists")
    op.drop_table("player_reports")
    op.drop_table("player_bans")
    op.drop_table("players")

    op.rename_table("players_new", "players")
    op.rename_table("player_bans_new", "player_bans")
    op.rename_table("player_reports_new", "player_reports")
    op.rename_table("player_watchlists_new", "player_watchlists")

    # Rename constraints on the new tables to match the old names
    op.execute("ALTER TABLE players RENAME CONSTRAINT players_new_pkey TO players_pkey")
    op.execute(
        "ALTER TABLE player_bans RENAME CONSTRAINT player_bans_new_integration_id_fkey TO player_bans_integration_id_fkey"
    )
    op.execute(
        "ALTER TABLE player_bans RENAME CONSTRAINT player_bans_new_player_id_fkey TO player_bans_player_id_fkey"
    )
    op.execute(
        "ALTER TABLE player_bans RENAME CONSTRAINT player_bans_new_pkey TO player_bans_pkey"
    )
    op.execute(
        "ALTER TABLE player_bans RENAME CONSTRAINT player_bans_new_player_id_integration_id_key TO player_bans_player_id_integration_id_key"
    )
    op.execute(
        "ALTER TABLE player_reports RENAME CONSTRAINT player_reports_new_pkey TO player_reports_pkey"
    )
    op.execute(
        "ALTER TABLE player_reports RENAME CONSTRAINT player_reports_new_player_id_fkey TO player_reports_player_id_fkey"
    )
    op.execute(
        "ALTER TABLE player_reports RENAME CONSTRAINT player_reports_new_report_id_fkey TO player_reports_report_id_fkey"
    )
    op.execute(
        "ALTER TABLE player_watchlists RENAME CONSTRAINT player_watchlists_new_community_id_fkey TO player_watchlists_community_id_fkey"
    )
    op.execute(
        "ALTER TABLE player_watchlists RENAME CONSTRAINT player_watchlists_new_player_id_fkey TO player_watchlists_player_id_fkey"
    )
    op.execute(
        "ALTER TABLE player_watchlists RENAME CONSTRAINT player_watchlists_new_pkey TO player_watchlists_pkey"
    )
    op.execute(
        "ALTER TABLE player_watchlists RENAME CONSTRAINT player_watchlists_new_player_id_community_id_key TO player_watchlists_player_id_community_id_key"
    )

    # Update sequences
    op.execute("ALTER SEQUENCE players_new_id_seq RENAME TO players_id_seq")
    op.execute("ALTER SEQUENCE player_bans_new_id_seq RENAME TO player_bans_id_seq")
    op.execute(
        "ALTER SEQUENCE player_reports_new_id_seq RENAME TO player_reports_id_seq"
    )
    op.execute(
        "ALTER SEQUENCE player_watchlists_new_id_seq RENAME TO player_watchlists_id_seq"
    )

    _reset_sequence("players_id_seq", "players")
    _reset_sequence("player_bans_id_seq", "player_bans")
    _reset_sequence("player_reports_id_seq", "player_reports")
    _reset_sequence("player_watchlists_id_seq", "player_watchlists")

    # Recreate indexes on the new players table
    op.create_index(
        op.f("ix_players_hllv_eos_id"), "players", ["hllv_eos_id"], unique=True
    )
    op.create_index(op.f("ix_players_steam_id"), "players", ["steam_id"], unique=True)
    op.create_index(op.f("ix_players_xplay_id"), "players", ["xplay_id"], unique=True)


def downgrade() -> None:
    # Reverse the upgrade: recreate the old string-keyed players table and dependent tables,
    # copy data back, then drop the integer-keyed tables.
    # Create old players table (id as string primary key)
    op.create_table(
        "players_old",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("bm_rcon_url", sa.String(), nullable=True),
        sa.Column("hll_eos_id", sa.String(), nullable=True),
        sa.Column("hllv_eos_id", sa.String(), nullable=True),
        sa.Column("platform", PlayerPlatform, nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )

    # Copy data back, mapping `steam_id` to the old string primary key
    op.execute(
        """
        INSERT INTO players_old (id, bm_rcon_url, hll_eos_id, hllv_eos_id, platform)
        SELECT COALESCE(steam_id, xplay_id), bm_rcon_url, hll_eos_id, hllv_eos_id, platform
        FROM players
        """
    )

    # Recreate dependent tables with player_id as string FK
    op.create_table(
        "player_bans_old",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("player_id", sa.String(), nullable=False),
        sa.Column("integration_id", sa.Integer(), nullable=False),
        sa.Column("remote_id", sa.String(), nullable=False),
        sa.Column("game", Game, nullable=False, server_default="HLL"),
        sa.ForeignKeyConstraint(
            ["integration_id"], ["integrations.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["player_id"], ["players_old.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("player_id", "integration_id"),
    )

    op.create_table(
        "player_reports_old",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("player_id", sa.String(), nullable=False),
        sa.Column("report_id", sa.Integer(), nullable=False),
        sa.Column("player_name", sa.String(), nullable=False),
        sa.ForeignKeyConstraint(["player_id"], ["players_old.id"]),
        sa.ForeignKeyConstraint(["report_id"], ["reports.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "player_watchlists_old",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("player_id", sa.String(), nullable=False),
        sa.Column("community_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["community_id"], ["communities.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["player_id"], ["players_old.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("player_id", "community_id"),
    )

    # Populate dependent old tables mapping integer player id -> steam_id string
    op.execute(
        """
        INSERT INTO player_bans_old (id, player_id, integration_id, remote_id, game)
        SELECT pb.id, p_old.id, pb.integration_id, pb.remote_id, pb.game
        FROM player_bans pb
        JOIN players p ON p.id = pb.player_id
        JOIN players_old p_old ON p_old.id = COALESCE(p.steam_id, p.xplay_id)
        """
    )

    op.execute(
        """
        INSERT INTO player_reports_old (id, player_id, report_id, player_name)
        SELECT pr.id, p_old.id, pr.report_id, pr.player_name
        FROM player_reports pr
        JOIN players p ON p.id = pr.player_id
        JOIN players_old p_old ON p_old.id = COALESCE(p.steam_id, p.xplay_id)
        """
    )

    op.execute(
        """
        INSERT INTO player_watchlists_old (id, player_id, community_id)
        SELECT pw.id, p_old.id, pw.community_id
        FROM player_watchlists pw
        JOIN players p ON p.id = pw.player_id
        JOIN players_old p_old ON p_old.id = COALESCE(p.steam_id, p.xplay_id)
        """
    )

    # Update the FK constraint on player_report_responses to reference the new integer PK on player_reports_old
    op.drop_constraint(
        "player_report_responses_pr_id_fkey",
        "player_report_responses",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "player_report_responses_pr_id_fkey",
        "player_report_responses",
        "player_reports_old",
        ["pr_id"],
        ["id"],
    )

    # Drop the integer-keyed tables and rename the _old tables back to original names
    op.drop_table("player_watchlists")
    op.drop_table("player_reports")
    op.drop_table("player_bans")
    op.drop_table("players")

    op.rename_table("players_old", "players")
    op.rename_table("player_bans_old", "player_bans")
    op.rename_table("player_reports_old", "player_reports")
    op.rename_table("player_watchlists_old", "player_watchlists")

    # Rename constraints on the new tables to match the old names
    op.execute("ALTER TABLE players RENAME CONSTRAINT players_old_pkey TO players_pkey")
    op.execute(
        "ALTER TABLE player_bans RENAME CONSTRAINT player_bans_old_integration_id_fkey TO player_bans_integration_id_fkey"
    )
    op.execute(
        "ALTER TABLE player_bans RENAME CONSTRAINT player_bans_old_player_id_fkey TO player_bans_player_id_fkey"
    )
    op.execute(
        "ALTER TABLE player_bans RENAME CONSTRAINT player_bans_old_pkey TO player_bans_pkey"
    )
    op.execute(
        "ALTER TABLE player_bans RENAME CONSTRAINT player_bans_old_player_id_integration_id_key TO player_bans_player_id_integration_id_key"
    )
    op.execute(
        "ALTER TABLE player_reports RENAME CONSTRAINT player_reports_old_pkey TO player_reports_pkey"
    )
    op.execute(
        "ALTER TABLE player_reports RENAME CONSTRAINT player_reports_old_player_id_fkey TO player_reports_player_id_fkey"
    )
    op.execute(
        "ALTER TABLE player_reports RENAME CONSTRAINT player_reports_old_report_id_fkey TO player_reports_report_id_fkey"
    )
    op.execute(
        "ALTER TABLE player_watchlists RENAME CONSTRAINT player_watchlists_old_community_id_fkey TO player_watchlists_community_id_fkey"
    )
    op.execute(
        "ALTER TABLE player_watchlists RENAME CONSTRAINT player_watchlists_old_player_id_fkey TO player_watchlists_player_id_fkey"
    )
    op.execute(
        "ALTER TABLE player_watchlists RENAME CONSTRAINT player_watchlists_old_pkey TO player_watchlists_pkey"
    )
    op.execute(
        "ALTER TABLE player_watchlists RENAME CONSTRAINT player_watchlists_old_player_id_community_id_key TO player_watchlists_player_id_community_id_key"
    )

    # Update sequences
    op.execute("ALTER SEQUENCE player_bans_old_id_seq RENAME TO player_bans_id_seq")
    op.execute(
        "ALTER SEQUENCE player_reports_old_id_seq RENAME TO player_reports_id_seq"
    )
    op.execute(
        "ALTER SEQUENCE player_watchlists_old_id_seq RENAME TO player_watchlists_id_seq"
    )

    _reset_sequence("player_bans_id_seq", "player_bans")
    _reset_sequence("player_reports_id_seq", "player_reports")
    _reset_sequence("player_watchlists_id_seq", "player_watchlists")
