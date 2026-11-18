import base64
from types import SimpleNamespace

import pytest
from deluge.error import AddTorrentError

from deluge_mobileui import write


class FakeTorrent:
    def __init__(self, state="Paused"):
        self.state = state
        self.files = [{"index": 0, "path": "a"}, {"index": 1, "path": "b"}]
        self.priorities = [4, 4]
        self.set_priorities_calls = []
        self.max_download_speed = -1
        self.max_upload_speed = -1
        self.set_speed_calls = []
        self.reannounce_result = True
        self.reannounced = 0
        self.recheck_result = True
        self.rechecked = 0
        self.move_result = True
        self.move_calls = []
        self.set_options_calls = []
        self.options = {
            "sequential_download": False,
            "prioritize_first_last_pieces": False,
            "auto_managed": True,
            "super_seeding": False,
            "stop_at_ratio": False,
            "stop_ratio": 1.0,
            "remove_at_ratio": False,
            "max_connections": -1,
            "max_upload_slots": -1,
        }

    def force_reannounce(self):
        self.reannounced += 1
        return self.reannounce_result

    def force_recheck(self):
        self.rechecked += 1
        return self.recheck_result

    def move_storage(self, dest):
        self.move_calls.append(dest)
        return self.move_result

    def get_files(self):
        return self.files

    def get_file_priorities(self):
        return list(self.priorities)

    def set_file_priorities(self, priorities):
        self.priorities = list(priorities)
        self.set_priorities_calls.append(list(priorities))

    def set_max_download_speed(self, value):
        self.max_download_speed = value
        self.set_speed_calls.append(("down", value))

    def set_max_upload_speed(self, value):
        self.max_upload_speed = value
        self.set_speed_calls.append(("up", value))

    def get_status(self, keys, update=False):
        return {
            "max_download_speed": self.max_download_speed,
            "max_upload_speed": self.max_upload_speed,
        }

    def get_options(self):
        return dict(self.options)

    def set_options(self, options):
        self.options.update(options)
        self.set_options_calls.append(dict(options))


class FakeCore:
    def __init__(self, torrents=None):
        self.torrentmanager = {
            torrent_id: FakeTorrent() for torrent_id in (torrents or ["abc"])
        }
        self.calls = []
        self.remove_result = True
        self.add_result = "newid"
        self.add_error = None
        self.paused = False
        self.session = SimpleNamespace(is_paused=lambda: self.paused)
        self.config = {
            "max_download_speed": -1.0,
            "max_upload_speed": -1.0,
            "max_active_downloading": 3,
            "max_active_seeding": 5,
            "max_active_limit": 8,
            "queue_new_to_top": False,
        }

    def set_config(self, updates):
        self.config.update(updates)
        self.calls.append(("config", dict(updates)))

    def get_config_values(self, keys):
        return {key: self.config.get(key) for key in keys}

    def pause_session(self):
        self.calls.append(("pause_session",))
        self.paused = True

    def resume_session(self):
        self.calls.append(("resume_session",))
        self.paused = False

    def pause_torrent(self, torrent_id):
        self.calls.append(("pause", torrent_id))

    def resume_torrent(self, torrent_id):
        self.calls.append(("resume", torrent_id))

    def remove_torrent(self, torrent_id, remove_data):
        self.calls.append(("remove", torrent_id, remove_data))
        return self.remove_result

    def queue_up(self, torrent_ids):
        self.calls.append(("queue_up", torrent_ids))

    def queue_down(self, torrent_ids):
        self.calls.append(("queue_down", torrent_ids))

    def queue_top(self, torrent_ids):
        self.calls.append(("queue_top", torrent_ids))

    def queue_bottom(self, torrent_ids):
        self.calls.append(("queue_bottom", torrent_ids))

    def add_torrent_magnet(self, uri, options):
        self.calls.append(("magnet", uri, options))
        if self.add_error:
            raise self.add_error
        return self.add_result

    def add_torrent_file(self, filename, filedump, options):
        self.calls.append(("file", filename, filedump, options))
        if self.add_error:
            raise self.add_error
        return self.add_result


class FakeLabel:
    def __init__(self):
        self.labels = {"movies": {}, "series": {}}
        self.torrent_labels = {}
        self.calls = []

    def set_torrent(self, torrent_id, label_id):
        self.calls.append((torrent_id, label_id))
        self.torrent_labels[torrent_id] = label_id

    def add(self, label_id):
        self.calls.append(("add", label_id))
        self.labels[label_id] = {}

    def remove(self, label_id):
        if label_id not in self.labels:
            raise Exception("Unknown Label")
        self.calls.append(("remove", label_id))
        del self.labels[label_id]


def test_pause_and_resume():
    core = FakeCore()

    assert write.pause(core, "abc") == {"id": "abc", "state": "Paused"}
    assert write.resume(core, "abc")["id"] == "abc"
    assert core.calls == [("pause", "abc"), ("resume", "abc")]


def test_pause_rejects_error_state():
    core = FakeCore()
    core.torrentmanager["abc"].state = "Error"

    with pytest.raises(write.Conflict):
        write.pause(core, "abc")


def test_remove_forwards_remove_data():
    core = FakeCore()

    result = write.remove(core, "abc", True)

    assert result == {"id": "abc", "removed": True, "remove_data": True}
    assert core.calls == [("remove", "abc", True)]


def test_remove_conflict_when_deluge_refuses():
    core = FakeCore()
    core.remove_result = False

    with pytest.raises(write.Conflict):
        write.remove(core, "abc")


@pytest.mark.parametrize(
    "action,method",
    [
        ("up", "queue_up"),
        ("down", "queue_down"),
        ("top", "queue_top"),
        ("bottom", "queue_bottom"),
    ],
)
def test_queue_actions(action, method):
    core = FakeCore()

    result = write.queue(core, "abc", action)

    assert result == {"id": "abc", "action": action}
    assert core.calls == [(method, ["abc"])]


def test_queue_rejects_unknown_action():
    core = FakeCore()

    with pytest.raises(write.BadRequest):
        write.queue(core, "abc", "sideways")


def test_set_label_validates_and_clears():
    core = FakeCore()
    labels = FakeLabel()

    assert write.set_label(core, labels, "abc", "movies")["label"] == "movies"
    cleared = write.set_label(core, labels, "abc", write.NO_LABEL)
    assert cleared["label"] == write.NO_LABEL
    assert labels.calls == [("abc", "movies"), ("abc", None)]


def test_set_label_rejects_unknown_label():
    core = FakeCore()
    labels = FakeLabel()

    with pytest.raises(write.BadRequest):
        write.set_label(core, labels, "abc", "nope")


def test_set_label_requires_the_plugin():
    core = FakeCore()

    with pytest.raises(write.Conflict):
        write.set_label(core, None, "abc", "movies")


def test_set_label_rejects_unknown_torrent():
    core = FakeCore()
    labels = FakeLabel()

    with pytest.raises(KeyError):
        write.set_label(core, labels, "missing", "movies")


def test_add_magnet_with_label_and_location():
    core = FakeCore()
    labels = FakeLabel()

    result = write.add(
        core,
        labels,
        magnet="magnet:?xt=urn:btih:abc",
        label="movies",
        download_location="/downloads",
        add_paused=True,
    )

    assert result == {
        "id": "newid",
        "label": "movies",
        "download_location": "/downloads",
    }
    assert core.calls == [
        (
            "magnet",
            "magnet:?xt=urn:btih:abc",
            {"download_location": "/downloads", "add_paused": True},
        )
    ]
    assert labels.calls == [("newid", "movies")]


def test_add_file_base64_encodes_dump():
    core = FakeCore()

    result = write.add(
        core,
        FakeLabel(),
        filename="x.torrent",
        filedump=b"torrent-bytes",
    )

    assert result["id"] == "newid"
    call = core.calls[0]
    assert call[0] == "file"
    assert call[1] == "x.torrent"
    assert base64.b64decode(call[2]) == b"torrent-bytes"
    assert call[3] == {}


def test_add_duplicate_is_conflict():
    core = FakeCore()
    labels = FakeLabel()
    core.add_error = AddTorrentError("Torrent already in session (abc).")

    with pytest.raises(write.Conflict):
        write.add(core, labels, magnet="magnet:?xt=urn:btih:abc")


def test_add_invalid_torrent_is_bad_request():
    core = FakeCore()
    labels = FakeLabel()
    core.add_error = AddTorrentError("Unable to add torrent, decoding filedump failed")

    with pytest.raises(write.BadRequest):
        write.add(core, labels, filedump=b"nope")


@pytest.mark.parametrize(
    "kwargs",
    [
        {},
        {"magnet": "magnet:?x", "filedump": b"x"},
        {"magnet": "http://example.com"},
        {"magnet": "magnet:?x", "download_location": "rel"},
        {"magnet": "magnet:?x", "add_paused": "yes"},
        {"magnet": "magnet:?x", "label": "nope"},
    ],
)
def test_add_validation(kwargs):
    core = FakeCore()
    labels = FakeLabel()

    with pytest.raises(write.BadRequest):
        write.add(core, labels, **kwargs)


def test_add_none_result_is_conflict():
    core = FakeCore()
    labels = FakeLabel()
    core.add_result = None

    with pytest.raises(write.Conflict):
        write.add(core, labels, magnet="magnet:?x")


def test_set_session_paused_toggles_the_whole_session():
    core = FakeCore()

    assert write.set_session_paused(core, True) == {"paused": True}
    assert core.calls[-1] == ("pause_session",)

    assert write.set_session_paused(core, False) == {"paused": False}
    assert core.calls[-1] == ("resume_session",)


def test_set_session_paused_falls_back_without_session_state():
    core = FakeCore()
    core.session = object()

    assert write.set_session_paused(core, True) == {"paused": True}
    assert write.set_session_paused(core, False) == {"paused": False}


def test_bulk_actions_collect_failures():
    core = FakeCore(["a", "b"])
    labels = FakeLabel()

    result = write.bulk(core, labels, ["a", "missing"], "pause")
    assert result == {
        "ok": 1,
        "failed": [{"id": "missing", "error": "unknown torrent"}],
    }
    assert core.calls == [("pause", "a")]

    result = write.bulk(core, labels, ["a", "b"], "label", label="movies")
    assert result["ok"] == 2
    assert labels.calls == [("a", "movies"), ("b", "movies")]


def test_bulk_rejects_bad_input():
    core = FakeCore()
    labels = FakeLabel()

    with pytest.raises(write.BadRequest):
        write.bulk(core, labels, [], "pause")
    with pytest.raises(write.BadRequest):
        write.bulk(core, labels, ["abc"], "queue")
    with pytest.raises(write.BadRequest):
        write.bulk(core, labels, ["abc"], "label", label="nope")
    with pytest.raises(write.Conflict):
        write.bulk(core, None, ["abc"], "label", label="movies")
    with pytest.raises(write.BadRequest):
        write.bulk(core, labels, ["abc"] * (write.MAX_BULK_IDS + 1), "pause")


def test_file_priorities_apply_a_change():
    core = FakeCore()
    torrent = core.torrentmanager["abc"]

    result = write.set_file_priorities(
        core, "abc", changes=[{"index": 1, "priority": 0}]
    )

    assert result == {"id": "abc", "priorities": [4, 0]}
    assert torrent.set_priorities_calls[-1] == [4, 0]


def test_file_priorities_only_selects_one():
    core = FakeCore()
    torrent = core.torrentmanager["abc"]

    result = write.set_file_priorities(core, "abc", only=0)

    assert result["priorities"] == [4, 0]
    assert torrent.set_priorities_calls[-1] == [4, 0]


def test_file_priorities_validate_input():
    core = FakeCore()
    torrent = core.torrentmanager["abc"]

    with pytest.raises(write.BadRequest):
        write.set_file_priorities(core, "abc", changes=[])
    with pytest.raises(write.BadRequest):
        write.set_file_priorities(core, "abc", changes=[{"index": 5, "priority": 4}])
    with pytest.raises(write.BadRequest):
        write.set_file_priorities(
            core, "abc", changes=[{"index": 0, "priority": 3}]
        )
    with pytest.raises(write.BadRequest):
        write.set_file_priorities(core, "abc", only=5)
    with pytest.raises(KeyError):
        write.set_file_priorities(core, "missing", only=0)

    torrent.files = []
    with pytest.raises(write.Conflict):
        write.set_file_priorities(core, "abc", only=0)


def test_session_limits_are_applied():
    core = FakeCore()

    result = write.set_session_limits(
        core, max_download_speed=512, max_upload_speed=128
    )

    assert result == {"max_download_speed": 512, "max_upload_speed": 128}
    assert core.config["max_download_speed"] == 512
    assert core.calls[-1] == (
        "config",
        {"max_download_speed": 512, "max_upload_speed": 128},
    )


def test_torrent_limits_are_applied():
    core = FakeCore()
    torrent = core.torrentmanager["abc"]

    result = write.set_torrent_limits(core, "abc", max_download_speed=0)

    assert result == {
        "id": "abc",
        "max_download_speed": 0,
        "max_upload_speed": -1,
    }
    assert torrent.set_speed_calls == [("down", 0)]


def test_torrent_options_roundtrip():
    core = FakeCore()

    result = write.get_torrent_options(core, "abc")

    assert result["id"] == "abc"
    assert set(result["options"]) == set(write.TORRENT_OPTION_KEYS)
    assert result["options"]["sequential_download"] is False

    updated = write.set_torrent_options(
        core,
        "abc",
        {
            "sequential_download": True,
            "stop_at_ratio": True,
            "stop_ratio": 2.5,
            "max_connections": 50,
        },
    )

    assert updated["options"]["sequential_download"] is True
    assert updated["options"]["stop_ratio"] == 2.5
    assert updated["options"]["max_connections"] == 50
    assert core.torrentmanager["abc"].set_options_calls == [
        {
            "sequential_download": True,
            "stop_at_ratio": True,
            "stop_ratio": 2.5,
            "max_connections": 50,
        }
    ]

    with pytest.raises(KeyError):
        write.get_torrent_options(core, "missing")
    with pytest.raises(KeyError):
        write.set_torrent_options(core, "missing", {"auto_managed": False})


def test_torrent_options_validate_input():
    core = FakeCore()

    with pytest.raises(write.BadRequest):
        write.set_torrent_options(core, "abc", {})
    with pytest.raises(write.BadRequest):
        write.set_torrent_options(core, "abc", {"unknown": True})
    with pytest.raises(write.BadRequest):
        write.set_torrent_options(core, "abc", {"auto_managed": 1})
    with pytest.raises(write.BadRequest):
        write.set_torrent_options(core, "abc", {"stop_ratio": 0.4})
    with pytest.raises(write.BadRequest):
        write.set_torrent_options(core, "abc", {"stop_ratio": 101})
    with pytest.raises(write.BadRequest):
        write.set_torrent_options(core, "abc", {"stop_ratio": True})
    with pytest.raises(write.BadRequest):
        write.set_torrent_options(core, "abc", {"max_connections": 9001})
    with pytest.raises(write.BadRequest):
        write.set_torrent_options(core, "abc", {"max_upload_slots": 1.5})


def test_session_queue_is_applied():
    core = FakeCore()

    result = write.set_session_queue(
        core,
        max_active_downloading=2,
        max_active_limit=-1,
        queue_new_to_top=True,
    )

    assert result == {
        "max_active_downloading": 2,
        "max_active_limit": -1,
        "queue_new_to_top": True,
    }
    assert core.config["max_active_seeding"] == 5
    assert core.calls[-1] == (
        "config",
        {
            "max_active_downloading": 2,
            "max_active_limit": -1,
            "queue_new_to_top": True,
        },
    )


def test_session_queue_validates_input():
    core = FakeCore()

    with pytest.raises(write.BadRequest):
        write.set_session_queue(core)
    with pytest.raises(write.BadRequest):
        write.set_session_queue(core, max_active_downloading=True)
    with pytest.raises(write.BadRequest):
        write.set_session_queue(core, max_active_downloading=2.5)
    with pytest.raises(write.BadRequest):
        write.set_session_queue(core, max_active_seeding=-2)
    with pytest.raises(write.BadRequest):
        write.set_session_queue(core, max_active_limit=10000)
    with pytest.raises(write.BadRequest):
        write.set_session_queue(core, max_active_limit="x")
    with pytest.raises(write.BadRequest):
        write.set_session_queue(core, queue_new_to_top="yes")


def test_limits_validate_input():
    core = FakeCore()

    with pytest.raises(write.BadRequest):
        write.set_session_limits(core)
    with pytest.raises(write.BadRequest):
        write.set_session_limits(core, max_download_speed=-2)
    with pytest.raises(write.BadRequest):
        write.set_session_limits(core, max_download_speed="x")
    with pytest.raises(write.BadRequest):
        write.set_torrent_limits(core, "abc")
    with pytest.raises(write.BadRequest):
        write.set_torrent_limits(core, "abc", max_upload_speed=-2)
    with pytest.raises(KeyError):
        write.set_torrent_limits(core, "missing", max_download_speed=0)


def test_label_add_and_remove():
    labels = FakeLabel()

    assert write.add_label(labels, " Movies ") == {"id": "movies"}
    assert labels.labels["movies"] == {}
    assert write.remove_label(labels, "movies") == {
        "id": "movies",
        "removed": True,
    }
    assert "movies" not in labels.labels

    with pytest.raises(write.BadRequest):
        write.add_label(labels, "")
    with pytest.raises(write.BadRequest):
        write.add_label(labels, 1)
    with pytest.raises(write.Conflict):
        write.add_label(None, "movies")
    with pytest.raises(write.BadRequest):
        write.remove_label(labels, "missing")


def test_reannounce():
    core = FakeCore()

    assert write.reannounce(core, "abc") == {"id": "abc", "reannounced": True}

    core.torrentmanager["abc"].reannounce_result = False
    assert write.reannounce(core, "abc")["reannounced"] is False

    with pytest.raises(KeyError):
        write.reannounce(core, "missing")


def test_recheck():
    core = FakeCore()

    assert write.recheck(core, "abc") == {"id": "abc", "rechecked": True}

    core.torrentmanager["abc"].recheck_result = False
    assert write.recheck(core, "abc")["rechecked"] is False

    with pytest.raises(KeyError):
        write.recheck(core, "missing")


def test_move_storage_delegates_to_torrent():
    core = FakeCore()
    torrent = core.torrentmanager["abc"]

    result = write.move_storage(core, "abc", "/data/new")

    assert result == {
        "id": "abc",
        "destination": "/data/new",
        "moving": True,
    }
    assert torrent.move_calls == ["/data/new"]


@pytest.mark.parametrize("location", [None, "", "relative/path"])
def test_move_storage_rejects_bad_location(location):
    core = FakeCore()

    with pytest.raises(write.BadRequest):
        write.move_storage(core, "abc", location)


def test_move_storage_rejects_a_moving_torrent():
    core = FakeCore()
    core.torrentmanager["abc"].state = "Moving"

    with pytest.raises(write.Conflict):
        write.move_storage(core, "abc", "/data/new")


def test_move_storage_reports_deluge_failure():
    core = FakeCore()
    core.torrentmanager["abc"].move_result = False

    with pytest.raises(write.Conflict):
        write.move_storage(core, "abc", "/data/new")


def test_move_storage_rejects_unknown_torrent():
    core = FakeCore()

    with pytest.raises(KeyError):
        write.move_storage(core, "missing", "/data/new")
