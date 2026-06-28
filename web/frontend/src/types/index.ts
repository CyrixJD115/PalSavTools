// TypeScript types mirroring web/backend/schemas.py. Single source of truth for
// the API contract; both sides must stay in sync.

export interface HealthResponse {
  status: string;
  version: string;
  app_version: string;
  game_version: string;
  save_loaded: boolean;
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
}

export interface PalListResponse {
  pals: PalSummary[];
  total: number;
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
  level_sav_path: string;
  players_folder?: string;
  new_slot_count: number;
  container_ids?: string[];
}

export interface ToolResponse {
  success: boolean;
  message: string;
  details: Record<string, unknown> | null;
}

