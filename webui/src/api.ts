import type {
  AuthInfo,
  BulkActionPayload,
  BulkResult,
  FilePriorityPayload,
  FilePriorityResult,
  Health,
  Labels,
  LimitPayload,
  LimitState,
  LoginResult,
  QueueSettings,
  Session,
  Torrent,
  TorrentDetail,
  TorrentFiles,
  TorrentFilters,
  TorrentIds,
  TorrentList,
} from "./types";

const TOKEN_KEY = "mobileui.token";

export class ApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

export class UnauthorizedError extends ApiError {
  constructor() {
    super("Érvénytelen vagy lejárt token", 401);
  }
}

export class ForbiddenError extends ApiError {
  constructor(message = "Csak olvasható fiók") {
    super(message, 403);
  }
}

export function getToken(): string {
  return localStorage.getItem(TOKEN_KEY) ?? "";
}

export function setToken(token: string): void {
  if (token) {
    localStorage.setItem(TOKEN_KEY, token);
  } else {
    localStorage.removeItem(TOKEN_KEY);
  }
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers = new Headers(options.headers);
  headers.set("authorization", `Bearer ${getToken()}`);
  if (options.body && !headers.has("content-type")) {
    headers.set("content-type", "application/json");
  }

  const response = await fetch(path, { ...options, headers });
  const cachedRead =
    (!options.method || options.method === "GET") &&
    (path.startsWith("/api/torrents") ||
      path === "/api/session" ||
      path === "/api/labels");
  if (cachedRead) {
    const stale = response.headers.get("X-MobileUi-Stale") === "1";
    if (stale) window.dispatchEvent(new Event("mobileui:stale"));
    else if (response.ok) window.dispatchEvent(new Event("mobileui:fresh"));
  }
  if (response.status === 401) {
    throw new UnauthorizedError();
  }
  if (response.status === 403) {
    throw new ForbiddenError();
  }

  const text = await response.text();
  let payload: unknown = null;
  if (text) {
    try {
      payload = JSON.parse(text);
    } catch {
      payload = null;
    }
  }
  if (!response.ok) {
    const message =
      (payload as { message?: string } | null)?.message ??
      `API hiba (${response.status})`;
    throw new ApiError(message, response.status);
  }
  return payload as T;
}

export function getHealth(): Promise<Health> {
  return request<Health>("/health");
}

export function getAuthInfo(): Promise<AuthInfo> {
  return request<AuthInfo>("/api/auth");
}

export function login(username: string, password: string): Promise<LoginResult> {
  return request<LoginResult>("/api/login", {
    method: "POST",
    body: JSON.stringify({ username, password }),
  });
}

export async function logout(): Promise<{ ok: boolean; session: boolean }> {
  const result = await request<{ ok: boolean; session: boolean }>("/api/logout", {
    method: "POST",
  });
  navigator.serviceWorker?.controller?.postMessage({ type: "clear-api-cache" });
  return result;
}

export function getSession(): Promise<Session> {
  return request<Session>("/api/session");
}

export function pauseSession(): Promise<{ paused: boolean }> {
  return request("/api/session/pause", { method: "POST" });
}

export function resumeSession(): Promise<{ paused: boolean }> {
  return request("/api/session/resume", { method: "POST" });
}

export function setSessionLimits(payload: LimitPayload): Promise<LimitState> {
  return request<LimitState>("/api/session/limits", {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export function setSessionQueue(
  payload: Partial<QueueSettings>,
): Promise<Partial<QueueSettings>> {
  return request<Partial<QueueSettings>>("/api/session/queue", {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export function getLabels(): Promise<Labels> {
  return request<Labels>("/api/labels");
}

export function listTorrents(
  filters: TorrentFilters,
  offset: number,
  limit: number,
): Promise<TorrentList> {
  const params = new URLSearchParams({
    offset: String(offset),
    limit: String(limit),
    sort: filters.sort,
  });
  if (filters.q) params.set("q", filters.q);
  if (filters.state) params.set("state", filters.state);
  if (filters.label) params.set("label", filters.label);
  return request<TorrentList>(`/api/torrents?${params.toString()}`);
}

export function listTorrentIds(filters: TorrentFilters): Promise<TorrentIds> {
  const params = new URLSearchParams();
  if (filters.q) params.set("q", filters.q);
  if (filters.state) params.set("state", filters.state);
  if (filters.label) params.set("label", filters.label);
  const query = params.toString();
  const suffix = query ? `?${query}` : "";
  return request<TorrentIds>(`/api/torrents/ids${suffix}`);
}

export function bulkAction(payload: BulkActionPayload): Promise<BulkResult> {
  return request<BulkResult>("/api/torrents/bulk", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function getTorrent(id: string): Promise<TorrentDetail> {
  return request<TorrentDetail>(`/api/torrents/${encodeURIComponent(id)}`);
}

export function getTorrentFiles(
  id: string,
  offset: number,
  limit: number,
  q = "",
): Promise<TorrentFiles> {
  const params = new URLSearchParams({
    offset: String(offset),
    limit: String(limit),
  });
  if (q) params.set("q", q);
  return request<TorrentFiles>(
    `/api/torrents/${encodeURIComponent(id)}/files?${params.toString()}`,
  );
}

export function setFilePriorities(
  id: string,
  payload: FilePriorityPayload,
): Promise<FilePriorityResult> {
  return request<FilePriorityResult>(
    `/api/torrents/${encodeURIComponent(id)}/files`,
    { method: "PATCH", body: JSON.stringify(payload) },
  );
}

export function setTorrentLimits(
  id: string,
  payload: LimitPayload,
): Promise<LimitState & { id: string }> {
  return request<LimitState & { id: string }>(
    `/api/torrents/${encodeURIComponent(id)}/limits`,
    { method: "PATCH", body: JSON.stringify(payload) },
  );
}

export interface AddTorrentOptions {
  label?: string;
  download_location?: string;
  add_paused?: boolean;
}

export function addTorrentMagnet(
  magnet: string,
  options: AddTorrentOptions = {},
): Promise<{ id: string }> {
  return request("/api/torrents", {
    method: "POST",
    body: JSON.stringify({ magnet, ...options }),
  });
}

export function addTorrentFile(
  file: File,
  options: AddTorrentOptions = {},
): Promise<{ id: string }> {
  const params = new URLSearchParams({ filename: file.name });
  if (options.label) params.set("label", options.label);
  if (options.download_location) {
    params.set("download_location", options.download_location);
  }
  if (options.add_paused) params.set("add_paused", "true");
  return request(`/api/torrents?${params.toString()}`, {
    method: "POST",
    headers: { "content-type": "application/x-bittorrent" },
    body: file,
  });
}

export function pauseTorrent(id: string): Promise<{ state: string }> {
  return request(`/api/torrents/${encodeURIComponent(id)}/pause`, {
    method: "POST",
  });
}

export function resumeTorrent(id: string): Promise<{ state: string }> {
  return request(`/api/torrents/${encodeURIComponent(id)}/resume`, {
    method: "POST",
  });
}

export function removeTorrent(
  id: string,
  removeData: boolean,
): Promise<{ removed: boolean }> {
  return request(`/api/torrents/${encodeURIComponent(id)}/remove`, {
    method: "POST",
    body: JSON.stringify({ remove_data: removeData }),
  });
}

export function queueTorrent(
  id: string,
  action: string,
): Promise<{ action: string }> {
  return request(`/api/torrents/${encodeURIComponent(id)}/queue`, {
    method: "POST",
    body: JSON.stringify({ action }),
  });
}

export function setLabel(id: string, label: string): Promise<{ label: string }> {
  return request(`/api/torrents/${encodeURIComponent(id)}`, {
    method: "PATCH",
    body: JSON.stringify({ label }),
  });
}

export function addLabel(id: string): Promise<{ id: string }> {
  return request("/api/labels", {
    method: "POST",
    body: JSON.stringify({ id }),
  });
}

export function removeLabel(
  id: string,
): Promise<{ id: string; removed: boolean }> {
  return request(`/api/labels/${encodeURIComponent(id)}`, {
    method: "DELETE",
  });
}

export function reannounceTorrent(
  id: string,
): Promise<{ id: string; reannounced: boolean }> {
  return request(`/api/torrents/${encodeURIComponent(id)}/reannounce`, {
    method: "POST",
  });
}

export function recheckTorrent(
  id: string,
): Promise<{ id: string; rechecked: boolean }> {
  return request(`/api/torrents/${encodeURIComponent(id)}/recheck`, {
    method: "POST",
  });
}

export function moveTorrent(
  id: string,
  location: string,
): Promise<{ id: string; destination: string; moving: boolean }> {
  return request(`/api/torrents/${encodeURIComponent(id)}/move`, {
    method: "POST",
    body: JSON.stringify({ location }),
  });
}

export interface PushConfig {
  enabled: boolean;
  public_key: string;
  subscriptions: number;
}

export interface PushSubscriptionInfo {
  id: string;
  host: string;
  added: number | null;
  last_seen: number | null;
  user_agent: string;
}

export function getPushConfig(): Promise<PushConfig> {
  return request<PushConfig>("/api/push/config");
}

export function subscribePush(
  subscription: PushSubscriptionJSON,
): Promise<{ count: number }> {
  return request("/api/push/subscribe", {
    method: "POST",
    body: JSON.stringify(subscription),
  });
}

export function unsubscribePush(
  endpoint: string,
): Promise<{ unsubscribed: boolean }> {
  return request("/api/push/subscribe", {
    method: "DELETE",
    body: JSON.stringify({ endpoint }),
  });
}

export function testPush(endpoint: string): Promise<{ queued: boolean }> {
  return request("/api/push/test", {
    method: "POST",
    body: JSON.stringify({ endpoint }),
  });
}

export function getPushSubscriptions(): Promise<{
  subscriptions: PushSubscriptionInfo[];
}> {
  return request("/api/push/subscriptions");
}

export function removePushSubscription(
  id: string,
): Promise<{ unsubscribed: boolean }> {
  return request("/api/push/subscriptions", {
    method: "DELETE",
    body: JSON.stringify({ id }),
  });
}

export function eventsUrl(): string {
  return `/api/events?token=${encodeURIComponent(getToken())}`;
}

export function updateTorrent(row: Torrent, fields: Record<string, unknown>): void {
  if (typeof fields.state === "string") row.state = fields.state;
  if (typeof fields.progress === "number") row.progress = fields.progress;
  if (typeof fields.download_payload_rate === "number") {
    row.download_payload_rate = fields.download_payload_rate;
  }
  if (typeof fields.upload_payload_rate === "number") {
    row.upload_payload_rate = fields.upload_payload_rate;
  }
  if (typeof fields.eta === "number") row.eta = fields.eta;
  if (typeof fields.label === "string") row.label = fields.label;
}
