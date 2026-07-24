"""Pydantic schemas - the API contract.

These mirror the TypeScript interfaces in ``web/frontend/src/types/index.ts``.
Most fields are optional because raw save shapes vary across game versions;
the frontend treats anything missing as "unknown".
"""

from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


# ---- health / system --------------------------------------------------------

class HealthResponse(BaseModel):
    status: str = "ok"
    version: str
    app_version: str
    game_version: str
    save_loaded: bool
    # Server-side defaults mirrored to the frontend so both sides share the
    # same storage-mode threshold and default. The client may still override
    # per-request via the load endpoints' params.
    storage_mode: str = "memory"
    large_save_threshold_mb: int = 50


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
    guild_tail_shape: str = "PostUpdate"


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
    # Decoded weapon/armor/egg payload — present only when dynamic_id resolves
    # to a DynamicItemSaveData entry. None for plain stackable items.
    dynamic: Optional["DynamicItemDetail"] = None


class DynamicItemDetail(BaseModel):
    """Decoded payload of a ``DynamicItemSaveData`` entry (weapon/armor/egg).

    Populated only for slots whose ``dynamic_id.local_id_in_created_world``
    resolves to a dynamic-item entry. Plain stackable items (nil GUID) omit it.
    The ``type`` field discriminates which optional fields are meaningful.
    """
    local_id: str
    static_id: str = ""
    type: str = "unknown"            # "weapon" | "armor" | "egg" | "unknown"
    # Weapon fields:
    durability: Optional[float] = None           # Weapon + Armor
    remaining_bullets: Optional[int] = None      # Weapon only
    passive_skills: list[str] = []               # Weapon only
    # Egg fields:
    character_id: Optional[str] = None
    egg_gender: Optional[str] = None
    egg_passive_skills: list[str] = []
    egg_talent_hp: Optional[int] = None
    egg_talent_shot: Optional[int] = None
    egg_talent_defense: Optional[int] = None


class ContainerDetail(BaseModel):
    id: str
    owner_player_uid: Optional[str] = None
    guild_id: Optional[str] = None
    slot_count: int = 0
    item_count: int = 0
    items: list[ContainerItemSlot] = []


class ExpandContainerRequest(BaseModel):
    new_slot_count: int


class SetSlotCountRequest(BaseModel):
    """Change one item slot's stack count (0 effectively clears the slot)."""
    slot_index: int = Field(ge=0)
    new_count: int = Field(ge=0, le=9999)


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
    # Container binding (present on grouped reads; omitted on the flat list).
    container_id: Optional[str] = None
    slot_index: int = 0
    # Icon + element join from characters.json (so the grid can render without
    # a second client-side fetch). None when the species isn't in the catalog.
    icon: Optional[str] = None
    elements: dict = {}
    # Derived flags for at-a-glance tile badges.
    is_boss: bool = False
    is_lucky: bool = False
    is_predator: bool = False
    is_sick: bool = False


class PalListResponse(BaseModel):
    pals: list[PalSummary]
    total: int


class PalGroupedResponse(BaseModel):
    """Pals pre-bucketed into a player's Party and Pal Box zones.

    ``party`` and ``palbox`` are sorted by ``slot_index``. Pals whose
    ``SlotId.ContainerId`` matches neither container id fall into ``ungrouped``
    (e.g. base-deployed pals, or pals with a missing slot struct) so nothing
    vanishes silently.
    """
    party_id: Optional[str] = None
    palbox_id: Optional[str] = None
    party: list[PalSummary] = []
    palbox: list[PalSummary] = []
    ungrouped: list[PalSummary] = []


# ---- pal editor: detail / mutation -----------------------------------------

class PalDetail(BaseModel):
    """Full editable pal detail (mirrors PalService.read_pal_detail output)."""
    instance_id: str
    character_id: str = ""
    display_name: Optional[str] = None
    icon: Optional[str] = None
    nickname: Optional[str] = None
    gender: str = ""
    level: int = 1
    exp: int = 0
    rank: int = 1
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
    work_suitability: dict = {}
    hp: int = 0
    max_hp: int = 0
    stomach: float = 0.0
    sanity: float = 100.0
    friendship_point: int = 0
    is_boss: bool = False
    is_lucky: bool = False
    is_predator: bool = False
    is_tower: bool = False
    is_sick: bool = False
    owner_uid: Optional[str] = None
    storage_id: Optional[str] = None
    storage_slot: int = 0
    boss_available: bool = False


class PalDetailResponse(BaseModel):
    pal: PalDetail


class PalEditRequest(BaseModel):
    """Granular pal edit. Each field optional; None/absent = don't touch.

    Numeric ranges are byte-width ceilings (0-255); semantic caps (IV 0-100,
    level 1-80, rank 1-5) are enforced in pal_service based on ``cheat_mode``.
    """
    nickname: Optional[str] = None
    character_id: Optional[str] = None
    gender: Optional[str] = None
    is_lucky: Optional[bool] = None
    is_boss: Optional[bool] = None
    level: Optional[int] = Field(None, ge=1, le=255)
    exp: Optional[int] = Field(None, ge=0)
    rank: Optional[int] = Field(None, ge=1, le=255)
    talent_hp: Optional[int] = Field(None, ge=0, le=255)
    talent_shot: Optional[int] = Field(None, ge=0, le=255)
    talent_defense: Optional[int] = Field(None, ge=0, le=255)
    rank_hp: Optional[int] = Field(None, ge=0, le=255)
    rank_attack: Optional[int] = Field(None, ge=0, le=255)
    rank_defense: Optional[int] = Field(None, ge=0, le=255)
    rank_craftspeed: Optional[int] = Field(None, ge=0, le=255)
    passive_skills: Optional[list[str]] = None
    active_skills: Optional[list[str]] = None
    learned_skills: Optional[list[str]] = None
    work_suitability: Optional[dict] = None
    friendship_point: Optional[int] = Field(None, ge=0, le=200000)
    cheat_mode: bool = False


class MovePalRequest(BaseModel):
    target_container_id: str
    player_uid: str


class SwapPalRequest(BaseModel):
    """Drag-and-drop slot swap: drop pal A onto pal B → they exchange places."""
    pal_a: str
    pal_b: str


class PalSkillCatalogResponse(BaseModel):
    passives: list[dict]
    actives: list[dict]


# ---- pal presets (JSON-file-backed) ----------------------------------------

class PalPreset(BaseModel):
    """A saved stat/skill profile. Every field optional; None = 'don't touch'."""
    id: Optional[str] = None
    name: str
    nickname: Optional[str] = None
    character_id: Optional[str] = None
    gender: Optional[str] = None
    is_lucky: Optional[bool] = None
    is_boss: Optional[bool] = None
    level: Optional[int] = None
    exp: Optional[int] = None
    rank: Optional[int] = None
    talent_hp: Optional[int] = None
    talent_shot: Optional[int] = None
    talent_defense: Optional[int] = None
    rank_hp: Optional[int] = None
    rank_attack: Optional[int] = None
    rank_defense: Optional[int] = None
    rank_craftspeed: Optional[int] = None
    passive_skills: Optional[list[str]] = None
    active_skills: Optional[list[str]] = None
    learned_skills: Optional[list[str]] = None
    work_suitability: Optional[dict] = None
    friendship_point: Optional[int] = None


class PresetListResponse(BaseModel):
    presets: list[PalPreset]


class PresetSaveRequest(BaseModel):
    name: str
    preset: PalPreset


class PresetApplyRequest(BaseModel):
    instance_ids: list[str]
    preset_id: str
    cheat_mode: bool = False


class PresetApplyResponse(BaseModel):
    applied: int
    failed: list[str]
    errors: dict = {}


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
    # Container IDs read from the player's .sav (OtomoCharacterContainerId =
    # party, PalStorageContainerId = palbox). Used by the pal-editor grid to
    # bucket pals into zones. None when the .sav isn't available/decoded.
    party_id: Optional[str] = None
    palbox_id: Optional[str] = None


class RenamePlayerRequest(BaseModel):
    name: str


class SetLevelRequest(BaseModel):
    level: int


class SetTechPointsRequest(BaseModel):
    tech_points: int = 0
    boss_tech_points: int = 0


class SetStatsRequest(BaseModel):
    """Stat-point allocation. Each stat is a 0-100 rank value (the game translates
    to in-game HP/Stamina/etc. via base+mult formulas). ``None`` = don't touch."""
    max_hp: Optional[int] = Field(None, ge=0, le=100)
    max_sp: Optional[int] = Field(None, ge=0, le=100)
    attack: Optional[int] = Field(None, ge=0, le=100)
    weight: Optional[int] = Field(None, ge=0, le=100)
    capture_rate: Optional[int] = Field(None, ge=0, le=100)
    work_speed: Optional[int] = Field(None, ge=0, le=100)
    unused_stat_points: Optional[int] = Field(None, ge=0, le=10000)


class PlayerStatsResponse(BaseModel):
    max_hp: int = 0
    max_sp: int = 0
    attack: int = 0
    weight: int = 0
    capture_rate: int = 0
    work_speed: int = 0
    unused_stat_points: int = 0


class PlayerTechPointsResponse(BaseModel):
    tech_points: int = 0
    boss_tech_points: int = 0


class PlayerTechnologiesResponse(BaseModel):
    """The player's currently-unlocked recipe list + tech-point pools."""
    technologies: list[str] = []
    tech_points: int = 0
    boss_tech_points: int = 0


class SetTechnologiesRequest(BaseModel):
    """Replace the player's entire unlock list. Idempotent; unknowns dropped."""
    technologies: list[str]


class MaxAbilitiesRequest(BaseModel):
    uids: list[str]


# ---- inventory (player bags + base chests) ----------------------------------

class InventoryBag(BaseModel):
    """One of the six player inventory bags (Common/Key/Weapon/Armor/Food/Drop).

    The bag's actual slots live in a world-level ``ItemContainerSaveData``
    entry; ``container_id`` is the link from the player's ``.sav``
    ``InventoryInfo``. ``None`` means the bag isn't allocated for this player.
    """
    bag_type: str        # "common"|"essential"|"weapon"|"armor"|"food"|"drop"
    label: str
    container_id: Optional[str] = None
    slot_count: int = 0
    item_count: int = 0
    items: list[ContainerItemSlot] = []


class PlayerInventoryResponse(BaseModel):
    """A player's full inventory snapshot: bags + party/palbox ids + stats."""
    uid: str
    name: str = "Unknown"
    bags: list[InventoryBag] = []
    party_id: Optional[str] = None
    palbox_id: Optional[str] = None
    stats: Optional[PlayerStatsResponse] = None


class BaseInventoryContainer(BaseModel):
    """A storage chest that belongs to a specific base camp."""
    id: str
    container_type: str = "Unknown"
    slot_count: int = 0
    item_count: int = 0
    items: list[ContainerItemSlot] = []
    location: Optional[tuple[float, float, float]] = None


class BaseInventoryResponse(BaseModel):
    """A base camp's inventory snapshot: its chests + its working pals."""
    base_id: str
    guild_name: Optional[str] = None
    containers: list[BaseInventoryContainer] = []
    worker_container_id: Optional[str] = None
    workers: list[PalSummary] = []


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


# ---- POIs (Points of Interest, ported from PSP Rust) -----------------------

class PoiProjection(BaseModel):
    """Pre-computed pixel + world coords for a POI on one map (world or tree)."""
    x: float
    y: float
    world_x: float
    world_y: float


class PoiEntity(BaseModel):
    """A combined boss / alpha-pal / predator-pal POI.

    ``subtype`` distinguishes the source:
      - ``"boss"``     — from ``bosses.json`` (tower / field / human NPC)
      - ``"alpha"``    — open-world alpha-spawn (pal portrait, white border)
      - ``"predator"`` — lucky/red-eyed variant (pal portrait, red border)
    """
    id: str
    name: str = ""
    subtype: str = "boss"  # "boss" | "alpha" | "predator"
    x: float = 0.0
    y: float = 0.0
    character_id: str = ""
    spawner_id: str = ""
    level: int = 0
    pal: str = ""
    world_img: Optional[PoiProjection] = None
    tree_img: Optional[PoiProjection] = None


class PoiDungeon(BaseModel):
    id: str
    name: str = ""
    x: float = 0.0
    y: float = 0.0
    world_img: Optional[PoiProjection] = None
    tree_img: Optional[PoiProjection] = None


class PoiFastTravel(BaseModel):
    id: str
    class_: str = Field(default="", alias="class")
    name: str = ""
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0
    world_img: Optional[PoiProjection] = None
    tree_img: Optional[PoiProjection] = None


class PoiRelic(BaseModel):
    id: str
    class_: str = Field(default="", alias="class")
    relic_type: str = "capture_power"
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0
    world_img: Optional[PoiProjection] = None
    tree_img: Optional[PoiProjection] = None


class MapPoiResponse(BaseModel):
    """All POI datasets, each with pre-computed world/tree projections."""
    entities: list[PoiEntity] = []
    dungeons: list[PoiDungeon] = []
    fast_travel: list[PoiFastTravel] = []
    relics: list[PoiRelic] = []
    relic_data: dict[str, Any] = {}


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


# ---- breeding calculator ----------------------------------------------------
# Mirrors the dataclasses in src/palworld_aio/breeding/model.py. The breeding
# engine is loaded via importlib (see services/breeding_service.py) and never
# imported directly, so these Pydantic models are the API's own serialization
# layer — keep them in sync with src/types/index.ts on the frontend.

class BreedablePal(BaseModel):
    """One entry in the breedable-pal picker list."""
    tribe: str                       # internal asset name (join key)
    display_name: str
    icon: Optional[str] = None
    combi_rank: int = 0
    rarity: int = 0
    gender_prob: dict = {}           # {"male": 0.4, "female": 0.6}


class BreedablePalsResponse(BaseModel):
    pals: list[BreedablePal]
    total: int


class DirectChildRequest(BaseModel):
    parent_a: str
    parent_b: str


class DirectPartnersRequest(BaseModel):
    parent_a: str
    target_child: str


class DirectParentsRequest(BaseModel):
    """Find ALL parent pairs for a target child — no fixed parent."""

    target_child: str


class DirectResultItem(BaseModel):
    parent_a: str
    parent_b: str
    child: str
    child_display: Optional[str] = None
    child_icon: Optional[str] = None
    child_gender_prob: Optional[dict] = None
    combo_type: Literal["formula", "unique"] = "formula"


class DirectChildResponse(BaseModel):
    result: Optional[DirectResultItem] = None


class DirectPartnersResponse(BaseModel):
    partners: list[DirectResultItem]


class DirectParentsResponse(BaseModel):
    """All parent pairs for a target child — reuses the same item shape."""

    parents: list[DirectResultItem]


class SelectedPal(BaseModel):
    """A user-picked theoretical pal for Selection Mode."""
    species: str
    gender: Optional[str] = None     # "Male" | "Female" | None (Wildcard)
    passives: list[str] = []


class ChainRequest(BaseModel):
    target_pal: str
    required_passives: list[str] = []
    target_gender: Optional[str] = None   # "Male" | "Female" | None
    max_generations: int = 5
    mode: Literal["selection", "save"] = "selection"
    # mode="selection": the user's theoretical pool.
    selected_pals: list[SelectedPal] = []
    # mode="save": filter the loaded save's pals by owner. None = all players.
    owner_uid: Optional[str] = None
    include_wild: bool = False
    max_results: int = 5


class BreedingStepSchema(BaseModel):
    parent_a: str
    parent_b: str
    child: str
    inherited_passives: list[str] = []
    gender_feasible: bool = True


class ChainSchema(BaseModel):
    target: str
    generations: int
    steps: list[BreedingStepSchema]
    final_passives: list[str]
    sources: list[dict]
    gender_feasible: bool
    matched_passives: list[str] = []


class ChainResponse(BaseModel):
    chains: list[ChainSchema]
    total: int
    elapsed_ms: int
    warnings: list[str] = []


# Resolve the ContainerItemSlot -> DynamicItemDetail forward reference.
ContainerItemSlot.model_rebuild()
