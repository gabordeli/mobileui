"""SSE broadcaster for live torrent/session updates."""

import json
import logging

from twisted.internet import task
from twisted.web.server import NOT_DONE_YET

from . import read
from .version import __version__

log = logging.getLogger(__name__)

PROGRESS_KEYS = [
    "progress",
    "download_payload_rate",
    "upload_payload_rate",
    "eta",
]
HEARTBEAT_SECONDS = 15
TICK_SECONDS = 1.0


class EventBroadcaster:
    def __init__(self, plugin):
        self.plugin = plugin
        self.core = None
        self.subscribers = set()
        self.pending = {}
        self.pending_added = set()
        self.pending_removed = set()
        self.last_progress = {}
        self.last_session = {}
        self.primed = False
        self.loop = None
        self.ticks = 0
        self.session_dirty = False
        self.handlers = {
            "TorrentStateChangedEvent": self._on_state,
            "TorrentAddedEvent": self._on_added,
            "TorrentRemovedEvent": self._on_removed,
            "SessionPausedEvent": self._on_session,
            "SessionResumedEvent": self._on_session,
        }

    def start(self):
        from deluge import component

        self.core = component.get("Core")
        event_manager = component.get("EventManager")
        for name, handler in self.handlers.items():
            event_manager.register_event_handler(name, handler)
        self.loop = task.LoopingCall(self._tick)
        self.loop.start(TICK_SECONDS, now=False)
        log.info("MobileUi event stream started")

    def stop(self):
        from deluge import component

        if self.loop is not None:
            self.loop.stop()
            self.loop = None
        try:
            event_manager = component.get("EventManager")
        except KeyError:
            event_manager = None
        if event_manager is not None:
            for name, handler in self.handlers.items():
                event_manager.deregister_event_handler(name, handler)
        for request in list(self.subscribers):
            self._close(request, "plugin disabled")
        self.subscribers.clear()
        log.info("MobileUi event stream stopped")

    def subscribe(self, request):
        self.subscribers.add(request)
        request.notifyFinish().addBoth(self._on_finish, request)
        num_torrents = 0
        if self.core is not None:
            num_torrents = len(self.core.torrentmanager.torrents)
        self._write(
            request,
            "hello",
            {
                "version": __version__,
                "heartbeat": HEARTBEAT_SECONDS,
                "num_torrents": num_torrents,
            },
        )
        return NOT_DONE_YET

    def _on_finish(self, result, request):
        self.subscribers.discard(request)

    def _on_state(self, torrent_id, state):
        self.pending.setdefault(torrent_id, {})["state"] = state

    def _on_added(self, torrent_id, from_state):
        self.pending_added.add(torrent_id)

    def _on_removed(self, torrent_id):
        self.pending_removed.add(torrent_id)
        self.pending.pop(torrent_id, None)
        self.last_progress.pop(torrent_id, None)

    def _on_session(self, *args):
        # The next tick re-reads the session and emits the changed fields.
        self.session_dirty = True

    def _tick(self):
        try:
            self._tick_inner()
        except Exception:
            log.exception("MobileUi event tick failed")

    def _tick_inner(self):
        self.ticks += 1
        if not self.subscribers or self.core is None:
            self.pending.clear()
            self.pending_added.clear()
            self.pending_removed.clear()
            self.last_progress = {}
            self.last_session = {}
            self.primed = False
            self.session_dirty = False
            return

        deltas = []
        for torrent_id in sorted(self.pending_added):
            deltas.append({"type": "added", "id": torrent_id, "fields": {}})
        for torrent_id, fields in self.pending.items():
            if torrent_id in self.pending_removed:
                continue
            deltas.append({"type": "state", "id": torrent_id, "fields": fields})
        for torrent_id in sorted(self.pending_removed):
            deltas.append({"type": "removed", "id": torrent_id, "fields": {}})
        self.pending.clear()
        self.pending_added.clear()
        self.pending_removed.clear()

        current = self._progress_snapshot()
        if not self.primed:
            self.last_progress = current
            self.primed = True
        else:
            for torrent_id, fields in current.items():
                if self.last_progress.get(torrent_id) != fields:
                    deltas.append(
                        {"type": "progress", "id": torrent_id, "fields": fields}
                    )
            self.last_progress = current

        session = read.get_session(self.core)
        if self.session_dirty:
            deltas.append({"type": "session", "id": None, "fields": session})
            self.session_dirty = False
        elif self.last_session:
            changed = {
                key: value
                for key, value in session.items()
                if self.last_session.get(key) != value
            }
            if changed:
                deltas.append({"type": "session", "id": None, "fields": changed})
        self.last_session = session

        for delta in deltas:
            event_name = "session" if delta["type"] == "session" else "torrent"
            for request in list(self.subscribers):
                self._write(request, event_name, delta)

        if self.ticks % HEARTBEAT_SECONDS == 0:
            for request in list(self.subscribers):
                self._write_raw(request, b": heartbeat\n\n")

    def _progress_snapshot(self):
        snapshot = {}
        for torrent_id, torrent in self.core.torrentmanager.torrents.items():
            try:
                snapshot[torrent_id] = torrent.get_status(PROGRESS_KEYS, update=False)
            except KeyError:
                continue
        return snapshot

    def _write(self, request, event, payload):
        data = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        return self._write_raw(
            request, b"event: " + event.encode("utf-8") + b"\ndata: " + data + b"\n\n"
        )

    def _write_raw(self, request, data):
        if getattr(request, "finished", False):
            self.subscribers.discard(request)
            return False
        try:
            request.write(data)
        except Exception:
            self.subscribers.discard(request)
            return False
        return True

    def _close(self, request, reason):
        self._write(request, "bye", {"reason": reason})
        self.subscribers.discard(request)
        try:
            request.finish()
        except Exception:
            pass
