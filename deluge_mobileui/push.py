"""Web Push: VAPID keys, the subscription store and delivery."""

import base64
import json
import logging
import os
import tempfile
import time
from pathlib import Path

log = logging.getLogger(__name__)

MAX_SUBSCRIPTIONS = 20


def _config_dir(config_file):
    return Path(config_file).resolve().parent


def vapid_file(config_file):
    return _config_dir(config_file) / "mobileui-vapid.pem"


def store_file(config_file):
    return _config_dir(config_file) / "mobileui-push.json"


def ensure_vapid(config_file):
    path = vapid_file(config_file)
    if path.exists():
        return path
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import ec

    key = ec.generate_private_key(ec.SECP256R1())
    pem = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "wb") as fh:
        fh.write(pem)
    os.chmod(path, 0o600)
    return path


def public_key(config_file):
    from cryptography.hazmat.primitives import serialization

    path = ensure_vapid(config_file)
    key = serialization.load_pem_private_key(path.read_bytes(), password=None)
    raw = key.public_key().public_bytes(
        serialization.Encoding.X962,
        serialization.PublicFormat.UncompressedPoint,
    )
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def load_subscriptions(config_file):
    try:
        data = json.loads(store_file(config_file).read_text())
    except (OSError, ValueError):
        return []
    return data if isinstance(data, list) else []


def save_subscriptions(config_file, subscriptions):
    path = store_file(config_file)
    payload = json.dumps(subscriptions[:MAX_SUBSCRIPTIONS])
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=".push-", text=True)
    try:
        with os.fdopen(fd, "w") as fh:
            fh.write(payload)
        os.chmod(tmp, 0o600)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def add_subscription(config_file, subscription):
    if not isinstance(subscription, dict):
        raise ValueError("subscription must be an object")
    endpoint = subscription.get("endpoint")
    keys = subscription.get("keys")
    if not isinstance(endpoint, str) or not endpoint.startswith("https://"):
        raise ValueError("invalid subscription endpoint")
    if not isinstance(keys, dict):
        raise ValueError("subscription keys are required")
    p256dh = keys.get("p256dh")
    auth = keys.get("auth")
    if not isinstance(p256dh, str) or not isinstance(auth, str):
        raise ValueError("invalid subscription keys")

    entry = {
        "endpoint": endpoint,
        "keys": {"p256dh": p256dh, "auth": auth},
        "added": int(time.time()),
    }
    subscriptions = [
        item
        for item in load_subscriptions(config_file)
        if item.get("endpoint") != endpoint
    ]
    subscriptions.insert(0, entry)
    save_subscriptions(config_file, subscriptions)
    return {"subscribed": True, "count": len(subscriptions[:MAX_SUBSCRIPTIONS])}


def remove_subscription(config_file, endpoint):
    if not isinstance(endpoint, str):
        raise ValueError("endpoint must be a string")
    subscriptions = load_subscriptions(config_file)
    kept = [item for item in subscriptions if item.get("endpoint") != endpoint]
    save_subscriptions(config_file, kept)
    return {"unsubscribed": len(kept) != len(subscriptions)}


def _load_webpush():
    from pywebpush import WebPushException, webpush

    return webpush, WebPushException


def send_push(
    config_file,
    payload,
    subscriptions=None,
    subject="mailto:admin@example.invalid",
):
    try:
        webpush, webpush_error = _load_webpush()
    except ImportError:
        log.warning("MobileUi push: pywebpush is not installed")
        return 0

    targets = (
        subscriptions
        if subscriptions is not None
        else load_subscriptions(config_file)
    )
    if not targets:
        return 0
    try:
        keyfile = str(ensure_vapid(config_file))
    except Exception:
        log.warning("MobileUi push: VAPID key unavailable", exc_info=True)
        return 0

    data = json.dumps(payload)
    sent = 0
    dead = []
    for item in targets:
        try:
            webpush(
                subscription_info=item,
                data=data,
                vapid_private_key=keyfile,
                vapid_claims={"sub": subject},
            )
            sent += 1
        except webpush_error as ex:
            status = getattr(getattr(ex, "response", None), "status_code", None)
            if status in (404, 410):
                dead.append(item.get("endpoint"))
            else:
                log.warning("MobileUi push failed (status %s)", status, exc_info=True)
        except Exception:
            log.warning("MobileUi push failed", exc_info=True)

    if dead:
        remaining = [
            item
            for item in load_subscriptions(config_file)
            if item.get("endpoint") not in dead
        ]
        save_subscriptions(config_file, remaining)
    return sent
