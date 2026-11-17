import base64

import pytest
from deluge.error import AddTorrentError

from deluge_mobileui import write


class FakeTorrent:
    def __init__(self, state="Paused"):
        self.state = state


class FakeCore:
    def __init__(self, torrents=None):
        self.torrentmanager = {
            torrent_id: FakeTorrent() for torrent_id in (torrents or ["abc"])
        }
        self.calls = []
        self.remove_result = True
        self.add_result = "newid"
        self.add_error = None

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
    with pytest.raises(write.BadRequest):
        write.queue(FakeCore(), "abc", "sideways")


def test_set_label_validates_and_clears():
    core = FakeCore()
    labels = FakeLabel()

    assert write.set_label(core, labels, "abc", "movies")["label"] == "movies"
    cleared = write.set_label(core, labels, "abc", write.NO_LABEL)
    assert cleared["label"] == write.NO_LABEL
    assert labels.calls == [("abc", "movies"), ("abc", None)]


def test_set_label_errors():
    core = FakeCore()

    with pytest.raises(write.BadRequest):
        write.set_label(core, FakeLabel(), "abc", "nope")
    with pytest.raises(write.Conflict):
        write.set_label(core, None, "abc", "movies")
    with pytest.raises(KeyError):
        write.set_label(core, FakeLabel(), "missing", "movies")


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
    core.add_error = AddTorrentError("Torrent already in session (abc).")

    with pytest.raises(write.Conflict):
        write.add(core, FakeLabel(), magnet="magnet:?xt=urn:btih:abc")


def test_add_invalid_torrent_is_bad_request():
    core = FakeCore()
    core.add_error = AddTorrentError("Unable to add torrent, decoding filedump failed")

    with pytest.raises(write.BadRequest):
        write.add(core, FakeLabel(), filedump=b"nope")


def test_add_validation():
    with pytest.raises(write.BadRequest):
        write.add(FakeCore(), FakeLabel())
    with pytest.raises(write.BadRequest):
        write.add(FakeCore(), FakeLabel(), magnet="magnet:?x", filedump=b"x")
    with pytest.raises(write.BadRequest):
        write.add(FakeCore(), FakeLabel(), magnet="http://example.com")
    with pytest.raises(write.BadRequest):
        write.add(FakeCore(), FakeLabel(), magnet="magnet:?x", download_location="rel")
    with pytest.raises(write.BadRequest):
        write.add(FakeCore(), FakeLabel(), magnet="magnet:?x", add_paused="yes")
    with pytest.raises(write.BadRequest):
        write.add(FakeCore(), FakeLabel(), magnet="magnet:?x", label="nope")


def test_add_none_result_is_conflict():
    core = FakeCore()
    core.add_result = None

    with pytest.raises(write.Conflict):
        write.add(core, FakeLabel(), magnet="magnet:?x")
