import json
from types import SimpleNamespace

from twisted.web.server import NOT_DONE_YET

from deluge_mobileui import events


class FakeTorrent:
    def __init__(self, **fields):
        self.fields = fields

    def get_status(self, keys, update=False):
        return {key: self.fields.get(key) for key in keys}


class FakeSession:
    def __init__(self):
        self.paused = False

    def is_paused(self):
        return self.paused


class FakeCore:
    def __init__(self, torrents=None):
        self.torrentmanager = SimpleNamespace(torrents=torrents or {})
        self.session = FakeSession()

    def get_session_status(self, keys):
        return {key: 0 for key in keys}

    def get_config_values(self, keys):
        return {key: 0 for key in keys}


class FakeDeferred:
    def addBoth(self, callback, *args):
        self.callback = (callback, args)


class FakeRequest:
    def __init__(self):
        self.chunks = []
        self.headers = {}
        self.finished = False
        self.notify = None

    def setHeader(self, name, value):
        self.headers[name] = value

    def write(self, data):
        self.chunks.append(data)

    def notifyFinish(self):
        self.notify = FakeDeferred()
        return self.notify

    def finish(self):
        self.finished = True


def make_broadcaster(torrents=None):
    broadcaster = events.EventBroadcaster(plugin=None)
    broadcaster.core = FakeCore(torrents)
    return broadcaster


def text(request):
    return b"".join(request.chunks).decode("utf-8")


def payloads(request):
    result = []
    for line in text(request).splitlines():
        if line.startswith("data: "):
            result.append(json.loads(line[6:]))
    return result


def test_subscribe_sends_hello_and_unsubscribes():
    broadcaster = make_broadcaster({"a": FakeTorrent(progress=10.0)})
    request = FakeRequest()

    assert broadcaster.subscribe(request) is NOT_DONE_YET
    assert request in broadcaster.subscribers
    assert "event: hello" in text(request)
    assert '"heartbeat":15' in text(request)
    assert '"num_torrents":1' in text(request)

    broadcaster._on_finish(None, request)

    assert request not in broadcaster.subscribers


def test_state_added_removed_deltas():
    broadcaster = make_broadcaster()
    request = FakeRequest()
    broadcaster.subscribe(request)
    request.chunks.clear()

    broadcaster._on_added("a", False)
    broadcaster._on_state("a", "Paused")
    broadcaster._on_removed("b")
    broadcaster._tick()

    deltas = payloads(request)
    assert {"type": "added", "id": "a", "fields": {}} in deltas
    assert {"type": "state", "id": "a", "fields": {"state": "Paused"}} in deltas
    assert {"type": "removed", "id": "b", "fields": {}} in deltas


def test_progress_is_diffed_once_per_tick():
    torrent = FakeTorrent(
        progress=10.0, download_payload_rate=0, upload_payload_rate=0, eta=0
    )
    broadcaster = make_broadcaster({"a": torrent})
    request = FakeRequest()
    broadcaster.subscribe(request)
    request.chunks.clear()

    broadcaster._tick()
    assert payloads(request) == []

    torrent.fields["progress"] = 20.0
    torrent.fields["download_payload_rate"] = 100
    broadcaster._tick()

    deltas = payloads(request)
    assert deltas == [
        {
            "type": "progress",
            "id": "a",
            "fields": {
                "progress": 20.0,
                "download_payload_rate": 100,
                "upload_payload_rate": 0,
                "eta": 0,
            },
        }
    ]


def test_session_pause_event_emits_changed_fields():
    broadcaster = make_broadcaster()
    request = FakeRequest()
    broadcaster.subscribe(request)
    broadcaster._tick()
    request.chunks.clear()

    broadcaster.core.session.paused = True
    broadcaster._on_session()
    broadcaster._tick()

    deltas = payloads(request)
    assert len(deltas) == 1
    assert deltas[0]["type"] == "session"
    assert deltas[0]["id"] is None
    assert deltas[0]["fields"]["paused"] is True


def test_heartbeat_is_sent_every_15_ticks():
    broadcaster = make_broadcaster()
    request = FakeRequest()
    broadcaster.subscribe(request)
    request.chunks.clear()
    broadcaster.ticks = 14

    broadcaster._tick()

    assert ": heartbeat" in text(request)


def test_tick_without_subscribers_clears_pending():
    broadcaster = make_broadcaster()
    broadcaster._on_state("a", "Paused")
    broadcaster._on_added("a", False)

    broadcaster._tick()

    assert broadcaster.pending == {}
    assert broadcaster.pending_added == set()


def test_stop_closes_subscribers():
    broadcaster = make_broadcaster()
    request = FakeRequest()
    broadcaster.subscribe(request)

    broadcaster.stop()

    assert request.finished is True
    assert "event: bye" in text(request)
    assert broadcaster.subscribers == set()
