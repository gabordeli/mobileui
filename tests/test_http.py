import io
import json

from twisted.web.server import NOT_DONE_YET
from twisted.web.test.requesthelper import DummyRequest

from deluge_mobileui import http
from deluge_mobileui.version import __version__


class FakePort:
    def __init__(self):
        self.stopped = False

    def stopListening(self):
        self.stopped = True


class FakeReactor:
    def __init__(self):
        self.calls = []
        self.port = FakePort()

    def listenTCP(self, port, site, interface=""):
        self.calls.append((port, site, interface))
        return self.port


class FakeConfig(dict):
    def __init__(self, data, config_file=""):
        super().__init__(data)
        self.config_file = config_file

    def save(self):
        pass


class StubPlugin:
    def __init__(self, authorized):
        self.config = {"port": 8113, "token": "secret"}
        self.authorized = authorized
        self.list_calls = []
        self.write_calls = []

    def is_authorized(self, request):
        return self.authorized

    def is_token_valid(self, token):
        return token == "secret"

    def subscribe_events(self, request):
        self.write_calls.append(("sse",))
        return NOT_DONE_YET

    def pause_torrent(self, torrent_id):
        if torrent_id == "missing":
            raise KeyError(torrent_id)
        self.write_calls.append(("pause", torrent_id))
        return {"id": torrent_id, "state": "Paused"}

    def resume_torrent(self, torrent_id):
        self.write_calls.append(("resume", torrent_id))
        return {"id": torrent_id, "state": "Downloading"}

    def remove_torrent(self, torrent_id, remove_data):
        if torrent_id == "conflict":
            raise http.Conflict("cannot remove")
        self.write_calls.append(("remove", torrent_id, remove_data))
        return {"id": torrent_id, "removed": True, "remove_data": remove_data}

    def queue_torrent(self, torrent_id, action):
        if action == "sideways":
            raise http.BadRequest("bad action")
        self.write_calls.append(("queue", torrent_id, action))
        return {"id": torrent_id, "action": action}

    def set_torrent_label(self, torrent_id, label):
        self.write_calls.append(("label", torrent_id, label))
        return {"id": torrent_id, "label": label}

    def add_torrent(self, **kwargs):
        if kwargs.get("magnet") == "magnet:?dup":
            raise http.Conflict("Torrent already in session")
        self.write_calls.append(("add", kwargs))
        return {"id": "newid", "label": "movies", "download_location": "/x"}

    def list_torrents(self, **kwargs):
        if kwargs["limit"] < 1:
            raise ValueError("limit must be between 1 and 200")
        self.list_calls.append(kwargs)
        return {
            "total": 0,
            "offset": kwargs["offset"],
            "limit": kwargs["limit"],
            "torrents": [],
        }

    def get_torrent(self, torrent_id):
        if torrent_id == "missing":
            raise KeyError(torrent_id)
        return {"id": torrent_id, "name": "Example"}

    def get_session(self):
        return {"version": "2.2.0", "num_torrents": 0}

    def get_labels(self):
        return {"labels": [], "no_label": 0}


def health_request():
    return DummyRequest([b"health"])


def test_health_returns_ok_json_without_auth():
    plugin = StubPlugin(authorized=False)
    request = health_request()

    body = http.HealthResource(plugin).render_GET(request)

    payload = json.loads(body)
    assert payload == {"ok": True, "version": __version__, "port": 8113}
    assert request.responseHeaders.getRawHeaders(b"content-type") == [
        b"application/json; charset=utf-8"
    ]


def test_root_exposes_health():
    plugin = StubPlugin(authorized=False)
    root = http.build_root(plugin)

    assert isinstance(
        root.getChildWithDefault(b"health", health_request()),
        http.HealthResource,
    )


def test_api_without_token_returns_json_401():
    plugin = StubPlugin(authorized=False)
    api = http.build_root(plugin).getChildWithDefault(
        b"api", DummyRequest([b"api"])
    )
    request = DummyRequest([b"api"])

    body = api.render(request)

    assert request.responseCode == 401
    assert json.loads(body)["error"] == "unauthorized"
    assert request.responseHeaders.getRawHeaders(b"www-authenticate") == [
        b'Bearer realm="mobileui"'
    ]


def test_api_with_token_returns_index():
    plugin = StubPlugin(authorized=True)
    api = http.build_root(plugin).getChildWithDefault(
        b"api", DummyRequest([b"api"])
    )
    request = DummyRequest([b"api"])

    body = api.render(request)

    assert request.responseCode == 200
    assert json.loads(body)["version"] == __version__


def test_unknown_api_child_requires_auth_first():
    plugin = StubPlugin(authorized=False)
    api = http.build_root(plugin).getChildWithDefault(
        b"api", DummyRequest([b"api"])
    )

    assert isinstance(
        api.getChild(b"session", DummyRequest([b"session"])),
        http.UnauthorizedResource,
    )


def api_child(plugin, path):
    request = DummyRequest([b"api", path])
    api = http.build_root(plugin).getChildWithDefault(b"api", request)
    return api.getChildWithDefault(path, request)


def test_session_requires_token_and_returns_payload():
    plugin = StubPlugin(authorized=False)
    session = api_child(plugin, b"session")
    request = DummyRequest([b"api", b"session"])

    body = session.render_GET(request)

    assert request.responseCode == 401
    assert json.loads(body)["error"] == "unauthorized"

    plugin.authorized = True
    request = DummyRequest([b"api", b"session"])
    body = session.render_GET(request)

    assert request.responseCode == 200
    assert json.loads(body)["version"] == "2.2.0"


def test_torrents_forwards_filters_and_pagination():
    plugin = StubPlugin(authorized=True)
    torrents = api_child(plugin, b"torrents")
    request = DummyRequest([b"api", b"torrents"])
    request.args = {
        b"state": [b"Paused"],
        b"label": [b"movies"],
        b"q": [b"dune"],
        b"sort": [b"-progress"],
        b"offset": [b"5"],
        b"limit": [b"10"],
    }

    body = torrents.render_GET(request)

    assert request.responseCode == 200
    assert json.loads(body)["limit"] == 10
    assert plugin.list_calls == [
        {
            "state": "Paused",
            "label": "movies",
            "q": "dune",
            "sort": "-progress",
            "offset": 5,
            "limit": 10,
        }
    ]


def test_torrents_rejects_bad_limit():
    plugin = StubPlugin(authorized=True)
    torrents = api_child(plugin, b"torrents")
    request = DummyRequest([b"api", b"torrents"])
    request.args = {b"limit": [b"0"]}

    body = torrents.render_GET(request)

    assert request.responseCode == 400
    assert json.loads(body)["error"] == "bad_request"
    assert plugin.list_calls == []


def test_torrent_detail_and_missing_id():
    plugin = StubPlugin(authorized=True)
    torrents = api_child(plugin, b"torrents")

    request = DummyRequest([b"api", b"torrents", b"abc"])
    body = torrents.getChild(b"abc", request).render_GET(request)
    assert request.responseCode == 200
    assert json.loads(body)["id"] == "abc"

    request = DummyRequest([b"api", b"torrents", b"missing"])
    body = torrents.getChild(b"missing", request).render_GET(request)
    assert request.responseCode == 404
    assert json.loads(body)["error"] == "not_found"


def test_labels_endpoint_requires_token():
    plugin = StubPlugin(authorized=False)
    labels = api_child(plugin, b"labels")
    request = DummyRequest([b"api", b"labels"])

    body = labels.render_GET(request)

    assert request.responseCode == 401
    assert json.loads(body)["error"] == "unauthorized"


def torrent_resource(plugin, torrent_id="abc"):
    torrents = api_child(plugin, b"torrents")
    request = DummyRequest([b"api", b"torrents", torrent_id.encode()])
    return torrents.getChild(torrent_id.encode(), request)


def post_request(path):
    request = DummyRequest(path)
    request.requestHeaders.addRawHeader(b"content-type", b"application/json")
    return request


def test_pause_and_resume_actions():
    plugin = StubPlugin(authorized=True)
    torrent = torrent_resource(plugin)

    request = post_request([b"api", b"torrents", b"abc", b"pause"])
    body = torrent.getChild(b"pause", request).render_POST(request)
    assert request.responseCode == 200
    assert json.loads(body)["state"] == "Paused"

    request = post_request([b"api", b"torrents", b"abc", b"resume"])
    body = torrent.getChild(b"resume", request).render_POST(request)
    assert request.responseCode == 200
    assert plugin.write_calls == [("pause", "abc"), ("resume", "abc")]


def test_action_unknown_torrent_returns_404():
    plugin = StubPlugin(authorized=True)
    torrent = torrent_resource(plugin, "missing")
    request = post_request([b"api", b"torrents", b"missing", b"pause"])

    body = torrent.getChild(b"pause", request).render_POST(request)

    assert request.responseCode == 404
    assert json.loads(body)["error"] == "not_found"


def test_remove_forwards_remove_data_and_conflict():
    plugin = StubPlugin(authorized=True)
    torrent = torrent_resource(plugin)
    request = post_request([b"api", b"torrents", b"abc", b"remove"])
    request.content = io.BytesIO(b'{"remove_data": true}')

    body = torrent.getChild(b"remove", request).render_POST(request)

    assert request.responseCode == 200
    assert plugin.write_calls[-1] == ("remove", "abc", True)

    conflict = torrent_resource(plugin, "conflict")
    request = post_request([b"api", b"torrents", b"conflict", b"remove"])
    body = conflict.getChild(b"remove", request).render_POST(request)
    assert request.responseCode == 409
    assert json.loads(body)["error"] == "conflict"


def test_queue_action_validation():
    plugin = StubPlugin(authorized=True)
    torrent = torrent_resource(plugin)
    request = post_request([b"api", b"torrents", b"abc", b"queue"])
    request.content = io.BytesIO(b'{"action": "top"}')

    torrent.getChild(b"queue", request).render_POST(request)

    assert request.responseCode == 200
    assert plugin.write_calls[-1] == ("queue", "abc", "top")

    request = post_request([b"api", b"torrents", b"abc", b"queue"])
    request.content = io.BytesIO(b'{"action": "sideways"}')
    torrent.getChild(b"queue", request).render_POST(request)
    assert request.responseCode == 400


def test_patch_label():
    plugin = StubPlugin(authorized=True)
    torrent = torrent_resource(plugin)
    request = post_request([b"api", b"torrents", b"abc"])
    request.content = io.BytesIO(b'{"label": "movies"}')

    body = torrent.render_PATCH(request)

    assert request.responseCode == 200
    assert json.loads(body)["label"] == "movies"
    assert plugin.write_calls == [("label", "abc", "movies")]


def test_patch_requires_label_field():
    plugin = StubPlugin(authorized=True)
    torrent = torrent_resource(plugin)
    request = post_request([b"api", b"torrents", b"abc"])
    request.content = io.BytesIO(b"{}")

    body = torrent.render_PATCH(request)

    assert request.responseCode == 400
    assert json.loads(body)["error"] == "bad_request"


def test_add_magnet_via_json():
    plugin = StubPlugin(authorized=True)
    torrents = api_child(plugin, b"torrents")
    request = post_request([b"api", b"torrents"])
    request.content = io.BytesIO(
        b'{"magnet": "magnet:?xt=urn:btih:x", "label": "movies",'
        b' "download_location": "/downloads", "add_paused": true}'
    )

    body = torrents.render_POST(request)

    assert request.responseCode == 201
    assert json.loads(body)["id"] == "newid"
    assert plugin.write_calls[-1] == (
        "add",
        {
            "magnet": "magnet:?xt=urn:btih:x",
            "filename": None,
            "filedump": None,
            "label": "movies",
            "download_location": "/downloads",
            "add_paused": True,
        },
    )


def test_add_magnet_conflict():
    plugin = StubPlugin(authorized=True)
    torrents = api_child(plugin, b"torrents")
    request = post_request([b"api", b"torrents"])
    request.content = io.BytesIO(b'{"magnet": "magnet:?dup"}')

    body = torrents.render_POST(request)

    assert request.responseCode == 409
    assert json.loads(body)["error"] == "conflict"


def test_add_raw_torrent_file():
    plugin = StubPlugin(authorized=True)
    torrents = api_child(plugin, b"torrents")
    request = DummyRequest([b"api", b"torrents"])
    request.requestHeaders.addRawHeader(b"content-type", b"application/x-bittorrent")
    request.content = io.BytesIO(b"torrent-bytes")
    request.args = {
        b"filename": [b"test.torrent"],
        b"label": [b"movies"],
        b"download_location": [b"/downloads"],
    }

    torrents.render_POST(request)

    assert request.responseCode == 201
    assert plugin.write_calls[-1] == (
        "add",
        {
            "filename": "test.torrent",
            "filedump": b"torrent-bytes",
            "label": "movies",
            "download_location": "/downloads",
            "add_paused": False,
        },
    )


def test_events_endpoint_requires_token():
    plugin = StubPlugin(authorized=False)
    events = api_child(plugin, b"events")
    request = DummyRequest([b"api", b"events"])

    body = events.render_GET(request)

    assert request.responseCode == 401
    assert json.loads(body)["error"] == "unauthorized"
    assert plugin.write_calls == []


def test_events_endpoint_accepts_query_token_and_streams():
    plugin = StubPlugin(authorized=False)
    events = api_child(plugin, b"events")
    request = DummyRequest([b"api", b"events"])
    request.args = {b"token": [b"secret"]}

    result = events.render_GET(request)

    assert result is NOT_DONE_YET
    assert request.responseHeaders.getRawHeaders(b"content-type") == [
        b"text/event-stream; charset=utf-8"
    ]
    assert request.responseHeaders.getRawHeaders(b"x-accel-buffering") == [b"no"]
    assert plugin.write_calls == [("sse",)]


def test_events_endpoint_rejects_bad_query_token():
    plugin = StubPlugin(authorized=False)
    events = api_child(plugin, b"events")
    request = DummyRequest([b"api", b"events"])
    request.args = {b"token": [b"wrong"]}

    body = events.render_GET(request)

    assert request.responseCode == 401
    assert json.loads(body)["error"] == "unauthorized"


def test_root_serves_spa_index(tmp_path, monkeypatch):
    (tmp_path / "index.html").write_text("<html>spa works</html>")
    monkeypatch.setattr(http, "DATA_DIR", tmp_path)
    plugin = StubPlugin(authorized=True)

    root = http.build_root(plugin)
    request = DummyRequest([b""])
    root.render_GET(request)

    assert b"spa works" in b"".join(request.written)


def test_root_without_build_returns_json_404(tmp_path, monkeypatch):
    monkeypatch.setattr(http, "DATA_DIR", tmp_path)
    plugin = StubPlugin(authorized=True)

    root = http.build_root(plugin)
    request = DummyRequest([b""])
    body = root.render_GET(request)

    assert request.responseCode == 404
    assert json.loads(body)["error"] == "not_found"
