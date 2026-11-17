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

export interface Session {
  download_rate: number;
  upload_rate: number;
  payload_download_rate: number;
  payload_upload_rate: number;
  num_torrents: number;
  paused: boolean;
  version: string;
  queue: Record<string, unknown>;
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
