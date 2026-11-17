import json

import pytest

from deluge_mobileui import push

SUBSCRIPTION = {
    "endpoint": "https://push.example/1",
    "keys": {"p256dh": "p256dh-key", "auth": "auth-key"},
}


def test_vapid_key_is_generated_once(tmp_path):
    pytest.importorskip("cryptography")

    config_file = str(tmp_path / "mobileui.conf")
    key1 = push.public_key(config_file)
    key2 = push.public_key(config_file)

    assert key1 == key2
    keyfile = push.vapid_file(config_file)
    assert keyfile.exists()
    assert keyfile.stat().st_mode & 0o777 == 0o600


def test_subscription_store_dedupes_and_removes(tmp_path):
    config_file = str(tmp_path / "mobileui.conf")

    assert push.add_subscription(config_file, SUBSCRIPTION)["count"] == 1
    assert push.add_subscription(config_file, SUBSCRIPTION)["count"] == 1
    assert len(push.load_subscriptions(config_file)) == 1

    assert push.remove_subscription(config_file, SUBSCRIPTION["endpoint"]) == {
        "unsubscribed": True
    }
    assert push.load_subscriptions(config_file) == []
    assert push.remove_subscription(config_file, SUBSCRIPTION["endpoint"]) == {
        "unsubscribed": False
    }


def test_subscription_validation(tmp_path):
    config_file = str(tmp_path / "mobileui.conf")
    bad_inputs = [
        None,
        {},
        {"endpoint": "http://push.example/1", "keys": {"p256dh": "a", "auth": "b"}},
        {"endpoint": "https://127.0.0.1/1", "keys": {"p256dh": "a", "auth": "b"}},
        {"endpoint": "https://localhost/1", "keys": {"p256dh": "a", "auth": "b"}},
        {"endpoint": "https://push.example/1", "keys": {}},
        {"endpoint": "https://push.example/1", "keys": {"p256dh": 1, "auth": "b"}},
    ]

    for bad in bad_inputs:
        with pytest.raises(ValueError):
            push.add_subscription(config_file, bad)


def test_subscription_list_and_remove_by_id(tmp_path):
    config_file = str(tmp_path / "mobileui.conf")
    push.add_subscription(
        config_file,
        {**SUBSCRIPTION, "user_agent": "Mobile Safari"},
    )

    items = push.list_subscriptions(config_file)
    assert items[0]["host"] == "push.example"
    assert items[0]["user_agent"] == "Mobile Safari"
    assert items[0]["id"] == push.subscription_id(SUBSCRIPTION["endpoint"])

    assert push.remove_subscription_by_id(config_file, items[0]["id"]) == {
        "unsubscribed": True
    }
    assert push.list_subscriptions(config_file) == []
    assert push.remove_subscription_by_id(config_file, "missing") == {
        "unsubscribed": False
    }
    with pytest.raises(ValueError):
        push.remove_subscription_by_id(config_file, "")


@pytest.mark.parametrize(
    "endpoint,expected",
    [
        ("https://8.8.8.8/1", True),
        ("https://127.0.0.1/1", False),
        ("https://localhost/1", False),
        ("http://8.8.8.8/1", False),
        ("not-a-url", False),
    ],
)
def test_endpoint_allowed_literals(endpoint, expected):
    assert push.endpoint_allowed(endpoint) is expected


def test_endpoint_allowed_resolves_dns(monkeypatch):
    monkeypatch.setattr(
        "deluge_mobileui.push.socket.getaddrinfo",
        lambda *args, **kwargs: [
            (2, 1, 6, "", ("8.8.8.8", 443)),
        ],
    )
    assert push.endpoint_allowed("https://push.example/1", resolve=True) is True

    monkeypatch.setattr(
        "deluge_mobileui.push.socket.getaddrinfo",
        lambda *args, **kwargs: [
            (2, 1, 6, "", ("192.168.1.10", 443)),
        ],
    )
    assert push.endpoint_allowed("https://push.example/1", resolve=True) is False

    def broken(*args, **kwargs):
        raise OSError("dns down")

    monkeypatch.setattr("deluge_mobileui.push.socket.getaddrinfo", broken)
    assert push.endpoint_allowed("https://push.example/1", resolve=True) is False


def test_store_is_private_and_holds_json(tmp_path):
    config_file = str(tmp_path / "mobileui.conf")
    push.add_subscription(config_file, SUBSCRIPTION)

    path = push.store_file(config_file)
    assert path.stat().st_mode & 0o777 == 0o600
    assert json.loads(path.read_text())[0]["endpoint"] == SUBSCRIPTION["endpoint"]


def test_send_push_marks_dead_subscriptions(tmp_path, monkeypatch):
    config_file = str(tmp_path / "mobileui.conf")
    push.add_subscription(config_file, SUBSCRIPTION)
    push.add_subscription(
        config_file,
        {
            "endpoint": "https://push.example/dead",
            "keys": {"p256dh": "a", "auth": "b"},
        },
    )

    calls = []

    class FakeWebPushError(Exception):
        def __init__(self):
            self.response = type("Response", (), {"status_code": 410})()

    def fake_webpush(subscription_info, data, vapid_private_key, vapid_claims):
        calls.append(subscription_info["endpoint"])
        if subscription_info["endpoint"].endswith("/dead"):
            raise FakeWebPushError()

    monkeypatch.setattr(
        "deluge_mobileui.push._load_webpush",
        lambda: (fake_webpush, FakeWebPushError),
    )
    monkeypatch.setattr(
        "deluge_mobileui.push.endpoint_allowed",
        lambda endpoint, resolve=False: True,
    )

    sent = push.send_push(
        config_file, {"title": "x"}, subject="mailto:test@example.invalid"
    )

    assert sent == 1
    assert calls == ["https://push.example/dead", SUBSCRIPTION["endpoint"]]
    assert [item["endpoint"] for item in push.load_subscriptions(config_file)] == [
        SUBSCRIPTION["endpoint"]
    ]


def test_send_push_without_pywebpush(tmp_path, monkeypatch):
    config_file = str(tmp_path / "mobileui.conf")
    push.add_subscription(config_file, SUBSCRIPTION)

    def missing():
        raise ImportError("no pywebpush")

    monkeypatch.setattr("deluge_mobileui.push._load_webpush", missing)

    assert push.send_push(config_file, {"title": "x"}) == 0
