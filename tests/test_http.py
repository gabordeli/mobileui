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
    def __init__(self, authorized, level=10):
        self.config = {"port": 8113, "token": "secret", "auth_mode": "both"}
        self.authorized = authorized
        self.level = level
        self.list_calls = []
        self.write_calls = []

    def is_authorized(self, request):
        return self.authorized

    def access_level(self, request):
        return self.level if self.authorized else None

    def access_level_for_token(self, token):
        return 10 if token == "secret" else None

    def auth_identity(self, request):
        if not self.authorized:
            return None
        return self.level, "admin"

    def auth_info(self, level=None, username=""):
        info = {"mode": "both", "modes": ["token", "password"], "token_set": True}
        if level is not None:
            info.update(
                {
                    "authenticated": True,
                    "username": username,
                    "level": level,
                    "write": level >= 5,
                }
            )
        return info

    def is_token_valid(self, token):
        return token == "secret"

    def logout(self, token):
        return {"ok": True, "session": token == "secret"}

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

    def get_torrent_files(self, torrent_id, offset, limit, q=None):
        if torrent_id == "missing":
            raise KeyError(torrent_id)
        if limit < 1:
            raise ValueError("limit must be between 1 and 500")
        self.last_files_query = q
        self.write_calls.append(("files", torrent_id, offset, limit))
        return {
            "total": 3,
            "offset": offset,
            "limit": limit,
            "files": [
                {
                    "index": 0,
                    "path": "file.mkv",
                    "size": 10,
                    "progress": 1.0,
                    "priority": 4,
                }
            ],
        }

    def set_torrent_files(self, torrent_id, files=None, only=None):
        self.write_calls.append(("files", torrent_id, files, only))
        return {"id": torrent_id, "priorities": [0, 4]}

    def add_label(self, label_id):
        self.write_calls.append(("add_label", label_id))
        return {"id": label_id}

    def remove_label(self, label_id):
        self.write_calls.append(("remove_label", label_id))
        return {"id": label_id, "removed": True}

    def reannounce_torrent(self, torrent_id):
        self.write_calls.append(("reannounce", torrent_id))
        return {"id": torrent_id, "reannounced": True}

    def recheck_torrent(self, torrent_id):
        self.write_calls.append(("recheck", torrent_id))
        return {"id": torrent_id, "rechecked": True}

    def move_torrent(self, torrent_id, location):
        self.write_calls.append(("move", torrent_id, location))
        return {"id": torrent_id, "destination": location, "moving": True}

    def get_push_config(self):
        return {"enabled": True, "public_key": "pk", "subscriptions": 0}

    def subscribe_push(self, subscription, user_agent=None):
        self.write_calls.append(("push_sub", subscription, user_agent))
        return {"subscribed": True, "count": 1}

    def list_push_subscriptions(self):
        return {"subscriptions": [{"id": "abc123", "host": "push.example"}]}

    def remove_push_subscription(self, subscription_id):
        self.write_calls.append(("push_remove", subscription_id))
        return {"unsubscribed": True}

    def unsubscribe_push(self, endpoint):
        self.write_calls.append(("push_unsub", endpoint))
        return {"unsubscribed": True}

    def test_push(self, endpoint):
        self.write_calls.append(("push_test", endpoint))
        return {"queued": True}

    def get_session(self):
        return {"version": "2.2.0", "num_torrents": 0, "free_space": 4096}

    def pause_session(self):
        self.write_calls.append(("pause_session",))
        return {"paused": True}

    def resume_session(self):
        self.write_calls.append(("resume_session",))
        return {"paused": False}

    def set_session_limits(self, max_download_speed=None, max_upload_speed=None):
        self.write_calls.append(
            ("limits", "session", max_download_speed, max_upload_speed)
        )
        return {
            "max_download_speed": max_download_speed,
            "max_upload_speed": max_upload_speed,
        }

    def set_session_queue(self, **kwargs):
        values = {key: value for key, value in kwargs.items() if value is not None}
        self.write_calls.append(("queue_settings", values))
        return values

    def set_torrent_limits(
        self, torrent_id, max_download_speed=None, max_upload_speed=None
    ):
        self.write_calls.append(
            ("limits", torrent_id, max_download_speed, max_upload_speed)
        )
        return {
            "id": torrent_id,
            "max_download_speed": max_download_speed,
            "max_upload_speed": max_upload_speed,
        }

    def get_torrent_options(self, torrent_id):
        return {
            "id": torrent_id,
            "options": {"sequential_download": False, "stop_ratio": 1.0},
        }

    def set_torrent_options(self, torrent_id, options):
        self.write_calls.append(("options", torrent_id, options))
        return {"id": torrent_id, "options": options}

    def list_torrent_ids(self, state=None, label=None, q=None):
        self.list_calls.append((state, label, q))
        return {"ids": ["abc"], "total": 1, "limit": 1000}

    def bulk_action(self, action, torrent_ids=None, label=None, remove_data=False):
        ids = list(torrent_ids or [])
        self.write_calls.append(("bulk", action, ids))
        return {"ok": len(ids), "failed": []}

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
    assert json.loads(body)["free_space"] == 4096


def test_session_pause_and_resume_actions():
    plugin = StubPlugin(authorized=True)
    session = api_child(plugin, b"session")

    for action, expected in ((b"pause", True), (b"resume", False)):
        request = post_request([b"api", b"session", action])
        body = session.getChildWithDefault(action, request).render_POST(request)
        assert request.responseCode == 200
        assert json.loads(body)["paused"] is expected

    assert plugin.write_calls == [("pause_session",), ("resume_session",)]


def test_session_actions_require_auth_and_write_level():
    plugin = StubPlugin(authorized=False)
    session = api_child(plugin, b"session")
    request = post_request([b"api", b"session", b"pause"])

    session.getChildWithDefault(b"pause", request).render_POST(request)
    assert request.responseCode == 401

    plugin.authorized = True
    plugin.level = 1
    request = post_request([b"api", b"session", b"pause"])
    body = session.getChildWithDefault(b"pause", request).render_POST(request)

    assert request.responseCode == 403
    assert json.loads(body)["error"] == "forbidden"
    assert plugin.write_calls == []


def mutation_cases(plugin):
    session = api_child(plugin, b"session")
    torrent = torrent_resource(plugin)
    torrents = api_child(plugin, b"torrents")
    labels = api_child(plugin, b"labels")

    def case(name, resource, method, path, payload=None):
        request = post_request(path)
        if payload is not None:
            request.content = io.BytesIO(json.dumps(payload).encode("utf-8"))
        return (name, resource, method, request)

    def child(resource, action, path):
        return resource.getChildWithDefault(action, DummyRequest(path))

    return [
        case(
            "session pause",
            child(session, b"pause", [b"api", b"session", b"pause"]),
            "render_POST",
            [b"api", b"session", b"pause"],
        ),
        case(
            "session resume",
            child(session, b"resume", [b"api", b"session", b"resume"]),
            "render_POST",
            [b"api", b"session", b"resume"],
        ),
        case(
            "torrent pause",
            child(torrent, b"pause", [b"api", b"torrents", b"abc", b"pause"]),
            "render_POST",
            [b"api", b"torrents", b"abc", b"pause"],
        ),
        case(
            "torrent resume",
            child(torrent, b"resume", [b"api", b"torrents", b"abc", b"resume"]),
            "render_POST",
            [b"api", b"torrents", b"abc", b"resume"],
        ),
        case(
            "torrent remove",
            child(torrent, b"remove", [b"api", b"torrents", b"abc", b"remove"]),
            "render_POST",
            [b"api", b"torrents", b"abc", b"remove"],
            {"remove_data": True},
        ),
        case(
            "torrent queue",
            child(torrent, b"queue", [b"api", b"torrents", b"abc", b"queue"]),
            "render_POST",
            [b"api", b"torrents", b"abc", b"queue"],
            {"action": "top"},
        ),
        case(
            "torrent label",
            torrent,
            "render_PATCH",
            [b"api", b"torrents", b"abc"],
            {"label": "No Label"},
        ),
        case(
            "add torrent",
            torrents,
            "render_POST",
            [b"api", b"torrents"],
            {"magnet": "magnet:?x"},
        ),
        case(
            "bulk pause",
            torrents.getChildWithDefault(
                b"bulk", DummyRequest([b"api", b"torrents", b"bulk"])
            ),
            "render_POST",
            [b"api", b"torrents", b"bulk"],
            {"action": "pause", "torrent_ids": ["abc"]},
        ),
        case(
            "torrent files",
            child(torrent, b"files", [b"api", b"torrents", b"abc", b"files"]),
            "render_PATCH",
            [b"api", b"torrents", b"abc", b"files"],
            {"files": [{"index": 0, "priority": 0}]},
        ),
        case(
            "session limits",
            child(session, b"limits", [b"api", b"session", b"limits"]),
            "render_PATCH",
            [b"api", b"session", b"limits"],
            {"max_download_speed": 512, "max_upload_speed": 128},
        ),
        case(
            "session queue",
            child(session, b"queue", [b"api", b"session", b"queue"]),
            "render_PATCH",
            [b"api", b"session", b"queue"],
            {"max_active_downloading": 2},
        ),
        case(
            "torrent limits",
            child(torrent, b"limits", [b"api", b"torrents", b"abc", b"limits"]),
            "render_PATCH",
            [b"api", b"torrents", b"abc", b"limits"],
            {"max_download_speed": 0},
        ),
        case(
            "torrent options",
            child(torrent, b"options", [b"api", b"torrents", b"abc", b"options"]),
            "render_PATCH",
            [b"api", b"torrents", b"abc", b"options"],
            {"sequential_download": True},
        ),
        case(
            "label add",
            labels,
            "render_POST",
            [b"api", b"labels"],
            {"id": "movies"},
        ),
        case(
            "label remove",
            child(labels, b"movies", [b"api", b"labels", b"movies"]),
            "render_DELETE",
            [b"api", b"labels", b"movies"],
        ),
        case(
            "reannounce",
            child(
                torrent,
                b"reannounce",
                [b"api", b"torrents", b"abc", b"reannounce"],
            ),
            "render_POST",
            [b"api", b"torrents", b"abc", b"reannounce"],
        ),
        case(
            "recheck",
            child(
                torrent,
                b"recheck",
                [b"api", b"torrents", b"abc", b"recheck"],
            ),
            "render_POST",
            [b"api", b"torrents", b"abc", b"recheck"],
        ),
        case(
            "move",
            child(
                torrent,
                b"move",
                [b"api", b"torrents", b"abc", b"move"],
            ),
            "render_POST",
            [b"api", b"torrents", b"abc", b"move"],
            {"location": "/data/new"},
        ),
    ]


def test_every_mutation_rejects_readonly_level():
    plugin = StubPlugin(authorized=True, level=1)

    for name, resource, method, request in mutation_cases(plugin):
        body = getattr(resource, method)(request)
        assert request.responseCode == 403, name
        assert json.loads(body)["error"] == "forbidden", name

    assert plugin.write_calls == []


def test_every_mutation_allows_normal_level():
    plugin = StubPlugin(authorized=True, level=5)
    cases = mutation_cases(plugin)

    for name, resource, method, request in cases:
        body = getattr(resource, method)(request)
        assert request.responseCode in (200, 201), name
        assert "error" not in json.loads(body), name

    assert len(plugin.write_calls) == len(cases)


def test_torrent_ids_returns_matching_ids():
    plugin = StubPlugin(authorized=True)
    torrents = api_child(plugin, b"torrents")
    request = DummyRequest([b"api", b"torrents", b"ids"])
    request.args = {b"state": [b"Paused"], b"label": [b"movies"]}

    body = torrents.getChildWithDefault(b"ids", request).render_GET(request)

    assert request.responseCode == 200
    assert json.loads(body)["ids"] == ["abc"]
    assert plugin.list_calls == [("Paused", "movies", None)]


def test_bulk_endpoint_returns_the_summary():
    plugin = StubPlugin(authorized=True)
    torrents = api_child(plugin, b"torrents")
    request = post_request([b"api", b"torrents", b"bulk"])
    request.content = io.BytesIO(b'{"action":"pause","torrent_ids":["a","b"]}')

    body = torrents.getChildWithDefault(b"bulk", request).render_POST(request)

    assert request.responseCode == 200
    assert json.loads(body) == {"ok": 2, "failed": []}
    assert plugin.write_calls == [("bulk", "pause", ["a", "b"])]


def test_bulk_endpoint_validates_the_body():
    plugin = StubPlugin(authorized=True)
    torrents = api_child(plugin, b"torrents")
    request = post_request([b"api", b"torrents", b"bulk"])
    request.content = io.BytesIO(b'{"action":"pause","torrent_ids":"abc"}')

    body = torrents.getChildWithDefault(b"bulk", request).render_POST(request)

    assert request.responseCode == 400
    assert json.loads(body)["error"] == "bad_request"


def test_torrent_files_patch_updates_priorities():
    plugin = StubPlugin(authorized=True)
    torrent = torrent_resource(plugin)
    request = post_request([b"api", b"torrents", b"abc", b"files"])
    request.method = b"PATCH"
    request.content = io.BytesIO(b'{"files":[{"index":0,"priority":0}]}')

    body = torrent.getChildWithDefault(b"files", request).render_PATCH(request)

    assert request.responseCode == 200
    assert json.loads(body)["priorities"] == [0, 4]
    assert plugin.write_calls == [
        ("files", "abc", [{"index": 0, "priority": 0}], None)
    ]


def test_torrent_files_patch_forwards_the_body():
    plugin = StubPlugin(authorized=True)
    torrent = torrent_resource(plugin)
    request = post_request([b"api", b"torrents", b"abc", b"files"])
    request.method = b"PATCH"
    request.content = io.BytesIO(b'{"only":1}')

    body = torrent.getChildWithDefault(b"files", request).render_PATCH(request)

    assert request.responseCode == 200
    assert json.loads(body)["id"] == "abc"
    assert plugin.write_calls == [("files", "abc", None, 1)]


def test_session_limits_patch_forwards_values():
    plugin = StubPlugin(authorized=True)
    session = api_child(plugin, b"session")
    request = post_request([b"api", b"session", b"limits"])
    request.method = b"PATCH"
    request.content = io.BytesIO(
        b'{"max_download_speed":512,"max_upload_speed":128}'
    )

    body = session.getChildWithDefault(b"limits", request).render_PATCH(request)

    assert request.responseCode == 200
    assert json.loads(body)["max_download_speed"] == 512
    assert plugin.write_calls == [("limits", "session", 512, 128)]


def test_session_queue_patch_forwards_values():
    plugin = StubPlugin(authorized=True)
    session = api_child(plugin, b"session")
    request = post_request([b"api", b"session", b"queue"])
    request.method = b"PATCH"
    request.content = io.BytesIO(
        b'{"max_active_downloading":2,"queue_new_to_top":true}'
    )

    body = session.getChildWithDefault(b"queue", request).render_PATCH(request)

    assert request.responseCode == 200
    assert json.loads(body) == {
        "max_active_downloading": 2,
        "queue_new_to_top": True,
    }
    assert plugin.write_calls == [
        (
            "queue_settings",
            {"max_active_downloading": 2, "queue_new_to_top": True},
        )
    ]


def test_torrent_limits_patch_forwards_values():
    plugin = StubPlugin(authorized=True)
    torrent = torrent_resource(plugin)
    request = post_request([b"api", b"torrents", b"abc", b"limits"])
    request.method = b"PATCH"
    request.content = io.BytesIO(b'{"max_download_speed":0}')

    body = torrent.getChildWithDefault(b"limits", request).render_PATCH(request)

    assert request.responseCode == 200
    assert json.loads(body)["id"] == "abc"
    assert plugin.write_calls == [("limits", "abc", 0, None)]


def test_torrent_options_get_and_patch():
    plugin = StubPlugin(authorized=True)
    torrent = torrent_resource(plugin)

    request = DummyRequest([b"api", b"torrents", b"abc", b"options"])
    body = torrent.getChildWithDefault(b"options", request).render_GET(request)

    assert request.responseCode == 200
    assert json.loads(body)["options"]["stop_ratio"] == 1.0

    request = post_request([b"api", b"torrents", b"abc", b"options"])
    request.method = b"PATCH"
    request.content = io.BytesIO(
        b'{"sequential_download":true,"stop_ratio":2.5}'
    )
    body = torrent.getChildWithDefault(b"options", request).render_PATCH(request)

    assert request.responseCode == 200
    assert json.loads(body)["options"]["stop_ratio"] == 2.5
    assert plugin.write_calls == [
        ("options", "abc", {"sequential_download": True, "stop_ratio": 2.5})
    ]


def test_labels_add_and_remove():
    plugin = StubPlugin(authorized=True)
    labels = api_child(plugin, b"labels")
    request = post_request([b"api", b"labels"])
    request.content = io.BytesIO(b'{"id":"movies"}')

    body = labels.render_POST(request)
    assert request.responseCode == 201
    assert json.loads(body)["id"] == "movies"

    request = post_request([b"api", b"labels", b"movies"])
    request.method = b"DELETE"
    body = labels.getChildWithDefault(b"movies", request).render_DELETE(request)
    assert request.responseCode == 200
    assert json.loads(body)["removed"] is True
    assert plugin.write_calls == [
        ("add_label", "movies"),
        ("remove_label", "movies"),
    ]


def test_reannounce_endpoint():
    plugin = StubPlugin(authorized=True)
    torrent = torrent_resource(plugin)
    request = post_request([b"api", b"torrents", b"abc", b"reannounce"])

    body = torrent.getChildWithDefault(b"reannounce", request).render_POST(request)

    assert request.responseCode == 200
    assert json.loads(body)["reannounced"] is True
    assert plugin.write_calls == [("reannounce", "abc")]


def test_recheck_endpoint():
    plugin = StubPlugin(authorized=True)
    torrent = torrent_resource(plugin)
    request = post_request([b"api", b"torrents", b"abc", b"recheck"])

    body = torrent.getChildWithDefault(b"recheck", request).render_POST(request)

    assert request.responseCode == 200
    assert json.loads(body)["rechecked"] is True
    assert plugin.write_calls == [("recheck", "abc")]


def test_move_endpoint_forwards_location():
    plugin = StubPlugin(authorized=True)
    torrent = torrent_resource(plugin)
    request = post_request([b"api", b"torrents", b"abc", b"move"])
    request.content = io.BytesIO(b'{"location":"/data/new"}')

    body = torrent.getChildWithDefault(b"move", request).render_POST(request)

    assert request.responseCode == 200
    payload = json.loads(body)
    assert payload["moving"] is True
    assert payload["destination"] == "/data/new"
    assert plugin.write_calls == [("move", "abc", "/data/new")]


def test_push_config_and_subscribe_endpoints():
    plugin = StubPlugin(authorized=True)
    root = api_child(plugin, b"push")

    request = DummyRequest([b"api", b"push", b"config"])
    body = root.getChildWithDefault(b"config", request).render_GET(request)
    assert request.responseCode == 200
    assert json.loads(body)["public_key"] == "pk"

    request = post_request([b"api", b"push", b"subscribe"])
    request.content = io.BytesIO(
        b'{"endpoint":"https://push/1","keys":{"p256dh":"a","auth":"b"}}'
    )
    body = root.getChildWithDefault(b"subscribe", request).render_POST(request)
    assert request.responseCode == 201
    assert json.loads(body)["subscribed"] is True
    assert plugin.write_calls[0][0] == "push_sub"

    request = post_request([b"api", b"push", b"subscribe"])
    request.method = b"DELETE"
    request.content = io.BytesIO(b'{"endpoint":"https://push/1"}')
    body = root.getChildWithDefault(b"subscribe", request).render_DELETE(request)
    assert request.responseCode == 200
    assert json.loads(body)["unsubscribed"] is True
    assert plugin.write_calls[1] == ("push_unsub", "https://push/1")

    request = post_request([b"api", b"push", b"test"])
    request.content = io.BytesIO(b'{"endpoint":"https://push/1"}')
    body = root.getChildWithDefault(b"test", request).render_POST(request)
    assert request.responseCode == 200
    assert json.loads(body)["queued"] is True
    assert plugin.write_calls[2] == ("push_test", "https://push/1")

    request = DummyRequest([b"api", b"push", b"subscriptions"])
    body = root.getChildWithDefault(b"subscriptions", request).render_GET(request)
    assert request.responseCode == 200
    assert json.loads(body)["subscriptions"][0]["id"] == "abc123"

    request = post_request([b"api", b"push", b"subscriptions"])
    request.method = b"DELETE"
    request.content = io.BytesIO(b'{"id":"abc123"}')
    body = root.getChildWithDefault(b"subscriptions", request).render_DELETE(request)
    assert request.responseCode == 200
    assert json.loads(body)["unsubscribed"] is True


def test_push_subscribe_allows_readonly_level():
    plugin = StubPlugin(authorized=True, level=1)
    root = api_child(plugin, b"push")
    request = post_request([b"api", b"push", b"subscribe"])
    request.content = io.BytesIO(
        b'{"endpoint":"https://push/1","keys":{"p256dh":"a","auth":"b"}}'
    )

    body = root.getChildWithDefault(b"subscribe", request).render_POST(request)

    assert request.responseCode == 201
    assert json.loads(body)["subscribed"] is True

    request = post_request([b"api", b"push", b"test"])
    request.content = io.BytesIO(b'{"endpoint":"https://push/1"}')
    body = root.getChildWithDefault(b"test", request).render_POST(request)

    assert request.responseCode == 200
    assert json.loads(body)["queued"] is True


def test_push_requires_auth():
    plugin = StubPlugin(authorized=False)
    root = api_child(plugin, b"push")
    request = DummyRequest([b"api", b"push", b"config"])

    body = root.getChildWithDefault(b"config", request).render(request)

    assert request.responseCode == 401
    assert json.loads(body)["error"] == "unauthorized"


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


def test_torrent_files_are_paginated():
    plugin = StubPlugin(authorized=True)
    torrent = torrent_resource(plugin)
    request = DummyRequest([b"api", b"torrents", b"abc", b"files"])
    request.args = {b"offset": [b"1"], b"limit": [b"5"], b"q": [b"file"]}

    body = torrent.getChild(b"files", request).render_GET(request)

    assert request.responseCode == 200
    assert json.loads(body)["total"] == 3
    assert plugin.last_files_query == "file"
    assert plugin.write_calls[-1] == ("files", "abc", 1, 5)


def test_torrent_files_errors():
    plugin = StubPlugin(authorized=True)
    torrent = torrent_resource(plugin)

    request = DummyRequest([b"api", b"torrents", b"abc", b"files"])
    request.args = {b"limit": [b"0"]}
    body = torrent.getChild(b"files", request).render_GET(request)
    assert request.responseCode == 400
    assert json.loads(body)["error"] == "bad_request"

    missing = torrent_resource(plugin, "missing")
    request = DummyRequest([b"api", b"torrents", b"missing", b"files"])
    missing.getChild(b"files", request).render_GET(request)
    assert request.responseCode == 404


class LoginStub(StubPlugin):
    def __init__(self):
        super().__init__(authorized=False)

    def login(self, username, password, remote=""):
        self.write_calls.append(("login", username, remote))
        if username == "limited":
            raise http.TooManyAttempts("limited")
        if username == "offline":
            raise http.AuthUnavailable("offline")
        if username == "admin" and password == "pw":
            return {
                "token": "sess",
                "username": "admin",
                "level": 10,
                "expires": 1,
            }
        raise http.InvalidCredentials("bad login")


class FakeAddress:
    host = "198.51.100.7"


def login_request(payload):
    request = post_request([b"api", b"login"])
    request.content = io.BytesIO(json.dumps(payload).encode("utf-8"))
    request.getClientAddress = lambda: FakeAddress()
    return request


def test_auth_info_is_public_without_identity():
    plugin = StubPlugin(authorized=False)
    auth = api_child(plugin, b"auth")
    request = DummyRequest([b"api", b"auth"])

    body = auth.render_GET(request)

    assert request.responseCode == 200
    payload = json.loads(body)
    assert payload["modes"] == ["token", "password"]
    assert payload["token_set"] is True
    assert "authenticated" not in payload


def test_auth_info_reports_readonly_identity():
    plugin = StubPlugin(authorized=True, level=1)
    auth = api_child(plugin, b"auth")
    request = DummyRequest([b"api", b"auth"])

    payload = json.loads(auth.render_GET(request))

    assert payload["authenticated"] is True
    assert payload["username"] == "admin"
    assert payload["level"] == 1
    assert payload["write"] is False


def test_login_returns_session_token():
    plugin = LoginStub()
    login = api_child(plugin, b"login")
    request = login_request({"username": "admin", "password": "pw"})

    body = login.render_POST(request)

    assert request.responseCode == 200
    assert json.loads(body)["token"] == "sess"
    assert plugin.write_calls == [("login", "admin", "198.51.100.7")]


def test_login_rejects_bad_credentials_with_generic_401():
    plugin = LoginStub()
    login = api_child(plugin, b"login")
    request = login_request({"username": "admin", "password": "nope"})

    body = login.render_POST(request)

    assert request.responseCode == 401
    payload = json.loads(body)
    assert payload["error"] == "unauthorized"
    assert payload["message"] == "Missing or invalid credentials"


def test_login_rate_limit_returns_429():
    plugin = LoginStub()
    login = api_child(plugin, b"login")
    request = login_request({"username": "limited", "password": "x"})

    body = login.render_POST(request)

    assert request.responseCode == 429
    assert json.loads(body)["error"] == "too_many_attempts"
    assert request.responseHeaders.getRawHeaders(b"retry-after") == [b"60"]


def test_login_without_auth_manager_returns_503():
    plugin = LoginStub()
    login = api_child(plugin, b"login")
    request = login_request({"username": "offline", "password": "x"})

    body = login.render_POST(request)

    assert request.responseCode == 503
    assert json.loads(body)["error"] == "auth_unavailable"


def test_login_rejects_invalid_body():
    plugin = LoginStub()
    login = api_child(plugin, b"login")
    request = post_request([b"api", b"login"])
    request.content = io.BytesIO(b"{")

    body = login.render_POST(request)

    assert request.responseCode == 400
    assert json.loads(body)["error"] == "bad_request"


def test_logout_requires_auth_and_invalidates():
    plugin = StubPlugin(authorized=False)
    logout = api_child(plugin, b"logout")
    request = post_request([b"api", b"logout"])

    logout.render_POST(request)
    assert request.responseCode == 401

    plugin.authorized = True
    request = post_request([b"api", b"logout"])
    request.requestHeaders.addRawHeader(b"authorization", b"Bearer secret")
    body = logout.render_POST(request)

    assert request.responseCode == 200
    assert json.loads(body) == {"ok": True, "session": True}


def test_readonly_account_can_read_but_not_write():
    plugin = StubPlugin(authorized=True, level=1)
    torrent = torrent_resource(plugin)

    request = DummyRequest([b"api", b"torrents", b"abc"])
    body = torrent.render_GET(request)
    assert request.responseCode == 200
    assert json.loads(body)["id"] == "abc"

    request = post_request([b"api", b"torrents", b"abc", b"pause"])
    body = torrent.getChild(b"pause", request).render_POST(request)
    assert request.responseCode == 403
    assert json.loads(body)["error"] == "forbidden"
    assert plugin.write_calls == []


def test_client_key_prefers_forwarded_header():
    request = DummyRequest([b"api"])
    request.requestHeaders.addRawHeader(
        b"x-forwarded-for", b"203.0.113.9, 10.0.0.1"
    )

    assert http.client_key(request) == "203.0.113.9"


def test_client_key_falls_back_to_peer_address():
    request = DummyRequest([b"api"])
    request.getClientAddress = lambda: FakeAddress()

    assert http.client_key(request) == "198.51.100.7"
