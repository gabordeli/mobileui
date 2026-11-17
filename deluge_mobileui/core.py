"""Core plugin: runs a Twisted HTTP server inside the deluged reactor."""

import hmac
import logging
import os
import secrets
import time

import deluge.component as component
from deluge.common import AUTH_LEVEL_ADMIN, AUTH_LEVEL_NORMAL
from deluge.configmanager import ConfigManager
from deluge.core.rpcserver import export
from deluge.error import AuthenticationRequired, BadLoginError
from deluge.plugins.pluginbase import CorePluginBase
from twisted.internet import defer, reactor
from twisted.web.server import Site

from .auth import (
    AUTH_MODES,
    LOGIN_MAX_FAILURES,
    LOGIN_WINDOW,
    SESSION_TTL,
    AuthDisabled,
    AuthUnavailable,
    InvalidCredentials,
    TooManyAttempts,
    bearer_token,
)
from .http import build_root
from .version import __version__

try:
    import sentry_sdk
except ImportError:
    sentry_sdk = None

try:
    from sentry_sdk.integrations.twisted import TwistedIntegration
except ImportError:
    TwistedIntegration = None

log = logging.getLogger(__name__)

CONFIG_FILE = "mobileui.conf"
CONFIG_DEFAULTS = {
    "enabled": True,
    "port": 8113,
    "token": "",
    "auth_mode": "token",
    "sentry_dsn": "",
}


class Core(CorePluginBase):
    def __init__(self, plugin_name):
        super().__init__(plugin_name)
        self.config = None
        self.site = None
        self.listener = None
        self.events = None
        self.sessions = {}
        self._login_failures = {}

    def enable(self):
        self.config = ConfigManager(CONFIG_FILE, defaults=CONFIG_DEFAULTS)
        self._ensure_config_file()
        if not self.config["enabled"]:
            log.info("MobileUi disabled by mobileui.conf; HTTP server not started")
            return
        self._init_sentry()
        self._start_listener(int(self.config["port"]))
        self._start_events()

    def disable(self):
        self._stop_events()
        self._flush_sentry()
        return self._stop_listener()

    def update(self):
        pass

    def list_torrents(self, **kwargs):
        from . import read

        return read.list_torrents(component.get("Core"), self._label_plugin(), **kwargs)

    def get_torrent(self, torrent_id):
        from . import read

        return read.get_torrent(component.get("Core"), self._label_plugin(), torrent_id)

    def get_torrent_files(self, torrent_id, offset=0, limit=100):
        from . import read

        return read.get_files(component.get("Core"), torrent_id, offset, limit)

    def get_session(self):
        from . import read

        return read.get_session(component.get("Core"))

    def get_labels(self):
        from . import read

        return read.get_labels(self._label_plugin(), component.get("Core"))

    def pause_session(self):
        from . import write

        return write.set_session_paused(component.get("Core"), True)

    def resume_session(self):
        from . import write

        return write.set_session_paused(component.get("Core"), False)

    def pause_torrent(self, torrent_id):
        from . import write

        return write.pause(component.get("Core"), torrent_id)

    def resume_torrent(self, torrent_id):
        from . import write

        return write.resume(component.get("Core"), torrent_id)

    def remove_torrent(self, torrent_id, remove_data=False):
        from . import write

        return write.remove(component.get("Core"), torrent_id, remove_data)

    def queue_torrent(self, torrent_id, action):
        from . import write

        return write.queue(component.get("Core"), torrent_id, action)

    def set_torrent_label(self, torrent_id, label):
        from . import write

        return write.set_label(
            component.get("Core"), self._label_plugin(), torrent_id, label
        )

    def add_torrent(self, **kwargs):
        from . import write

        return write.add(component.get("Core"), self._label_plugin(), **kwargs)

    def subscribe_events(self, request):
        if self.events is None:
            self._start_events()
        if self.events is None:
            raise RuntimeError("event stream is not available")
        return self.events.subscribe(request)

    def _label_plugin(self):
        try:
            return component.get("CorePlugin.Label")
        except KeyError:
            return None

    def _start_events(self):
        if self.events is not None:
            return
        from .events import EventBroadcaster

        broadcaster = EventBroadcaster(self)
        try:
            broadcaster.start()
        except Exception:
            log.exception("MobileUi failed to start the event stream")
            return
        self.events = broadcaster

    def _stop_events(self):
        if self.events is not None:
            self.events.stop()
            self.events = None

    def _init_sentry(self):
        if sentry_sdk is None:
            if str(self.config.get("sentry_dsn", "")).strip():
                log.warning(
                    "MobileUi: sentry_dsn is set but sentry-sdk is not installed"
                )
            return
        dsn = str(self.config.get("sentry_dsn", "")).strip()
        if not dsn:
            return
        integrations = [TwistedIntegration()] if TwistedIntegration else []
        try:
            sentry_sdk.init(
                dsn=dsn,
                release=__version__,
                environment="production",
                integrations=integrations,
                traces_sample_rate=0.0,
                send_default_pii=False,
            )
        except Exception:
            log.warning("MobileUi: Sentry initialization failed", exc_info=True)
            return
        log.info("MobileUi Sentry enabled (release %s)", __version__)

    def _flush_sentry(self):
        if sentry_sdk is None:
            return
        try:
            sentry_sdk.flush(timeout=2)
        except Exception:
            log.warning("MobileUi: Sentry flush failed", exc_info=True)

    @export
    def set_config(self, config):
        """Update auth/token/port/enabled/sentry_dsn; apply without a restart."""
        if not isinstance(config, dict):
            raise TypeError("config must be a dict")
        unknown = set(config) - set(CONFIG_DEFAULTS)
        if unknown:
            raise ValueError(f"unknown config keys: {', '.join(sorted(unknown))}")

        updates = {}
        if "enabled" in config:
            if not isinstance(config["enabled"], bool):
                raise TypeError("enabled must be a bool")
            updates["enabled"] = config["enabled"]
        if "port" in config:
            port = int(config["port"])
            if not 1 <= port <= 65535:
                raise ValueError("port must be between 1 and 65535")
            updates["port"] = port
        if "token" in config:
            if not isinstance(config["token"], str):
                raise TypeError("token must be a string")
            updates["token"] = config["token"]
        if "auth_mode" in config:
            if not isinstance(config["auth_mode"], str):
                raise TypeError("auth_mode must be a string")
            if config["auth_mode"] not in AUTH_MODES:
                raise ValueError("auth_mode must be one of: " + ", ".join(AUTH_MODES))
            updates["auth_mode"] = config["auth_mode"]
        if "sentry_dsn" in config:
            if not isinstance(config["sentry_dsn"], str):
                raise TypeError("sentry_dsn must be a string")
            updates["sentry_dsn"] = config["sentry_dsn"]

        old = {key: self.config[key] for key in updates}
        for key, value in updates.items():
            self.config[key] = value
        self.config.save()
        self._secure_config_file()
        try:
            self._apply_runtime(old)
        except Exception:
            for key, value in old.items():
                self.config[key] = value
            self.config.save()
            log.error("MobileUi config change failed, reverted", exc_info=True)
            raise

        if "auth_mode" in updates and "password" not in self.auth_modes():
            self.sessions.clear()

        if "sentry_dsn" in updates:
            self._init_sentry()

        log.info(
            "MobileUi config updated "
            "(port=%s, enabled=%s, auth_mode=%s, token_set=%s, sentry_set=%s)",
            self.config["port"],
            self.config["enabled"],
            self.config.get("auth_mode", "token"),
            bool(self.config["token"]),
            bool(self.config.get("sentry_dsn", "")),
        )
        return {
            "port": int(self.config["port"]),
            "enabled": bool(self.config["enabled"]),
            "auth_mode": str(self.config.get("auth_mode", "token")),
            "token_set": bool(self.config["token"]),
            "sentry_set": bool(self.config.get("sentry_dsn", "")),
        }

    def auth_modes(self):
        if not self.config:
            return ("token",)
        mode = str(self.config.get("auth_mode", "token"))
        modes = []
        if mode in ("token", "both"):
            modes.append("token")
        if mode in ("password", "both"):
            modes.append("password")
        return tuple(modes)

    def auth_info(self, level=None, username=""):
        token = str(self.config.get("token", "")).strip() if self.config else ""
        info = {
            "mode": str(self.config.get("auth_mode", "token"))
            if self.config
            else "token",
            "modes": list(self.auth_modes()),
            "token_set": bool(token),
        }
        if level is not None:
            info.update(
                {
                    "authenticated": True,
                    "username": username,
                    "level": int(level),
                    "write": int(level) >= AUTH_LEVEL_NORMAL,
                }
            )
        return info

    def identity_for_token(self, token):
        if not self.config or not token:
            return None
        modes = self.auth_modes()
        if "token" in modes and self.is_token_valid(token):
            return AUTH_LEVEL_ADMIN, "token"
        if "password" in modes:
            session = self.sessions.get(str(token))
            if session is None:
                return None
            if session["expires"] <= time.time():
                self.sessions.pop(str(token), None)
                return None
            return int(session["level"]), str(session["username"])
        return None

    def access_level_for_token(self, token):
        identity = self.identity_for_token(token)
        return None if identity is None else identity[0]

    def auth_identity(self, request):
        return self.identity_for_token(bearer_token(request))

    def access_level(self, request):
        identity = self.auth_identity(request)
        return None if identity is None else identity[0]

    def is_authorized(self, request):
        return self.auth_identity(request) is not None

    def login(self, username, password, remote="", now=None):
        if "password" not in self.auth_modes():
            raise AuthDisabled("password login is not enabled")
        if not isinstance(username, str) or not isinstance(password, str):
            raise TypeError("username and password must be strings")
        now = time.time() if now is None else float(now)
        failures = self._login_failures_for(remote, now)
        if len(failures) >= LOGIN_MAX_FAILURES:
            raise TooManyAttempts("too many failed login attempts")

        name = username.strip()
        if not name or not password:
            failures.append(now)
            raise InvalidCredentials("invalid username or password")

        manager = self._auth_manager()
        if manager is None:
            raise AuthUnavailable("Deluge AuthManager is not available")
        try:
            level = manager.authorize(name, password)
        except (AuthenticationRequired, BadLoginError):
            failures.append(now)
            raise InvalidCredentials("invalid username or password") from None

        self._login_failures.pop(remote, None)
        self._prune_sessions(now)
        token = secrets.token_urlsafe(32)
        expires = now + SESSION_TTL
        self.sessions[token] = {
            "username": name,
            "level": int(level),
            "expires": expires,
        }
        log.info("MobileUi login: user=%s level=%s", name, level)
        return {
            "token": token,
            "username": name,
            "level": int(level),
            "expires": int(expires),
        }

    def logout(self, token):
        removed = self.sessions.pop(str(token), None) if token else None
        return {"ok": True, "session": removed is not None}

    def _auth_manager(self):
        try:
            return component.get("AuthManager")
        except KeyError:
            return None

    def _login_failures_for(self, remote, now):
        entries = [
            stamp
            for stamp in self._login_failures.get(remote, ())
            if stamp > now - LOGIN_WINDOW
        ]
        self._login_failures[remote] = entries
        return entries

    def _prune_sessions(self, now):
        expired = [
            token
            for token, session in self.sessions.items()
            if session["expires"] <= now
        ]
        for token in expired:
            self.sessions.pop(token, None)

    def is_token_valid(self, token):
        if token is None:
            return False
        if isinstance(token, bytes):
            token = token.decode("utf-8", "replace")
        configured = str(self.config["token"]) if self.config else ""
        if not configured or not token:
            return False
        return hmac.compare_digest(
            str(token).encode("utf-8"), configured.encode("utf-8")
        )

    def _apply_runtime(self, old):
        if not self.config["enabled"]:
            self._stop_listener()
            self._stop_events()
            return
        port = int(self.config["port"])
        if self.listener is None:
            self._start_listener(port)
            self._start_events()
            return
        if port != int(old.get("port", port)):
            self._stop_listener()
            try:
                self._start_listener(port)
            except Exception:
                self._start_listener(int(old["port"]))
                raise

    def _start_listener(self, port):
        self.site = Site(build_root(self))
        try:
            self.listener = reactor.listenTCP(port, self.site, interface="0.0.0.0")
        except Exception:
            self.site = None
            log.exception("MobileUi failed to listen on port %s", port)
            raise
        log.info("MobileUi %s listening on 0.0.0.0:%s", __version__, port)

    def _stop_listener(self):
        if self.listener is None:
            return None
        listener, self.listener = self.listener, None
        self.site = None
        log.info("MobileUi HTTP server stopping")
        return defer.maybeDeferred(listener.stopListening)

    def _ensure_config_file(self):
        if not os.path.exists(self.config.config_file):
            self.config.save()
        self._secure_config_file()

    def _secure_config_file(self):
        try:
            os.chmod(self.config.config_file, 0o600)
        except OSError as ex:
            log.warning(
                "MobileUi: could not set permissions on %s: %s",
                self.config.config_file,
                ex,
            )
