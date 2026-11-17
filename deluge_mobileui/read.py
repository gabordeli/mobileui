"""Read-side helpers: torrent list/detail/session/labels.

Runs in the deluged reactor, so it reads the cached torrent status instead of
calling ``core.get_torrents_status`` (which may wait for a libtorrent update
alert under load).
"""

from collections import Counter

NO_LABEL = "No Label"

LIST_KEYS = [
    "name",
    "state",
    "progress",
    "download_payload_rate",
    "upload_payload_rate",
    "eta",
    "ratio",
    "total_size",
    "save_path",
]

DETAIL_KEYS = [
    "name",
    "state",
    "progress",
    "download_payload_rate",
    "upload_payload_rate",
    "eta",
    "ratio",
    "total_size",
    "total_done",
    "total_uploaded",
    "total_payload_download",
    "total_payload_upload",
    "save_path",
    "download_location",
    "num_peers",
    "num_seeds",
    "total_peers",
    "total_seeds",
    "is_finished",
    "is_seed",
    "time_added",
    "tracker",
    "tracker_host",
    "tracker_status",
    "trackers",
    "comment",
    "creator",
    "num_files",
    "num_pieces",
    "piece_length",
    "private",
    "queue",
    "message",
    "active_time",
    "seeding_time",
    "finished_time",
    "max_download_speed",
    "max_upload_speed",
]

SORT_FIELDS = {
    "name",
    "state",
    "progress",
    "download_payload_rate",
    "upload_payload_rate",
    "eta",
    "ratio",
    "total_size",
    "label",
}

SESSION_KEYS = [
    "download_rate",
    "upload_rate",
    "payload_download_rate",
    "payload_upload_rate",
    "num_connections",
]

QUEUE_KEYS = [
    "max_active_downloading",
    "max_active_seeding",
    "max_active_limit",
    "queue_new_to_top",
]

SPEED_KEYS = ["max_download_speed", "max_upload_speed"]

MAX_LIMIT = 200
DEFAULT_LIMIT = 50
MAX_FILES_LIMIT = 500
DEFAULT_FILES_LIMIT = 100
MAX_BULK_IDS = 1000


def _label_plugin_labels(label_plugin):
    if label_plugin is None:
        return {}
    return getattr(label_plugin, "torrent_labels", {}) or {}


def _sort_value(row, field):
    if field in {"name", "label"}:
        return str(row[field]).casefold()
    value = row[field]
    if field == "eta" and (value is None or value < 0):
        return float("inf")
    return value


def _matching_rows(core, label_plugin, state=None, label=None, q=None):
    label_map = _label_plugin_labels(label_plugin)
    needle = q.casefold() if q else None

    rows = []
    for torrent_id, torrent in core.torrentmanager.torrents.items():
        try:
            row = torrent.get_status(LIST_KEYS, update=False)
        except KeyError:
            continue
        row["id"] = torrent_id
        row["label"] = label_map.get(torrent_id, NO_LABEL)
        if state and state != "All" and row["state"] != state:
            continue
        if label and row["label"] != label:
            continue
        if needle and needle not in row["name"].casefold():
            continue
        rows.append(row)
    return rows


def list_torrents(
    core,
    label_plugin,
    state=None,
    label=None,
    q=None,
    sort="name",
    offset=0,
    limit=DEFAULT_LIMIT,
):
    offset = int(offset)
    limit = int(limit)
    if offset < 0:
        raise ValueError("offset must be >= 0")
    if not 1 <= limit <= MAX_LIMIT:
        raise ValueError(f"limit must be between 1 and {MAX_LIMIT}")

    sort_field = sort[1:] if sort.startswith("-") else sort
    if sort_field not in SORT_FIELDS:
        raise ValueError(f"unknown sort field: {sort}")
    descending = sort.startswith("-")

    rows = _matching_rows(core, label_plugin, state, label, q)
    rows.sort(
        key=lambda row: (_sort_value(row, sort_field), row["name"].casefold()),
        reverse=descending,
    )
    total = len(rows)
    page = rows[offset : offset + limit]
    return {
        "total": total,
        "offset": offset,
        "limit": limit,
        "torrents": page,
    }


def matching_ids(
    core, label_plugin, state=None, label=None, q=None, limit=MAX_BULK_IDS
):
    rows = _matching_rows(core, label_plugin, state, label, q)
    return {
        "ids": [row["id"] for row in rows[:limit]],
        "total": len(rows),
        "limit": limit,
    }


def _text(value):
    if isinstance(value, bytes):
        return value.decode("utf-8", "replace")
    return value


def _tracker_row(entry):
    return {key: _text(value) for key, value in entry.items()}


def get_torrent(core, label_plugin, torrent_id):
    torrent = core.torrentmanager.torrents[torrent_id]
    status = torrent.get_status(DETAIL_KEYS, update=True)
    status["id"] = torrent_id
    status["label"] = _label_plugin_labels(label_plugin).get(torrent_id, NO_LABEL)
    status["trackers"] = [
        _tracker_row(entry) for entry in (status.get("trackers") or [])
    ]
    for key in ("tracker", "tracker_host", "tracker_status"):
        if key in status:
            status[key] = _text(status[key])
    return status


def get_files(core, torrent_id, offset=0, limit=100):
    offset = int(offset)
    limit = int(limit)
    if offset < 0:
        raise ValueError("offset must be >= 0")
    if not 1 <= limit <= MAX_FILES_LIMIT:
        raise ValueError(f"limit must be between 1 and {MAX_FILES_LIMIT}")

    torrent = core.torrentmanager.torrents[torrent_id]
    files = torrent.get_files()
    progress = torrent.get_file_progress()
    priorities = torrent.get_file_priorities()
    rows = []
    for index, entry in enumerate(files):
        row = dict(entry)
        row["progress"] = progress[index] if index < len(progress) else 0.0
        row["priority"] = priorities[index] if index < len(priorities) else 4
        rows.append(row)
    total = len(rows)
    return {
        "total": total,
        "offset": offset,
        "limit": limit,
        "files": rows[offset : offset + limit],
    }


def get_session(core):
    status = core.get_session_status(SESSION_KEYS)
    config = core.get_config_values(
        [*QUEUE_KEYS, "download_location", *SPEED_KEYS]
    )
    status["queue"] = {key: config[key] for key in QUEUE_KEYS}
    status["download_location"] = config["download_location"]
    for key in SPEED_KEYS:
        status[key] = config[key]
    status["num_torrents"] = len(core.torrentmanager.torrents)
    status["version"] = _deluge_version()
    try:
        status["paused"] = bool(core.session.is_paused())
    except (AttributeError, KeyError):
        pass
    try:
        free_space = int(core.get_free_space(config["download_location"]))
        status["free_space"] = free_space if free_space >= 0 else None
    except (AttributeError, KeyError, OSError, TypeError, ValueError):
        status["free_space"] = None
    return status


def get_labels(label_plugin, core):
    labels = label_plugin.get_labels() if label_plugin is not None else []
    label_map = _label_plugin_labels(label_plugin)
    counts = Counter(
        label_map.get(torrent_id, NO_LABEL)
        for torrent_id in core.torrentmanager.torrents
    )
    return {
        "labels": [{"id": label, "count": counts.get(label, 0)} for label in labels],
        "no_label": counts.get(NO_LABEL, 0),
    }


def _deluge_version():
    try:
        from deluge.common import get_version

        return get_version()
    except Exception:
        return ""
