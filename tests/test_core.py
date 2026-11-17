import pytest
from deluge.common import AUTH_LEVEL_ADMIN, AUTH_LEVEL_READONLY
from twisted.web.test.requesthelper import DummyRequest

from deluge_mobileui import core

from .test_http import FakeConfig, FakePort, FakeReactor


class CoreStub(core.Core):
    # CorePluginBase.__del__ deregisters from RPCServer, which does not exist
    # in the unit-test process; keep GC from raising an unraisable KeyError.
    def __del__(self):
        pass


def make_plugin():
    plugin = object.__new__(CoreStub)
    plugin.config = None
    plugin.site = None
    plugin.listener = None
    plugin.events = None
    plugin.sessions = {}
    plugin._login_failures = {}
    return plugin


def authorization_request(header=None):
    request = DummyRequest([b""])
    if header is not None:
        request.requestHeaders.addRawHeader(b"authorization", header)
    return request


def test_enable_starts_server_and_disable_stops_it(monkeypatch):
    fake_reactor = FakeReactor()
    monkeypatch.setattr(core, "reactor", fake_reactor)
    monkeypatch.setattr(
        core,
        "ConfigManager",
        lambda *args, **kwargs: FakeConfig(
            {"enabled": True, "port": 8113, "token": ""}
        ),
    )
    monkeypatch.setattr(core.Core, "_ensure_config_file", lambda self: None)

    plugin = make_plugin()
    plugin.enable()

    assert fake_reactor.calls[0][0] == 8113
    assert fake_reactor.calls[0][2] == "0.0.0.0"
    assert plugin.site is not None

    deferred = plugin.disable()

    assert fake_reactor.port.stopped is True
    assert plugin.listener is None
    assert deferred.called is True


def test_enable_can_be_skipped_by_config(monkeypatch):
    fake_reactor = FakeReactor()
    monkeypatch.setattr(core, "reactor", fake_reactor)
    monkeypatch.setattr(
        core,
        "ConfigManager",
        lambda *args, **kwargs: FakeConfig(
            {"enabled": False, "port": 8113, "token": ""}
        ),
    )
    monkeypatch.setattr(core.Core, "_ensure_config_file", lambda self: None)

    plugin = make_plugin()
    plugin.enable()

    assert fake_reactor.calls == []
    assert plugin.listener is None


def test_disable_without_listener_is_a_noop():
    plugin = make_plugin()

    assert plugin.disable() is None


def test_ensure_config_file_creates_600(tmp_path):
    from deluge.config import Config

    config_file = tmp_path / "mobileui.conf"
    plugin = make_plugin()
    plugin.config = Config(str(config_file), defaults=core.CONFIG_DEFAULTS)

    plugin._ensure_config_file()

    assert config_file.exists()
    assert config_file.stat().st_mode & 0o777 == 0o600
    assert plugin.config["token"] == ""


def test_is_token_valid_accepts_configured_token():
    plugin = make_plugin()
    plugin.config = {"token": "secret"}

    assert plugin.is_token_valid("secret") is True
    assert plugin.is_token_valid("wrong") is False
    assert plugin.is_token_valid("") is False
    assert plugin.is_token_valid(None) is False


def test_is_authorized_accepts_bearer_token():
    plugin = make_plugin()
    plugin.config = {"token": "secret"}

    assert plugin.is_authorized(authorization_request(b"Bearer secret")) is True


@pytest.mark.parametrize(
    "header,token",
    [
        (None, "secret"),
        (b"Bearer wrong", "secret"),
        (b"Basic secret", "secret"),
        (b"Bearer secret", ""),
    ],
)
def test_is_authorized_rejects_bad_credentials(header, token):
    plugin = make_plugin()
    plugin.config = {"token": token}

    assert plugin.is_authorized(authorization_request(header)) is False


def test_set_config_updates_token_immediately(tmp_path, monkeypatch):
    config_file = tmp_path / "mobileui.conf"
    config_file.write_text("{}")
    plugin = make_plugin()
    plugin.config = FakeConfig(
        {"enabled": True, "port": 8113, "token": "old"}, str(config_file)
    )
    fake_reactor = FakeReactor()
    monkeypatch.setattr(core, "reactor", fake_reactor)

    result = plugin.set_config({"token": "new"})

    assert result["token_set"] is True
    assert plugin.is_authorized(authorization_request(b"Bearer new")) is True
    assert plugin.is_authorized(authorization_request(b"Bearer old")) is False
    assert config_file.stat().st_mode & 0o777 == 0o600


def test_set_config_rebinds_port(tmp_path, monkeypatch):
    config_file = tmp_path / "mobileui.conf"
    config_file.write_text("{}")
    plugin = make_plugin()
    plugin.config = FakeConfig(
        {"enabled": True, "port": 8113, "token": "secret"}, str(config_file)
    )
    plugin.listener = old_port = FakePort()
    fake_reactor = FakeReactor()
    monkeypatch.setattr(core, "reactor", fake_reactor)

    result = plugin.set_config({"port": 8114})

    assert result["port"] == 8114
    assert old_port.stopped is True
    assert fake_reactor.calls[-1][0] == 8114


def test_set_config_reverts_port_when_bind_fails(tmp_path, monkeypatch):
    class FailingReactor(FakeReactor):
        def listenTCP(self, port, site, interface=""):
            if port == 9999:
                raise OSError("address in use")
            return super().listenTCP(port, site, interface)

    config_file = tmp_path / "mobileui.conf"
    config_file.write_text("{}")
    plugin = make_plugin()
    plugin.config = FakeConfig(
        {"enabled": True, "port": 8113, "token": "secret"}, str(config_file)
    )
    plugin.listener = FakePort()
    fake_reactor = FailingReactor()
    monkeypatch.setattr(core, "reactor", fake_reactor)

    with pytest.raises(OSError):
        plugin.set_config({"port": 9999})

    assert plugin.config["port"] == 8113
    assert fake_reactor.calls[-1][0] == 8113


def test_set_config_can_disable_server(tmp_path, monkeypatch):
    config_file = tmp_path / "mobileui.conf"
    config_file.write_text("{}")
    plugin = make_plugin()
    plugin.config = FakeConfig(
        {"enabled": True, "port": 8113, "token": "secret"}, str(config_file)
    )
    plugin.listener = FakePort()
    monkeypatch.setattr(core, "reactor", FakeReactor())

    result = plugin.set_config({"enabled": False})

    assert result["enabled"] is False
    assert plugin.listener is None


@pytest.mark.parametrize(
    "config,exception",
    [
        ({"nope": 1}, ValueError),
        ({"port": 0}, ValueError),
        ({"token": 123}, TypeError),
        ({"enabled": "yes"}, TypeError),
        ({"sentry_dsn": 123}, TypeError),
        ({"auth_mode": "nope"}, ValueError),
        ({"auth_mode": 1}, TypeError),
        ({"vapid_subject": 1}, TypeError),
    ],
)
def test_set_config_validates_input(config, exception, tmp_path):
    plugin = make_plugin()
    plugin.config = FakeConfig(
        {"enabled": True, "port": 8113, "token": "secret"},
        str(tmp_path / "mobileui.conf"),
    )

    with pytest.raises(exception):
        plugin.set_config(config)


def _fake_sentry():
    calls = []

    class FakeSentry:
        def init(self, **kwargs):
            calls.append(kwargs)

    return FakeSentry(), calls


def test_init_sentry_skips_without_dsn(monkeypatch):
    fake, calls = _fake_sentry()
    monkeypatch.setattr(core, "sentry_sdk", fake)
    monkeypatch.setattr(core, "TwistedIntegration", lambda: "twisted")
    plugin = make_plugin()
    plugin.config = {"sentry_dsn": ""}

    plugin._init_sentry()

    assert calls == []


def test_init_sentry_initializes_with_dsn(monkeypatch):
    fake, calls = _fake_sentry()
    monkeypatch.setattr(core, "sentry_sdk", fake)
    monkeypatch.setattr(core, "TwistedIntegration", lambda: "twisted")
    plugin = make_plugin()
    plugin.config = {"sentry_dsn": "https://key@bugsink/4"}

    plugin._init_sentry()

    assert calls[0]["dsn"] == "https://key@bugsink/4"
    assert calls[0]["release"] == core.__version__
    assert calls[0]["integrations"] == ["twisted"]
    assert calls[0]["traces_sample_rate"] == 0.0
    assert calls[0]["send_default_pii"] is False


def test_set_config_updates_sentry_dsn(tmp_path, monkeypatch):
    config_file = tmp_path / "mobileui.conf"
    config_file.write_text("{}")
    plugin = make_plugin()
    plugin.config = FakeConfig(
        {
            "enabled": True,
            "port": 8113,
            "token": "secret",
            "sentry_dsn": "",
        },
        str(config_file),
    )
    plugin.listener = FakePort()
    fake, calls = _fake_sentry()
    monkeypatch.setattr(core, "reactor", FakeReactor())
    monkeypatch.setattr(core, "sentry_sdk", fake)
    monkeypatch.setattr(core, "TwistedIntegration", lambda: "twisted")

    result = plugin.set_config({"sentry_dsn": "https://key@bugsink/4"})

    assert result["sentry_set"] is True
    assert plugin.config["sentry_dsn"] == "https://key@bugsink/4"
    assert calls[0]["dsn"] == "https://key@bugsink/4"
    assert config_file.stat().st_mode & 0o777 == 0o600


class FakeAuthManager:
    def __init__(self):
        self.calls = []

    def authorize(self, username, password):
        self.calls.append((username, password))
        if username == "admin" and password == "pw":
            return AUTH_LEVEL_ADMIN
        if username == "guest" and password == "ro":
            return AUTH_LEVEL_READONLY
        raise core.BadLoginError("bad login", username)


NOW = 4_000_000_000


def auth_plugin(monkeypatch, mode="password", token="secret"):
    plugin = make_plugin()
    plugin.config = {
        "enabled": True,
        "port": 8113,
        "token": token,
        "auth_mode": mode,
    }
    manager = FakeAuthManager()
    monkeypatch.setattr(core.Core, "_auth_manager", lambda self: manager)
    return plugin, manager


@pytest.mark.parametrize(
    "mode,expected",
    [
        ("token", ("token",)),
        ("password", ("password",)),
        ("both", ("token", "password")),
    ],
)
def test_auth_modes_follow_config(mode, expected):
    plugin = make_plugin()
    plugin.config = {"token": "secret", "auth_mode": mode}

    assert plugin.auth_modes() == expected


def test_login_creates_session_and_authorizes(monkeypatch):
    plugin, manager = auth_plugin(monkeypatch, mode="both")

    result = plugin.login("admin", "pw", now=NOW)

    assert result["username"] == "admin"
    assert result["level"] == AUTH_LEVEL_ADMIN
    assert result["expires"] == NOW + core.SESSION_TTL
    assert manager.calls == [("admin", "pw")]
    request = authorization_request(f"Bearer {result['token']}".encode())
    assert plugin.access_level(request) == AUTH_LEVEL_ADMIN
    assert plugin.auth_identity(request) == (AUTH_LEVEL_ADMIN, "admin")


def test_static_token_is_admin_in_token_mode(monkeypatch):
    plugin, _ = auth_plugin(monkeypatch, mode="token")

    assert plugin.identity_for_token("secret") == (AUTH_LEVEL_ADMIN, "token")


def test_static_token_is_ignored_in_password_mode(monkeypatch):
    plugin, _ = auth_plugin(monkeypatch, mode="password")

    assert plugin.identity_for_token("secret") is None
    assert plugin.is_authorized(authorization_request(b"Bearer secret")) is False


def test_login_rejects_bad_password(monkeypatch):
    plugin, _ = auth_plugin(monkeypatch)

    with pytest.raises(core.InvalidCredentials):
        plugin.login("admin", "nope", remote="ip", now=1000)

    assert plugin.sessions == {}
    assert plugin._login_failures["ip"] == [1000]


def test_login_rejects_empty_credentials(monkeypatch):
    plugin, manager = auth_plugin(monkeypatch)

    with pytest.raises(core.InvalidCredentials):
        plugin.login("", "pw", remote="ip", now=1000)
    with pytest.raises(core.InvalidCredentials):
        plugin.login("admin", "", remote="ip", now=1000)

    assert manager.calls == []
    assert plugin._login_failures["ip"] == [1000, 1000]


def test_login_locks_out_after_five_failures(monkeypatch):
    plugin, _ = auth_plugin(monkeypatch)

    for _ in range(core.LOGIN_MAX_FAILURES):
        with pytest.raises(core.InvalidCredentials):
            plugin.login("admin", "nope", remote="ip", now=1000)

    with pytest.raises(core.TooManyAttempts):
        plugin.login("admin", "pw", remote="ip", now=1000)

    later = 1000 + core.LOGIN_WINDOW + 1
    result = plugin.login("admin", "pw", remote="ip", now=later)
    assert result["username"] == "admin"
    assert plugin._login_failures == {}


def test_login_requires_password_mode(monkeypatch):
    plugin, _ = auth_plugin(monkeypatch, mode="token")

    with pytest.raises(core.AuthDisabled):
        plugin.login("admin", "pw", now=1000)


def test_login_requires_auth_manager(monkeypatch):
    plugin, _ = auth_plugin(monkeypatch)
    monkeypatch.setattr(core.Core, "_auth_manager", lambda self: None)

    with pytest.raises(core.AuthUnavailable):
        plugin.login("admin", "pw", now=1000)


def test_session_expiry_prunes_the_token(monkeypatch):
    plugin, _ = auth_plugin(monkeypatch)

    result = plugin.login("admin", "pw", now=1000)
    plugin.sessions[result["token"]]["expires"] = 0

    assert plugin.access_level_for_token(result["token"]) is None
    assert result["token"] not in plugin.sessions


def test_logout_invalidates_the_session(monkeypatch):
    plugin, _ = auth_plugin(monkeypatch)

    result = plugin.login("admin", "pw", now=NOW)

    assert plugin.access_level_for_token(result["token"]) == AUTH_LEVEL_ADMIN
    assert plugin.logout(result["token"]) == {"ok": True, "session": True}
    assert plugin.access_level_for_token(result["token"]) is None
    assert plugin.logout(result["token"]) == {"ok": True, "session": False}
    assert plugin.logout(None) == {"ok": True, "session": False}


def test_readonly_session_is_not_writable(monkeypatch):
    plugin, _ = auth_plugin(monkeypatch)

    result = plugin.login("guest", "ro", now=NOW)
    level, username = plugin.identity_for_token(result["token"])

    assert level == AUTH_LEVEL_READONLY
    info = plugin.auth_info(level, username)
    assert info["write"] is False
    assert info["username"] == "guest"


def test_auth_info_is_public_without_identity(monkeypatch):
    plugin, _ = auth_plugin(monkeypatch, mode="both", token="")

    info = plugin.auth_info()

    assert info["modes"] == ["token", "password"]
    assert info["token_set"] is False
    assert "authenticated" not in info


def test_set_config_updates_auth_mode_and_clears_sessions(tmp_path, monkeypatch):
    config_file = tmp_path / "mobileui.conf"
    config_file.write_text("{}")
    plugin = make_plugin()
    plugin.config = FakeConfig(
        {"enabled": True, "port": 8113, "token": "secret", "auth_mode": "both"},
        str(config_file),
    )
    plugin.listener = FakePort()
    monkeypatch.setattr(core, "reactor", FakeReactor())
    monkeypatch.setattr(core.Core, "_auth_manager", lambda self: FakeAuthManager())

    result = plugin.login("admin", "pw", now=1000)
    assert result["token"] in plugin.sessions

    updated = plugin.set_config({"auth_mode": "token"})

    assert updated["auth_mode"] == "token"
    assert plugin.auth_modes() == ("token",)
    assert plugin.sessions == {}


def push_plugin(tmp_path):
    plugin = make_plugin()
    plugin.config = FakeConfig(
        {"vapid_subject": "mailto:ops@example.invalid"},
        str(tmp_path / "mobileui.conf"),
    )
    plugin._error_notified = set()
    return plugin


def test_dispatch_push_sends_to_subscriptions(tmp_path, monkeypatch):
    from twisted.internet import threads

    from deluge_mobileui import push

    plugin = push_plugin(tmp_path)
    subscription = {"endpoint": "https://push.example/1"}
    monkeypatch.setattr(push, "load_subscriptions", lambda path: [subscription])
    calls = []
    monkeypatch.setattr(
        push,
        "send_push",
        lambda *args: calls.append(args) or 1,
    )

    class FakeDeferred:
        def addErrback(self, callback):
            self.errback = callback

    def fake_defer(fn, *args):
        fn(*args)
        return FakeDeferred()

    monkeypatch.setattr(threads, "deferToThread", fake_defer)

    plugin._dispatch_push("finished", "Demo", "abc")

    assert calls == [
        (
            plugin.config.config_file,
            {
                "kind": "finished",
                "name": "Demo",
                "message": "",
                "title": "Torrent finished",
                "body": "Demo",
                "url": "/?torrent=abc",
                "tag": "mobileui-abc",
            },
            [subscription],
            "mailto:ops@example.invalid",
        )
    ]


def test_dispatch_push_skips_without_subscriptions(tmp_path, monkeypatch):
    from deluge_mobileui import push

    plugin = push_plugin(tmp_path)
    monkeypatch.setattr(push, "load_subscriptions", lambda path: [])
    monkeypatch.setattr(
        push,
        "send_push",
        lambda *args: (_ for _ in ()).throw(AssertionError("no send")),
    )

    plugin._dispatch_push("finished", "Demo", "abc")


def test_push_events_dedupe_errors(tmp_path, monkeypatch):
    plugin = push_plugin(tmp_path)
    monkeypatch.setattr(
        plugin,
        "_torrent_field",
        lambda torrent_id, key: "Demo" if key == "name" else "Tracker error",
    )
    calls = []
    monkeypatch.setattr(
        plugin,
        "_dispatch_push",
        lambda kind, name, torrent_id, message="": calls.append(
            (kind, name, torrent_id, message)
        ),
    )

    plugin._on_torrent_finished("abc")
    plugin._on_torrent_state_changed("abc", "Error")
    plugin._on_torrent_state_changed("abc", "Error")
    plugin._on_torrent_state_changed("abc", "Downloading")
    plugin._on_torrent_state_changed("abc", "Error")

    assert calls == [
        ("finished", "Demo", "abc", ""),
        ("error", "Demo", "abc", "Tracker error"),
        ("error", "Demo", "abc", "Tracker error"),
    ]


def test_push_config_and_subscriptions_delegate_to_store(tmp_path, monkeypatch):
    from deluge_mobileui import push

    plugin = push_plugin(tmp_path)
    monkeypatch.setattr(push, "public_key", lambda path: "pk")
    monkeypatch.setattr(push, "load_subscriptions", lambda path: [{"endpoint": "a"}])

    assert plugin.get_push_config() == {
        "enabled": True,
        "public_key": "pk",
        "subscriptions": 1,
    }

    calls = []
    monkeypatch.setattr(
        push,
        "add_subscription",
        lambda path, subscription: calls.append(("add", path, subscription))
        or {"subscribed": True, "count": 1},
    )
    monkeypatch.setattr(
        push,
        "remove_subscription",
        lambda path, endpoint: calls.append(("remove", path, endpoint))
        or {"unsubscribed": True},
    )

    assert plugin.subscribe_push({"endpoint": "a"})["count"] == 1
    assert plugin.unsubscribe_push("a") == {"unsubscribed": True}
    assert [call[0] for call in calls] == ["add", "remove"]


def test_test_push_queues_for_a_known_endpoint(tmp_path, monkeypatch):
    from twisted.internet import threads

    from deluge_mobileui import push

    plugin = push_plugin(tmp_path)
    subscription = {"endpoint": "https://push.example/1"}
    monkeypatch.setattr(push, "load_subscriptions", lambda path: [subscription])
    calls = []
    monkeypatch.setattr(push, "send_push", lambda *args: calls.append(args) or 1)

    class FakeDeferred:
        def addErrback(self, callback):
            self.errback = callback

    monkeypatch.setattr(
        threads, "deferToThread", lambda fn, *args: (fn(*args), FakeDeferred())[1]
    )

    assert plugin.test_push(subscription["endpoint"]) == {"queued": True}
    assert calls[0][1]["kind"] == "test"
    assert calls[0][2] == [subscription]

    with pytest.raises(ValueError):
        plugin.test_push("http://push.example/1")
    with pytest.raises(KeyError):
        plugin.test_push("https://push.example/missing")
