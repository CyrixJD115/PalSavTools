// TypeScript types mirroring web/backend/schemas.py. Single source of truth for
// the API contract; both sides must stay in sync.

export interface HealthResponse {
  status: string;
  version: string;
  app_version: string;
  game_version: string;
  save_loaded: boolean;
  /** Server default for where the decoded save lives ("memory" | "disk"). */
  storage_mode: StorageMode;
  /** Files above this size (MB) trigger the storage-mode warning on upload. */
  large_save_threshold_mb: number;
}

/** Where the decoded save lives after load. Mirrors backend StorageMode. */
export type StorageMode = 'memory' | 'disk';

/** Load-stage progress pushed over /ws during save load. */
export interface LoadProgressPayload {
  /** "parse" | "precompute" | "prewarm" | "done" */
  stage: string;
  /** 1-indexed section position when stage === "prewarm". */
  current: number;
  /** Total sections when stage === "prewarm". */
  total: number;
  /** Section name being materialized when stage === "prewarm". */
  section: string | null;
}

/** Options forwarded to /save/load and /save/upload. */
export interface LoadOptions {
  storageMode?: StorageMode;
  prewarm?: boolean;
}

export interface LanguageInfo {
  code: string;
  label: string;
}

export interface LanguagesResponse {
  current: string;
  default: string;
  available: LanguageInfo[];
}

export interface SaveSummary {
  filename: string;
  save_dir: string;
  players_dir: string;
  class_name: string;
  save_type: number;
  file_size: number;
  loaded_at: number;
}

export interface WorldCounts {
  guilds: number;
  players: number;
  bases: number;
  containers: number;
  characters: number;
  pals: number;
}

export interface SaveStateResponse {
  loaded: boolean;
  summary: SaveSummary | null;
  counts: WorldCounts | null;
}

export interface LoadResponse {
  summary: SaveSummary;
  counts: WorldCounts;
}

export interface PlayerSummary {
  uid: string;
  name: string;
  level: number;
  pal_count: number;
  guild_id: string | null;
  guild_name: string | null;
  guild_level: number | null;
  is_leader: boolean;
  last_seen_seconds: number | null;
  last_seen_text: string | null;
}

export interface PlayerListResponse {
  players: PlayerSummary[];
  total: number;
}

export interface PlayerDetail {
  uid: string;
  name: string;
  level: number;
  pal_count: number;
  guild_id: string | null;
  guild_name: string | null;
  guild_level: number;
  is_leader: boolean;
  last_seen_seconds: number | null;
  last_seen_text: string | null;
  party_id?: string | null;
  palbox_id?: string | null;
}

export interface RenamePlayerRequest {
  name: string;
}

export interface SetLevelRequest {
  level: number;
}

export interface SetTechPointsRequest {
  tech_points: number;
  boss_tech_points: number;
}

export interface SetStatsRequest {
  max_hp?: number;
  max_sp?: number;
  attack?: number;
  weight?: number;
  capture_rate?: number;
  work_speed?: number;
  unused_stat_points?: number;
}

export interface PlayerStatsResponse {
  max_hp: number;
  max_sp: number;
  attack: number;
  weight: number;
  capture_rate: number;
  work_speed: number;
  unused_stat_points: number;
}

export interface PlayerTechPointsResponse {
  tech_points: number;
  boss_tech_points: number;
}

/** The player's currently-unlocked recipe list + tech-point pools. */
export interface PlayerTechnologiesResponse {
  technologies: string[];
  tech_points: number;
  boss_tech_points: number;
}

/** Replace the player's entire unlock list. Idempotent; unknowns dropped. */
export interface SetTechnologiesRequest {
  technologies: string[];
}

/** One entry in the game-data technology catalog (world.json#technology[]).
 *  Used by TechTreeModal to render the 588-recipe grid. */
export interface Technology {
  asset: string;                 // unlock key (what's stored in the save)
  name: string;
  icon: string | null;
  description: string | null;
  cost: number;                  // tech-point cost
  level_cap: number;             // player level required (1-80)
  type: 'standard' | 'boss';     // standard vs ancient
  is_boss_tech: boolean;
  require_technology: string;    // prerequisite asset name (or "")
  require_tower_boss: string;    // "None" | "ForestBoss" | ...
  unlock_build_objects: string[];
  unlock_item_recipes: string[];
}

export interface MaxAbilitiesRequest {
  uids: string[];
}

export interface GuildSummary {
  id: string;
  name: string;
  player_count: number;
  base_count: number;
  leader_uid: string | null;
  player_uids: string[];
}

export interface GuildListResponse {
  guilds: GuildSummary[];
  total: number;
}

export interface GuildMember {
  uid: string;
  name: string;
  is_leader: boolean;
  _u8_flag: number;
  last_seen_seconds: number | null;
}

export interface GuildDetail {
  id: string;
  name: string;
  level: number;
  admin_uid: string;
  member_count: number;
  base_count: number;
  members: GuildMember[];
  base_ids: string[];
}

export interface SetLeaderRequest {
  player_uid: string;
}

export type Vec3 = [number, number, number] | null;

export interface BaseSummary {
  id: string;
  guild_id: string | null;
  guild_name: string | null;
  guild_level: number | null;
  leader_name: string | null;
  member_count: number;
  total_bases: number;
  base_position: number;
  location: Vec3;
  area_range: number;
  worker_count: number;
}

export interface BaseListResponse {
  bases: BaseSummary[];
  total: number;
}

export interface BaseDetail {
  id: string;
  guild_id: string | null;
  guild_name: string | null;
  guild_level: number;
  leader_name: string | null;
  member_count: number;
  total_bases: number;
  base_position: number;
  location: Vec3;
  area_range: number;
  worker_count: number;
}

export interface RenameGuildRequest {
  name: string;
}

export interface SetGuildLevelRequest {
  level: number;
}

export interface SetBaseRadiusRequest {
  radius: number;
}

export interface DeleteBaseRequest {
  delete_workers?: boolean;
}

export interface ContainerSummary {
  id: string;
  container_type: string;
  owner_player_uid: string | null;
  guild_id: string | null;
  guild_name: string | null;
  base_camp_id: string | null;
  slot_count: number;
  item_count: number;
  location: Vec3;
}

export interface ContainerListResponse {
  containers: ContainerSummary[];
  total: number;
  has_more: boolean;
}

export interface ContainerItemSlot {
  slot_index: number;
  count: number;
  static_id: string;
  dynamic_id: string | null;
  /** Decoded weapon/armor/egg payload — present only when dynamic_id resolves
   *  to a DynamicItemSaveData entry. Undefined for plain stackable items. */
  dynamic?: DynamicItemDetail;
}

/** Decoded payload of a DynamicItemSaveData entry (weapon/armor/egg).
 *  `type` discriminates which optional fields are meaningful. */
export interface DynamicItemDetail {
  local_id: string;
  static_id: string;
  type: 'weapon' | 'armor' | 'egg' | 'unknown';
  // Weapon + Armor:
  durability?: number | null;
  // Weapon only:
  remaining_bullets?: number | null;
  passive_skills?: string[];
  // Egg only:
  character_id?: string | null;
  egg_gender?: string | null;
  egg_passive_skills?: string[];
  egg_talent_hp?: number | null;
  egg_talent_shot?: number | null;
  egg_talent_defense?: number | null;
}

export interface ContainerDetail {
  id: string;
  owner_player_uid: string | null;
  guild_id: string | null;
  slot_count: number;
  item_count: number;
  items: ContainerItemSlot[];
}

export interface ExpandContainerRequest {
  new_slot_count: number;
}

/** Change one item slot's stack count (0 = clear the slot, keep the slot). */
export interface SetSlotCountRequest {
  slot_index: number;
  new_count: number;
}

/** One of the six player inventory bags. Slots live in a world-level
 *  ItemContainerSaveData entry; `container_id` is the link from the player's
 *  .sav InventoryInfo. `null` = bag not allocated for this player. */
export interface InventoryBag {
  bag_type: string;            // "common"|"essential"|"weapon"|"armor"|"food"|"drop"
  label: string;
  container_id: string | null;
  slot_count: number;
  item_count: number;
  items: ContainerItemSlot[];
}

/** A player's full inventory snapshot: bags + party/palbox ids + stats. */
export interface PlayerInventoryResponse {
  uid: string;
  name: string;
  bags: InventoryBag[];
  party_id: string | null;
  palbox_id: string | null;
  stats: PlayerStatsResponse | null;
}

/** A storage chest that belongs to a specific base camp. */
export interface BaseInventoryContainer {
  id: string;
  container_type: string;
  slot_count: number;
  item_count: number;
  items: ContainerItemSlot[];
  location: Vec3;
}

/** A base camp's inventory snapshot: its chests + its working pals. */
export interface BaseInventoryResponse {
  base_id: string;
  guild_name: string | null;
  containers: BaseInventoryContainer[];
  worker_container_id: string | null;
  workers: PalSummary[];
}

export interface PalSummary {
  instance_id: string;
  character_id: string;
  display_name: string | null;
  owner_uid: string | null;
  nickname: string | null;
  level: number;
  rank: number;
  gender: string;
  talent_hp: number;
  talent_shot: number;
  talent_defense: number;
  rank_hp: number;
  rank_attack: number;
  rank_defense: number;
  rank_craftspeed: number;
  passive_skills: string[];
  active_skills: string[];
  learned_skills: string[];
  is_illegal: boolean;
  // Container binding + icon join (present on grouped reads).
  container_id?: string | null;
  slot_index?: number;
  icon?: string | null;
  elements?: Record<string, { name: string; icon: string; icon_large?: string }>;
  is_boss?: boolean;
  is_lucky?: boolean;
  is_predator?: boolean;
  is_sick?: boolean;
}

export interface PalGroupedResponse {
  party_id: string | null;
  palbox_id: string | null;
  party: PalSummary[];
  palbox: PalSummary[];
  ungrouped: PalSummary[];
}

export interface PalListResponse {
  pals: PalSummary[];
  total: number;
}

// ---- pal editor: detail / mutation ----------------------------------------

export interface PalDetail {
  instance_id: string;
  character_id: string;
  display_name: string | null;
  icon: string | null;
  nickname: string | null;
  gender: string;
  level: number;
  exp: number;
  rank: number;
  talent_hp: number;
  talent_shot: number;
  talent_defense: number;
  rank_hp: number;
  rank_attack: number;
  rank_defense: number;
  rank_craftspeed: number;
  passive_skills: string[];
  active_skills: string[];
  learned_skills: string[];
  work_suitability: Record<string, number>;
  hp: number;
  max_hp: number;
  stomach: number;
  sanity: number;
  friendship_point: number;
  is_boss: boolean;
  is_lucky: boolean;
  is_predator: boolean;
  is_tower: boolean;
  is_sick: boolean;
  owner_uid: string | null;
  storage_id: string | null;
  storage_slot: number;
  boss_available: boolean;
}

export interface PalDetailResponse {
  pal: PalDetail;
}

export interface PalEditRequest {
  nickname?: string | null;
  character_id?: string | null;
  gender?: string | null;
  is_lucky?: boolean | null;
  is_boss?: boolean | null;
  level?: number | null;
  exp?: number | null;
  rank?: number | null;
  talent_hp?: number | null;
  talent_shot?: number | null;
  talent_defense?: number | null;
  rank_hp?: number | null;
  rank_attack?: number | null;
  rank_defense?: number | null;
  rank_craftspeed?: number | null;
  passive_skills?: string[] | null;
  active_skills?: string[] | null;
  learned_skills?: string[] | null;
  work_suitability?: Record<string, number> | null;
  friendship_point?: number | null;
  cheat_mode?: boolean;
}

export interface MovePalRequest {
  target_container_id: string;
  player_uid: string;
}

export interface SkillCatalogEntry {
  name: string;
  asset: string;
  icon?: string;
  rank?: number;
  element?: string;
  power?: number;
  description?: string;
  [key: string]: unknown;
}

export interface PalSkillCatalogResponse {
  passives: SkillCatalogEntry[];
  actives: SkillCatalogEntry[];
}

// ---- pal presets -----------------------------------------------------------

export interface PalPreset {
  id?: string | null;
  name: string;
  nickname?: string | null;
  character_id?: string | null;
  gender?: string | null;
  is_lucky?: boolean | null;
  is_boss?: boolean | null;
  level?: number | null;
  exp?: number | null;
  rank?: number | null;
  talent_hp?: number | null;
  talent_shot?: number | null;
  talent_defense?: number | null;
  rank_hp?: number | null;
  rank_attack?: number | null;
  rank_defense?: number | null;
  rank_craftspeed?: number | null;
  passive_skills?: string[] | null;
  active_skills?: string[] | null;
  learned_skills?: string[] | null;
  work_suitability?: Record<string, number> | null;
  friendship_point?: number | null;
}

export interface PresetListResponse {
  presets: PalPreset[];
}

export interface PresetSaveRequest {
  name: string;
  preset: PalPreset;
}

export interface PresetApplyRequest {
  instance_ids: string[];
  preset_id: string;
  cheat_mode?: boolean;
}

export interface PresetApplyResponse {
  applied: number;
  failed: string[];
  errors: Record<string, string>;
}

// ---- map -------------------------------------------------------------------

export type MapType = 'world' | 'tree';

export interface MapProjection {
  x: number;
  y: number;
  world_x: number;
  world_y: number;
}

export interface MapBase {
  id: string;
  guild_id: string | null;
  guild_name: string;
  guild_level: number;
  leader_name: string;
  member_count: number;
  total_bases: number;
  base_position: number;
  location: [number, number, number] | null;
  area_range: number;
  map_type: MapType;
  world_img: MapProjection | null;
  tree_img: MapProjection | null;
}

export interface MapPlayer {
  uid: string;
  name: string;
  level: number;
  guild_id: string | null;
  guild_name: string;
  last_seen_text: string | null;
  pal_count: number;
  location: [number, number, number] | null;
  map_type: MapType;
  world_img: MapProjection | null;
  tree_img: MapProjection | null;
}

export interface MapDataResponse {
  bases: MapBase[];
  players: MapPlayer[];
  map_size: number;
  world_coord_range: number;
  tree_coord_range: number;
}

// ---- tools ----------------------------------------------------------------

export interface ToolInfo {
  id: string;
  name: string;
  category: string;
  category_label: string;
  icon: string;
  description: string;
  windows_only: boolean;
}

export interface ToolsListResponse {
  tools: ToolInfo[];
}

export interface ConvertRequest {
  direction: string;
  input_path: string;
  output_path?: string;
}

export interface ConvertIdsRequest {
  input: string;
}

export interface ConvertIdsResponse {
  input: string;
  input_type: string;
  steam_id: string | null;
  palworld_uid: string | null;
  nosteam_uid: string | null;
}

export interface SlotInjectorRequest {
  level_sav_path?: string;
  players_folder?: string;
  new_slot_count: number;
  container_ids?: string[];
  use_loaded_save?: boolean;
}

export interface FixHostSaveRequest {
  level_sav_path?: string;
  old_uid: string;
  new_uid: string;
  guild_fix?: boolean;
  use_loaded_save?: boolean;
}

export interface FixGuildRequest {
  level_sav_path?: string;
  player_uid: string;
  target_guild_id: string;
  use_loaded_save?: boolean;
}

export interface CharacterTransferRequest {
  source_sav_path: string;
  target_sav_path: string;
  source_player_uid: string;
  target_player_uid?: string;
  steps?: Record<string, boolean>;
}

export interface PlayerMigrateRequest {
  source_sav_path: string;
  target_sav_path: string;
  source_player_uid: string;
  target_player_uid?: string;
}

export interface ConvertExportRequest {
  output_path?: string;
}

export interface ToolResponse {
  success: boolean;
  message: string;
  details: Record<string, unknown> | null;
}

// ---- breeding calculator ---------------------------------------------------
// Mirrors app/backend/schemas.py breeding models + src/palworld_aio/breeding.
// Keep both sides in sync.

export interface BreedablePal {
  tribe: string;
  display_name: string;
  icon: string | null;
  combi_rank: number;
  rarity: number;
  gender_prob: Record<string, number>;
}

export interface BreedablePalsResponse {
  pals: BreedablePal[];
  total: number;
}

export interface DirectChildRequest {
  parent_a: string;
  parent_b: string;
}

export interface DirectPartnersRequest {
  parent_a: string;
  target_child: string;
}

export interface DirectResultItem {
  parent_a: string;
  parent_b: string;
  child: string;
  child_display: string | null;
  child_icon: string | null;
  child_gender_prob: Record<string, number> | null;
  combo_type: 'formula' | 'unique';
}

export interface DirectChildResponse {
  result: DirectResultItem | null;
}

export interface DirectPartnersResponse {
  partners: DirectResultItem[];
}

export interface SelectedPal {
  species: string;
  gender?: string | null;
  passives?: string[];
}

export interface ChainRequest {
  target_pal: string;
  required_passives?: string[];
  target_gender?: string | null;
  max_generations?: number;
  mode: 'selection' | 'save';
  selected_pals?: SelectedPal[];
  owner_uid?: string | null;
  include_wild?: boolean;
  max_results?: number;
}

export interface BreedingStep {
  parent_a: string;
  parent_b: string;
  child: string;
  inherited_passives: string[];
  gender_feasible: boolean;
}

export interface ChainSource {
  type: 'owned' | 'selected' | 'wild';
  pal: string;
  display?: string;
  gender?: string;
  passives?: string[];
  nickname?: string;
  level?: number;
  instance_id?: string;
  [key: string]: unknown;
}

export interface Chain {
  target: string;
  generations: number;
  steps: BreedingStep[];
  final_passives: string[];
  sources: ChainSource[];
  gender_feasible: boolean;
  matched_passives: string[];
}

export interface ChainResponse {
  chains: Chain[];
  total: number;
  elapsed_ms: number;
  warnings: string[];
}

