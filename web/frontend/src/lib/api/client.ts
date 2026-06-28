// Typed API client. Uses relative /api paths so it works both through the Vite
// dev proxy (:5173 -> :8000) and the production single-origin FastAPI serve.
import type {
  BaseDetail, BaseListResponse, ContainerDetail, ContainerListResponse,
  ConvertIdsRequest, ConvertIdsResponse, ConvertRequest, DeleteBaseRequest,
  ExpandContainerRequest, GuildDetail, GuildListResponse, HealthResponse,
  LanguagesResponse, LoadResponse, MapDataResponse, MaxAbilitiesRequest,
  PalListResponse, PlayerDetail, PlayerListResponse, RenameGuildRequest,
  RenamePlayerRequest, SaveStateResponse, SetBaseRadiusRequest,
  SetGuildLevelRequest, SetLeaderRequest, SetLevelRequest, SetStatsRequest,
  SetTechPointsRequest, SlotInjectorRequest, ToolResponse, ToolsListResponse,
} from '$types/index';

const API_BASE = '/api';

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, init);
  const text = await res.text();
  if (!res.ok) {
    let detail = text;
    try {
      const j = JSON.parse(text);
      detail = j.detail ?? text;
    } catch {
      /* keep raw text */
    }
    throw new Error(`API ${res.status}: ${detail}`);
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
  loadFromPath: (path: string) =>
    request<LoadResponse>('/save/load', jsonBody({ path })),
  unload: () => request<SaveStateResponse>('/save', { method: 'DELETE' }),

  uploadSave: async (file: File): Promise<LoadResponse> => {
    const form = new FormData();
    form.append('file', file);
    const res = await fetch(`${API_BASE}/save/upload`, { method: 'POST', body: form });
    const text = await res.text();
    if (!res.ok) {
      let detail = text;
      try { const j = JSON.parse(text); detail = j.detail ?? text; } catch { /* keep raw */ }
      throw new Error(`API ${res.status}: ${detail}`);
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

  players: () => request<PlayerListResponse>('/players'),

  playerDetail: (uid: string) => request<PlayerDetail>(`/players/${uid}`),
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
  resetPlayerTimestamp: (uid: string) =>
    request<{ status: string }>(`/players/${uid}/reset-timestamp`, { method: 'PUT' }),
  unlockViewingCage: (uid: string) =>
    request<{ status: string }>(`/players/${uid}/viewing-cage`, { method: 'PUT' }),
  unlockPlayerTechnologies: (uid: string) =>
    request<{ status: string }>(`/players/${uid}/unlock-technologies`, { method: 'PUT' }),
  maxPlayerAbilities: (body: MaxAbilitiesRequest) =>
    request<{ status: string }>('/players/max-abilities', jsonBody(body)),
  guilds: () => request<GuildListResponse>('/guilds'),
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
  bases: () => request<BaseListResponse>('/bases'),
  baseDetail: (id: string) => request<BaseDetail>(`/bases/${id}`),
  deleteBase: (id: string, body?: DeleteBaseRequest) =>
    request<{ status: string }>(`/bases/${id}`, jsonBody(body ?? {}, 'DELETE')),
  setBaseRadius: (id: string, body: SetBaseRadiusRequest) =>
    request<{ status: string }>(`/bases/${id}/radius`, jsonBody(body, 'PUT')),
  renameBaseGuild: (baseId: string, body: RenameGuildRequest) =>
    request<{ status: string }>(`/bases/${baseId}/guild/name`, jsonBody(body, 'PUT')),
  setBaseGuildLevel: (baseId: string, body: SetGuildLevelRequest) =>
    request<{ status: string }>(`/bases/${baseId}/guild/level`, jsonBody(body, 'PUT')),
  containers: (limit = 500) =>
    request<ContainerListResponse>(`/containers?limit=${limit}`),
  containerDetail: (id: string) => request<ContainerDetail>(`/containers/${id}`),
  clearContainer: (id: string) =>
    request<{ status: string }>(`/containers/${id}/clear`, { method: 'POST' }),
  expandContainer: (id: string, body: ExpandContainerRequest) =>
    request<{ status: string }>(`/containers/${id}/expand`, jsonBody(body, 'PUT')),
  pals: (limit = 300) => request<PalListResponse>(`/pals?limit=${limit}`),

  mapData: () => request<MapDataResponse>('/map/data'),

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
  toolFixHostSave: (params: Record<string, unknown>) =>
    request<ToolResponse>('/tools/fix-host-save', jsonBody(params)),
};
