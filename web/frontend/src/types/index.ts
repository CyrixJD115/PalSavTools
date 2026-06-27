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
  guild_id: string | null;
  guild_name: string | null;
  last_seen_seconds: number | null;
  last_seen_text: string | null;
}

export interface PlayerListResponse {
  players: PlayerSummary[];
  total: number;
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

export type Vec3 = [number, number, number] | null;

export interface BaseSummary {
  id: string;
  guild_id: string | null;
  guild_name: string | null;
  location: Vec3;
  worker_count: number;
}

export interface BaseListResponse {
  bases: BaseSummary[];
  total: number;
}

export interface ContainerSummary {
  id: string;
  owner_player_uid: string | null;
  guild_id: string | null;
  slot_count: number;
  item_count: number;
}

export interface ContainerListResponse {
  containers: ContainerSummary[];
  total: number;
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

