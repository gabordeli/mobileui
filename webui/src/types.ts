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

export interface Session {
  download_rate: number;
  upload_rate: number;
  payload_download_rate: number;
  payload_upload_rate: number;
  num_torrents: number;
  paused: boolean;
  version: string;
  download_location: string;
  queue: Record<string, unknown>;
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
  time_added: number;
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
}

export interface TorrentFile {
  index: number;
  path: string;
  size: number;
  offset: number;
  progress: number;
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

export interface ActionPayload {
  kind: "pause" | "resume" | "queue" | "label" | "remove";
  action?: string;
  label?: string;
  remove_data?: boolean;
}
