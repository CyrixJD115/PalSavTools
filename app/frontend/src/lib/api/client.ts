// Typed API client. Uses relative /api paths so it works both through the Vite
// dev proxy (:5173 -> :8000) and the production single-origin FastAPI serve.
import type {
  BaseDetail, BaseInventoryResponse, BaseListResponse, BreedablePalsResponse,
  CharacterTransferRequest, ChainRequest, ChainResponse, ContainerDetail,
  ContainerListResponse, ConvertExportRequest, ConvertIdsRequest,
  ConvertIdsResponse, ConvertRequest, DeleteBaseRequest, DirectChildRequest,
		  DirectChildResponse, DirectParentsRequest, DirectParentsResponse,
		  DirectPartnersRequest, DirectPartnersResponse,
  ExpandContainerRequest, FixGuildRequest, FixHostSaveRequest, GuildDetail,
  GuildListResponse, HealthResponse, LanguagesResponse, LoadOptions,
  LoadResponse, MapDataResponse, MapPoiResponse, MaxAbilitiesRequest, MovePalRequest,
  PalDetailResponse, PalEditRequest, PalGroupedResponse, PalListResponse,
  PalPreset, PalSkillCatalogResponse, PlayerAbilitiesResponse, PlayerDetail,
  PlayerInventoryResponse, PlayerListResponse, PlayerMigrateRequest,
  PlayerQuestsResponse, PlayerStatsResponse, PlayerTechPointsResponse,
  PlayerTechnologiesResponse, PresetApplyRequest, PresetApplyResponse,
  PresetListResponse, PresetSaveRequest, RenameGuildRequest,
  RenamePlayerRequest, SaveStateResponse, SetBaseRadiusRequest,
  SetGuildLevelRequest, SetLeaderRequest, SetLevelRequest,
  SetPlayerAbilitiesRequest, SetPlayerQuestsRequest, SetSlotCountRequest,
  SetStatsRequest, SetTechnologiesRequest, SetTechPointsRequest,
  SlotInjectorRequest, ToolResponse, ToolsListResponse,
  ProtectionState, EditLockRequest,
} from '$types/index';

const API_BASE = '/api';

/**
 * Extract a human-readable message from a backend error body.
 *
 * The backend uses several shapes:
 *  - `{"detail": "string"}`           — FastAPI HTTPException(str)
 *  - `{"detail": {obj}}`              — protection gate / structured errors
 *  - `{"detail": [{msg: "..."}]}`     — FastAPI validation errors
 *  - plain text                        — fallback
 *
 * Returns the most useful string we can find, never an object (avoids the
 * `[object Object]` toast bug).
 */
function extractDetail(text: string): string {
  try {
    const j = JSON.parse(text);
    const d = j?.detail;
    if (typeof d === 'string') return d;
    if (Array.isArray(d) && d.length) {
      // Pydantic v2 validation errors: [{msg: "...", ...}]
      const first = d[0];
      if (first?.msg) return String(first.msg);
      return JSON.stringify(d[0]) ?? text;
    }
    if (d && typeof d === 'object') {
      // Structured detail — protection gate returns {reason, target_type, ...}.
      // Build a readable sentence from the known keys; fall back to JSON.
      if (typeof d.reason === 'string') {
        if (d.reason === 'save_edit_locked') {
          return 'The save is edit-locked. Turn off the Edit Lock in the Protection tab to make changes.';
        }
        if (d.reason === 'rule_match') {
          const tgt = d.target_type ? `${d.target_type} ` : '';
          const id = d.target_id ? ` ${String(d.target_id).slice(0, 8)}` : '';
          const act = d.action ? d.action : 'modify';
          return `This ${tgt}${id ? id.trim() : ''}is protected from ${act}. Remove the rule in the Protection tab first.`;
        }
        return String(d.reason);
      }
      if (typeof d.message === 'string') return d.message;
      if (typeof d.error === 'string') return d.error;
      return JSON.stringify(d);
    }
    if (typeof j?.message === 'string') return j.message;
    return text;
  } catch {
    return text || 'Unknown error';
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, init);
  const text = await res.text();
  if (!res.ok) {
    throw new Error(`API ${res.status}: ${extractDetail(text)}`);
  }
  return text ? (JSON.parse(text) as T) : (undefined as unknown as T);
}

function jsonBody(body: unknown, method = 'POST'): RequestInit {
  return {
    method,
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  };
}

export const api = {
  health: () => request<HealthResponse>('/health'),

  languages: () => request<LanguagesResponse>('/data/languages'),
  i18n: (lang: string) =>
    request<{ lang: string; keys: Record<string, string> }>(`/data/i18n/${lang}`),

  saveState: () => request<SaveStateResponse>('/save/state'),
  loadFromPath: (path: string, opts?: LoadOptions) =>
    request<LoadResponse>('/save/load', jsonBody({
      path,
      storage_mode: opts?.storageMode ?? 'memory',
      prewarm: opts?.prewarm ?? false,
    })),
  unload: () => request<SaveStateResponse>('/save', { method: 'DELETE' }),

  uploadSave: async (file: File, opts?: LoadOptions): Promise<LoadResponse> => {
    const form = new FormData();
    form.append('file', file);
    // storage_mode / prewarm travel as multipart form fields alongside file.
    form.append('storage_mode', opts?.storageMode ?? 'memory');
    form.append('prewarm', String(opts?.prewarm ?? false));
    const res = await fetch(`${API_BASE}/save/upload`, { method: 'POST', body: form });
    const text = await res.text();
    if (!res.ok) {
      throw new Error(`API ${res.status}: ${extractDetail(text)}`);
    }
    return JSON.parse(text) as LoadResponse;
  },

  exportSave: async (): Promise<{ blob: Blob; filename: string; size: number }> => {
    const res = await fetch(`${API_BASE}/save/export`, { method: 'POST' });
    if (!res.ok) {
      const text = await res.text();
      throw new Error(`Export failed: ${text}`);
    }
    const dispo = res.headers.get('Content-Disposition') ?? '';
    const match = dispo.match(/filename="?([^"]+)"?/);
    const filename = match ? match[1] : 'Level.sav';
    const blob = await res.blob();
    return { blob, filename, size: Number(res.headers.get('X-Export-Size') ?? blob.size) };
  },

  persistSave: () =>
    request<{ status: string; backup_path: string | null }>('/save/persist', { method: 'POST' }),

  players: (opts: { limit?: number; offset?: number; search?: string } = {}) => {
    const params = new URLSearchParams();
    if (opts.limit != null) params.set('limit', String(opts.limit));
    if (opts.offset != null) params.set('offset', String(opts.offset));
    if (opts.search) params.set('search', opts.search);
    const qs = params.toString();
    return request<PlayerListResponse>(`/players${qs ? `?${qs}` : ''}`);
  },

  playerDetail: (uid: string) => request<PlayerDetail>(`/players/${uid}`),
  playerInventory: (uid: string) =>
    request<PlayerInventoryResponse>(`/players/${uid}/inventory`),
  playerStats: (uid: string) =>
    request<PlayerStatsResponse>(`/players/${uid}/stats`),
  playerTechPoints: (uid: string) =>
    request<PlayerTechPointsResponse>(`/players/${uid}/tech-points`),
  renamePlayer: (uid: string, body: RenamePlayerRequest) =>
    request<{ status: string }>(`/players/${uid}/name`, jsonBody(body, 'PUT')),
  deletePlayer: (uid: string) =>
    request<{ status: string }>(`/players/${uid}`, { method: 'DELETE' }),
  setPlayerLevel: (uid: string, body: SetLevelRequest) =>
    request<{ status: string }>(`/players/${uid}/level`, jsonBody(body, 'PUT')),
  setPlayerTechPoints: (uid: string, body: SetTechPointsRequest) =>
    request<{ status: string }>(`/players/${uid}/tech-points`, jsonBody(body, 'PUT')),
  setPlayerStats: (uid: string, body: SetStatsRequest) =>
    request<{ status: string }>(`/players/${uid}/stats`, jsonBody(body, 'PUT')),
  maxPlayerStats: (uid: string) =>
    request<{ status: string }>(`/players/${uid}/stats/max`, { method: 'POST' }),
  resetPlayerStats: (uid: string) =>
    request<{ status: string }>(`/players/${uid}/stats/reset`, { method: 'POST' }),
  playerTechnologies: (uid: string) =>
    request<PlayerTechnologiesResponse>(`/players/${uid}/technologies`),
  setPlayerTechnologies: (uid: string, body: SetTechnologiesRequest) =>
    request<{ status: string }>(`/players/${uid}/technologies`, jsonBody(body, 'PUT')),
  resetPlayerTimestamp: (uid: string) =>
    request<{ status: string }>(`/players/${uid}/reset-timestamp`, { method: 'PUT' }),
  unlockViewingCage: (uid: string) =>
    request<{ status: string }>(`/players/${uid}/viewing-cage`, { method: 'PUT' }),
  unlockPlayerTechnologies: (uid: string) =>
    request<{ status: string }>(`/players/${uid}/unlock-technologies`, { method: 'PUT' }),
  maxPlayerAbilities: (body: MaxAbilitiesRequest) =>
    request<{ status: string }>('/players/max-abilities', jsonBody(body)),
  playerQuests: (uid: string) =>
    request<PlayerQuestsResponse>(`/players/${uid}/quests`),
  setPlayerQuests: (uid: string, body: SetPlayerQuestsRequest) =>
    request<{ status: string }>(`/players/${uid}/quests`, jsonBody(body, 'PUT')),
  playerAbilities: (uid: string) =>
    request<PlayerAbilitiesResponse>(`/players/${uid}/abilities`),
  setPlayerAbilities: (uid: string, body: SetPlayerAbilitiesRequest) =>
    request<{ status: string }>(`/players/${uid}/abilities`, jsonBody(body, 'PUT')),
  guilds: (opts: { limit?: number; offset?: number; search?: string } = {}) => {
    const params = new URLSearchParams();
    if (opts.limit != null) params.set('limit', String(opts.limit));
    if (opts.offset != null) params.set('offset', String(opts.offset));
    if (opts.search) params.set('search', opts.search);
    const qs = params.toString();
    return request<GuildListResponse>(`/guilds${qs ? `?${qs}` : ''}`);
  },
  guildDetail: (id: string) => request<GuildDetail>(`/guilds/${id}`),
  renameGuild: (gid: string, body: RenameGuildRequest) =>
    request<{ status: string }>(`/guilds/${gid}/name`, jsonBody(body, 'PUT')),
  setGuildLevel: (gid: string, body: SetGuildLevelRequest) =>
    request<{ status: string }>(`/guilds/${gid}/level`, jsonBody(body, 'PUT')),
  setGuildLeader: (gid: string, body: SetLeaderRequest) =>
    request<{ status: string }>(`/guilds/${gid}/leader`, jsonBody(body, 'PUT')),
  removeGuildMember: (gid: string, uid: string) =>
    request<{ status: string }>(`/guilds/${gid}/members/${uid}`, { method: 'DELETE' }),
  deleteGuild: (gid: string) =>
    request<{ status: string }>(`/guilds/${gid}`, { method: 'DELETE' }),
  bases: (opts: { limit?: number; offset?: number; search?: string } = {}) => {
    const params = new URLSearchParams();
    if (opts.limit != null) params.set('limit', String(opts.limit));
    if (opts.offset != null) params.set('offset', String(opts.offset));
    if (opts.search) params.set('search', opts.search);
    const qs = params.toString();
    return request<BaseListResponse>(`/bases${qs ? `?${qs}` : ''}`);
  },
  baseDetail: (id: string) => request<BaseDetail>(`/bases/${id}`),
  baseInventory: (id: string) =>
    request<BaseInventoryResponse>(`/bases/${id}/inventory`),
  deleteBase: (id: string, body?: DeleteBaseRequest) =>
    request<{ status: string }>(`/bases/${id}`, jsonBody(body ?? {}, 'DELETE')),
  setBaseRadius: (id: string, body: SetBaseRadiusRequest) =>
    request<{ status: string }>(`/bases/${id}/radius`, jsonBody(body, 'PUT')),
  renameBaseGuild: (baseId: string, body: RenameGuildRequest) =>
    request<{ status: string }>(`/bases/${baseId}/guild/name`, jsonBody(body, 'PUT')),
  setBaseGuildLevel: (baseId: string, body: SetGuildLevelRequest) =>
    request<{ status: string }>(`/bases/${baseId}/guild/level`, jsonBody(body, 'PUT')),
  containers: (offset = 0, limit = 1000) =>
    request<ContainerListResponse>(`/containers?offset=${offset}&limit=${limit}`),
  containerDetail: (id: string) => request<ContainerDetail>(`/containers/${id}`),
  clearContainer: (id: string) =>
    request<{ status: string }>(`/containers/${id}/clear`, { method: 'POST' }),
  expandContainer: (id: string, body: ExpandContainerRequest) =>
    request<{ status: string }>(`/containers/${id}/expand`, jsonBody(body, 'PUT')),
  /** Change one item slot's stack count (0 = clear the slot, keep the slot). */
  setSlotCount: (id: string, body: SetSlotCountRequest) =>
    request<{ status: string }>(`/containers/${id}/slots`, jsonBody(body, 'PUT')),
  /** Remove the item from a slot (zero it out, keep the slot itself). */
  deleteSlot: (id: string, slotIndex: number) =>
    request<{ status: string }>(`/containers/${id}/slots/${slotIndex}`, { method: 'DELETE' }),
  pals: (opts: { limit?: number; offset?: number; search?: string } = {}) => {
    const params = new URLSearchParams();
    if (opts.limit != null) params.set('limit', String(opts.limit));
    if (opts.offset != null) params.set('offset', String(opts.offset));
    if (opts.search) params.set('search', opts.search);
    const qs = params.toString();
    return request<PalListResponse>(`/pals${qs ? `?${qs}` : ''}`);
  },
  palGrouped: (ownerUid: string) =>
    request<PalGroupedResponse>(`/pals/grouped?owner_uid=${encodeURIComponent(ownerUid)}`),

  // ---- pal editor ----
  palDetail: (instanceId: string) =>
    request<PalDetailResponse>(`/pals/${encodeURIComponent(instanceId)}`),
  editPal: (instanceId: string, body: PalEditRequest) =>
    request<PalDetailResponse>(`/pals/${encodeURIComponent(instanceId)}`, jsonBody(body, 'PUT')),
  maxOutPal: (instanceId: string, cheatMode = false) =>
    request<PalDetailResponse>(`/pals/${encodeURIComponent(instanceId)}/max-out`, jsonBody({ cheat_mode: cheatMode })),
  healPal: (instanceId: string) =>
    request<PalDetailResponse>(`/pals/${encodeURIComponent(instanceId)}/heal`, jsonBody({}, 'POST')),
  learnAllPal: (instanceId: string, cheatMode = false) =>
    request<PalDetailResponse>(`/pals/${encodeURIComponent(instanceId)}/learn-all`, jsonBody({ cheat_mode: cheatMode })),
  movePal: (instanceId: string, body: MovePalRequest) =>
    request<PalDetailResponse>(`/pals/${encodeURIComponent(instanceId)}/move`, jsonBody(body)),
  swapPals: (palA: string, palB: string) =>
    request<{ status: string; pal_a: string; pal_b: string }>('/pals/swap', jsonBody({ pal_a: palA, pal_b: palB })),
  deletePal: (instanceId: string) =>
    request<{ status: string }>(`/pals/${encodeURIComponent(instanceId)}`, { method: 'DELETE' }),
  palSkillCatalog: () =>
    request<PalSkillCatalogResponse>('/pals/catalog/skills'),
  applyPreset: (body: PresetApplyRequest) =>
    request<PresetApplyResponse>('/pals/apply-preset', jsonBody(body)),

  // ---- pal presets ----
  listPresets: () => request<PresetListResponse>('/presets'),
  savePreset: (body: PresetSaveRequest) =>
    request<PalPreset>('/presets', jsonBody(body)),
  deletePreset: (id: string) =>
    request<{ status: string }>(`/presets/${encodeURIComponent(id)}`, { method: 'DELETE' }),

  mapData: () => request<MapDataResponse>('/map/data'),
  mapPois: () => request<MapPoiResponse>('/map/pois'),

  // ---- tools ----
  tools: () => request<ToolsListResponse>('/tools'),
  toolConvert: (params: ConvertRequest) =>
    request<ToolResponse>('/tools/convert', jsonBody(params)),
  toolConvertIds: (params: ConvertIdsRequest) =>
    request<ConvertIdsResponse>('/tools/convert-ids', jsonBody(params)),
  toolRestoreMap: (params: { path: string }) =>
    request<ToolResponse>('/tools/restore-map', jsonBody(params)),
  toolSlotInject: (params: SlotInjectorRequest) =>
    request<ToolResponse>('/tools/slot-injector', jsonBody(params)),
  toolFixHostSave: (params: FixHostSaveRequest) =>
    request<ToolResponse>('/tools/fix-host-save', jsonBody(params)),
  toolFixGuild: (params: FixGuildRequest) =>
    request<ToolResponse>('/tools/fix-guild', jsonBody(params)),
  toolCharacterTransfer: (params: CharacterTransferRequest) =>
    request<ToolResponse>('/tools/character-transfer', jsonBody(params)),
  toolPlayerMigrate: (params: PlayerMigrateRequest) =>
    request<ToolResponse>('/tools/player-migrate', jsonBody(params)),
  toolConvertExport: (params: ConvertExportRequest) =>
    request<ToolResponse>('/tools/convert-export', jsonBody(params)),

  // ---- breeding calculator ----
  breedingPals: () => request<BreedablePalsResponse>('/breeding/pals'),
  breedingDirectChild: (params: DirectChildRequest) =>
    request<DirectChildResponse>('/breeding/direct/child', jsonBody(params)),
  breedingDirectPartners: (params: DirectPartnersRequest) =>
    request<DirectPartnersResponse>('/breeding/direct/partners', jsonBody(params)),
  breedingDirectParents: (params: DirectParentsRequest) =>
    request<DirectParentsResponse>('/breeding/direct/parents', jsonBody(params)),
  breedingChain: (params: ChainRequest) =>
    request<ChainResponse>('/breeding/chain', jsonBody(params)),

  // ---- protection & locking ----
  getProtection: () => request<ProtectionState>('/protection'),
  putProtectionState: (state: ProtectionState) =>
    request<ProtectionState>('/protection/state', jsonBody(state, 'PUT')),
  putEditLock: (body: EditLockRequest) =>
    request<ProtectionState>('/protection/lock', jsonBody(body, 'PUT')),
};
