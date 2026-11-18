export interface Torrent {
  id: string;
  name: string;
  state: string;
  progress: number;
  label: string;
  download_payload_rate: number;
  upload_payload_rate: number;
  eta: number;
  ratio: number;
  total_size: number;
  save_path: string;
  time_added: number;
  message: string;
}

export interface TorrentList {
  total: number;
  offset: number;
  limit: number;
  torrents: Torrent[];
}

export interface LabelInfo {
  id: string;
  count: number;
}

export interface Labels {
  labels: LabelInfo[];
  no_label: number;
}

export interface Health {
  ok: boolean;
  version: string;
  port: number | null;
}

export interface QueueSettings {
  max_active_downloading: number;
  max_active_seeding: number;
  max_active_limit: number;
  queue_new_to_top: boolean;
}

export interface TorrentOptions {
  sequential_download: boolean;
  prioritize_first_last_pieces: boolean;
  auto_managed: boolean;
  super_seeding: boolean;
  stop_at_ratio: boolean;
  stop_ratio: number;
  remove_at_ratio: boolean;
  max_connections: number;
  max_upload_slots: number;
}

export interface DirEntry {
  name: string;
  path: string;
  writable: boolean;
}

export interface DirListing {
  path: string;
  parent: string | null;
  writable: boolean;
  dirs: DirEntry[];
  truncated: boolean;
}

export interface Session {
  download_rate: number;
  upload_rate: number;
  payload_download_rate: number;
  payload_upload_rate: number;
  num_torrents: number;
  paused: boolean;
  free_space: number | null;
  version: string;
  download_location: string;
  max_download_speed: number;
  max_upload_speed: number;
  queue: QueueSettings;
}

export interface LimitPayload {
  max_download_speed?: number;
  max_upload_speed?: number;
}

export interface LimitState {
  max_download_speed: number;
  max_upload_speed: number;
}

export interface TorrentTracker {
  url: string;
  tier?: number;
  verified?: boolean;
  message?: string;
  next_announce?: number;
}

export interface TorrentDetail extends Torrent {
  total_done: number;
  total_uploaded: number;
  total_payload_download: number;
  total_payload_upload: number;
  download_location: string;
  num_peers: number;
  num_seeds: number;
  total_peers: number;
  total_seeds: number;
  is_finished: boolean;
  is_seed: boolean;
  tracker: string;
  tracker_host: string;
  comment: string;
  creator: string;
  num_files: number;
  num_pieces: number;
  piece_length: number;
  private: boolean;
  queue: number;
  message: string;
  active_time: number;
  seeding_time: number;
  finished_time: number;
  max_download_speed: number;
  max_upload_speed: number;
  tracker_status: string;
  trackers: TorrentTracker[];
}

export interface TorrentFile {
  index: number;
  path: string;
  size: number;
  offset: number;
  progress: number;
  priority: number;
}

export interface FilePriorityPayload {
  files?: { index: number; priority: number }[];
  only?: number;
}

export interface FilePriorityResult {
  id: string;
  priorities: number[];
}

export interface TorrentFiles {
  total: number;
  offset: number;
  limit: number;
  files: TorrentFile[];
}

export interface TorrentEvent {
  type: "state" | "progress" | "added" | "removed" | "session";
  id: string | null;
  fields: Record<string, unknown>;
}

export interface TorrentFilters {
  q: string;
  state: string;
  label: string;
  sort: string;
}

export interface TorrentIds {
  ids: string[];
  total: number;
  limit: number;
}

export interface BulkResult {
  ok: number;
  failed: { id: string; error: string }[];
}

export interface BulkActionPayload {
  action: "pause" | "resume" | "remove" | "label";
  torrent_ids: string[];
  label?: string;
  remove_data?: boolean;
}

export type AuthMode = "token" | "password";

export interface AuthInfo {
  mode: string;
  modes: AuthMode[];
  token_set: boolean;
  authenticated?: boolean;
  username?: string;
  level?: number;
  write?: boolean;
}

export interface LoginResult {
  token: string;
  username: string;
  level: number;
  expires: number;
}

export interface GatePayload {
  mode: AuthMode;
  token?: string;
  username?: string;
  password?: string;
}
