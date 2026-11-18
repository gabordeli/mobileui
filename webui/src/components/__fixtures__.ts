import type { LabelInfo, Torrent, TorrentDetail, TorrentFile } from "../types";

export const labels: LabelInfo[] = [{ id: "film", count: 2 }];

export const torrent: Torrent = {
  id: "demo-movie",
  name: "Demo Movie 2024",
  state: "Downloading",
  progress: 42.5,
  label: "film",
  download_payload_rate: 1024 * 1024,
  upload_payload_rate: 2048,
  eta: 3600,
  ratio: 0.5,
  total_size: 734003200,
  save_path: "/data/downloads",
  time_added: 1763380000,
  message: "OK",
};

export const detail: TorrentDetail = {
  ...torrent,
  total_done: 311951360,
  total_uploaded: 1048576,
  total_payload_download: 311951360,
  total_payload_upload: 1048576,
  download_location: "/data/downloads",
  num_peers: 3,
  num_seeds: 2,
  total_peers: 10,
  total_seeds: 5,
  is_finished: false,
  is_seed: false,
  tracker: "https://tracker.example/announce",
  tracker_host: "tracker.example",
  comment: "",
  creator: "",
  num_files: 2,
  num_pieces: 0,
  piece_length: 0,
  private: false,
  queue: 1,
  message: "OK",
  active_time: 60,
  seeding_time: 0,
  finished_time: 0,
  max_download_speed: -1,
  max_upload_speed: -1,
  tracker_status: "OK",
  trackers: [
    {
      url: "https://tracker.example/announce",
      tier: 0,
      verified: true,
      message: "OK",
    },
  ],
};

export const files: TorrentFile[] = [
  { index: 0, path: "demo-movie.mkv", size: 733000000, offset: 0, progress: 0.42, priority: 4 },
  { index: 1, path: "demo-movie.srt", size: 1003200, offset: 0, progress: 1, priority: 4 },
];
