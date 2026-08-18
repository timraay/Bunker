from typing import Any

from barricade.enums import PlayerIDType


def find_player_id_in_attributes(attrs: dict) -> tuple[str | None, PlayerIDType]:
    player_id: str | None = None
    player_id_type = PlayerIDType.STEAM_64_ID

    # Find identifier of valid type
    identifiers: list[dict[str, Any]] = attrs["identifiers"]
    for identifier_data in identifiers:
        try:
            # TODO: Add HLL & HLLV EOS IDs
            player_id_type = PlayerIDType(identifier_data["type"])
        except ValueError:
            continue

        # If identifier is EOS ID, skip if not from HLL:V
        is_manual = bool(identifier_data.get("manual", False))
        metadata: dict[str, Any] = identifier_data.get("metadata", {})
        if (
            player_id_type == PlayerIDType.EOS_ID
            and metadata.get("game") != "hllv"
            and not is_manual
        ):
            continue

        player_id = identifier_data["identifier"]
        break

    if player_id and player_id.startswith("miHash:"):
        player_id = None

    return player_id, player_id_type
