
from __future__ import annotations
from .character_transfer import character_transfer


# Player Migrate — simplified character transfer


def player_migrate(
    source_sav_path: str,
    target_sav_path: str,
    source_player_uid: str,
    target_player_uid: str | None = None,
) -> dict:
    """Migrate a player's guild / base / pals to another save file."""
    return character_transfer(
        source_sav_path=source_sav_path,
        target_sav_path=target_sav_path,
        source_player_uid=source_player_uid,
        target_player_uid=target_player_uid,
        steps={"character": True, "tech_data": True, "inventory": False,
               "guild": True, "pals": True, "dynamics": True, "timestamps": True},
    )
