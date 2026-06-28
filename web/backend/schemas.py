"""Pydantic schemas - the API contract.

These mirror the TypeScript interfaces in ``web/frontend/src/types/index.ts``.
Most fields are optional because raw save shapes vary across game versions;
the frontend treats anything missing as "unknown".
"""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel


# ---- health / system --------------------------------------------------------

class HealthResponse(BaseModel):
    status: str = "ok"
    version: str
    app_version: str
    game_version: str
    save_loaded: bool


class LanguageInfo(BaseModel):
    code: str
    label: str


class LanguagesResponse(BaseModel):
    current: str
    default: str
    available: list[LanguageInfo]


# ---- save lifecycle ---------------------------------------------------------

class SaveSummary(BaseModel):
    filename: str
    save_dir: str
    players_dir: str
    class_name: str
    save_type: int
    file_size: int
    loaded_at: float


class WorldCounts(BaseModel):
    guilds: int = 0
    players: int = 0
    bases: int = 0
    containers: int = 0
    characters: int = 0
    pals: int = 0


class SaveStateResponse(BaseModel):
    loaded: bool
    summary: Optional[SaveSummary] = None
    counts: Optional[WorldCounts] = None


class LoadResponse(BaseModel):
    summary: SaveSummary
    counts: WorldCounts


class ExportResponse(BaseModel):
    status: str
    filename: str
    size_bytes: int


# ---- world viewers (read-only) ---------------------------------------------

class PlayerSummary(BaseModel):
    uid: str
    name: str = "Unknown"
    level: int = 0
    pal_count: int = 0
    guild_id: Optional[str] = None
    guild_name: Optional[str] = None
    guild_level: Optional[int] = None
    is_leader: bool = False
    last_seen_seconds: Optional[float] = None
    last_seen_text: Optional[str] = None


class PlayerListResponse(BaseModel):
    players: list[PlayerSummary]
    total: int


class GuildSummary(BaseModel):
    id: str
    name: str = "Unnamed Guild"
    player_count: int = 0
    base_count: int = 0
    leader_uid: Optional[str] = None
    player_uids: list[str] = []


class GuildListResponse(BaseModel):
    guilds: list[GuildSummary]
    total: int


class BaseSummary(BaseModel):
    id: str
    guild_id: Optional[str] = None
    guild_name: Optional[str] = None
    guild_level: Optional[int] = None
    leader_name: Optional[str] = None
    member_count: int = 0
    total_bases: int = 0
    base_position: int = 0
    location: Optional[tuple[float, float, float]] = None
    area_range: float = 3500.0
    worker_count: int = 0


class BaseListResponse(BaseModel):
    bases: list[BaseSummary]
    total: int


class BaseDetail(BaseModel):
    id: str
    guild_id: Optional[str] = None
    guild_name: Optional[str] = None
    guild_level: int = 1
    leader_name: Optional[str] = None
    member_count: int = 0
    total_bases: int = 0
    base_position: int = 0
    location: Optional[tuple[float, float, float]] = None
    area_range: float = 3500.0
    worker_count: int = 0


class GuildMember(BaseModel):
    uid: str
    name: str = "Unknown"
    is_leader: bool = False
    _u8_flag: int = 3
    last_seen_seconds: Optional[float] = None


class GuildDetail(BaseModel):
    id: str
    name: str = "Unnamed Guild"
    level: int = 1
    admin_uid: str = ""
    member_count: int = 0
    base_count: int = 0
    members: list[GuildMember] = []
    base_ids: list[str] = []


class RenameGuildRequest(BaseModel):
    name: str


class SetGuildLevelRequest(BaseModel):
    level: int


class SetLeaderRequest(BaseModel):
    player_uid: str


class SetBaseRadiusRequest(BaseModel):
    radius: float


class DeleteBaseRequest(BaseModel):
    delete_workers: bool = False


class ContainerSummary(BaseModel):
    id: str
    container_type: str = "Unknown"
    owner_player_uid: Optional[str] = None
    guild_id: Optional[str] = None
    guild_name: Optional[str] = None
    base_camp_id: Optional[str] = None
    slot_count: int = 0
    item_count: int = 0
    location: Optional[tuple[float, float, float]] = None


class ContainerListResponse(BaseModel):
    containers: list[ContainerSummary]
    total: int
    has_more: bool = False


class ContainerItemSlot(BaseModel):
    slot_index: int = 0
    count: int = 0
    static_id: str = ""
    dynamic_id: Optional[str] = None


class ContainerDetail(BaseModel):
    id: str
    owner_player_uid: Optional[str] = None
    guild_id: Optional[str] = None
    slot_count: int = 0
    item_count: int = 0
    items: list[ContainerItemSlot] = []


class ExpandContainerRequest(BaseModel):
    new_slot_count: int


class PalSummary(BaseModel):
    instance_id: str
    gender: str = ""
    talent_hp: int = 0
    talent_shot: int = 0
    talent_defense: int = 0
    rank_hp: int = 0
    rank_attack: int = 0
    rank_defense: int = 0
    rank_craftspeed: int = 0
    passive_skills: list[str] = []
    active_skills: list[str] = []
    learned_skills: list[str] = []
    character_id: str = ""
    display_name: Optional[str] = None
    owner_uid: Optional[str] = None
    nickname: Optional[str] = None
    level: Optional[int] = None
    rank: Optional[int] = None
    is_illegal: bool = False


class PalListResponse(BaseModel):
    pals: list[PalSummary]
    total: int


# ---- player detail / mutation ------------------------------------------------

class PlayerDetail(BaseModel):
    uid: str
    name: str = "Unknown"
    level: int = 0
    pal_count: int = 0
    guild_id: Optional[str] = None
    guild_name: Optional[str] = None
    guild_level: int = 1
    is_leader: bool = False
    last_seen_seconds: Optional[float] = None
    last_seen_text: Optional[str] = None


class RenamePlayerRequest(BaseModel):
    name: str


class SetLevelRequest(BaseModel):
    level: int


class SetTechPointsRequest(BaseModel):
    tech_points: int = 0
    boss_tech_points: int = 0


class SetStatsRequest(BaseModel):
    max_hp: Optional[int] = None
    max_sp: Optional[int] = None
    attack: Optional[int] = None
    weight: Optional[int] = None
    capture_rate: Optional[int] = None
    work_speed: Optional[int] = None
    unused_stat_points: Optional[int] = None


class MaxAbilitiesRequest(BaseModel):
    uids: list[str]


# ---- map -------------------------------------------------------------------

class MapProjection(BaseModel):
    x: float
    y: float
    world_x: float
    world_y: float


class MapBase(BaseModel):
    id: str
    guild_id: Optional[str] = None
    guild_name: str = ""
    guild_level: int = 1
    leader_name: str = ""
    member_count: int = 0
    total_bases: int = 0
    base_position: int = 1
    location: Optional[tuple[float, float, float]] = None
    area_range: float = 3500.0
    map_type: str = "world"  # "world" | "tree"
    world_img: Optional[MapProjection] = None
    tree_img: Optional[MapProjection] = None


class MapPlayer(BaseModel):
    uid: str
    name: str = "Unknown"
    level: int = 0
    guild_id: Optional[str] = None
    guild_name: str = ""
    last_seen_text: Optional[str] = None
    pal_count: int = 0
    location: Optional[tuple[float, float, float]] = None
    map_type: str = "world"
    world_img: Optional[MapProjection] = None
    tree_img: Optional[MapProjection] = None


class MapDataResponse(BaseModel):
    bases: list[MapBase]
    players: list[MapPlayer]
    map_size: int = 2048
    world_coord_range: int = 1000
    tree_coord_range: int = 2500


# ---- static data -----------------------------------------------------------

class GameDataResponse(BaseModel):
    name: str
    data: Any


class I18nResponse(BaseModel):
    lang: str
    keys: dict[str, str]


# ---- tools ------------------------------------------------------------------

class ToolInfo(BaseModel):
    id: str
    name: str
    category: str  # "converting", "management", "utility"
    category_label: str
    icon: str
    description: str
    windows_only: bool = False


class ToolsListResponse(BaseModel):
    tools: list[ToolInfo]


class ConvertRequest(BaseModel):
    direction: str = "sav2json"  # "sav2json" | "json2sav"
    input_path: str
    output_path: str | None = None


class ConvertIdsRequest(BaseModel):
    input: str


class ConvertIdsResponse(BaseModel):
    input: str
    input_type: str
    steam_id: str | None = None
    palworld_uid: str | None = None
    nosteam_uid: str | None = None


class SlotInjectorRequest(BaseModel):
    level_sav_path: str | None = None
    players_folder: str | None = None
    new_slot_count: int = 960
    container_ids: list[str] | None = None
    use_loaded_save: bool = False


class FixHostSaveRequest(BaseModel):
    level_sav_path: str | None = None
    old_uid: str
    new_uid: str
    guild_fix: bool = True
    use_loaded_save: bool = False


class FixGuildRequest(BaseModel):
    level_sav_path: str | None = None
    player_uid: str
    target_guild_id: str
    use_loaded_save: bool = False


class CharacterTransferRequest(BaseModel):
    source_sav_path: str
    target_sav_path: str
    source_player_uid: str
    target_player_uid: str | None = None
    steps: dict | None = None


class PlayerMigrateRequest(BaseModel):
    source_sav_path: str
    target_sav_path: str
    source_player_uid: str
    target_player_uid: str | None = None


class ConvertExportRequest(BaseModel):
    output_path: str | None = None


class ToolResponse(BaseModel):
    success: bool
    message: str
    details: dict | None = None
