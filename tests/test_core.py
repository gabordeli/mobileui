import pytest
from twisted.web.test.requesthelper import DummyRequest

from deluge_mobileui import core

from .test_http import FakeConfig, FakePort, FakeReactor


def make_plugin():
    plugin = object.__new__(core.Core)
    plugin.config = None
    plugin.site = None
    plugin.listener = None
    plugin.events = None
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
