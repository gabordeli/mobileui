"""Write-side helpers: pause/resume/remove/label/queue/add."""

import base64
import logging
import os

from deluge.error import AddTorrentError, InvalidTorrentError

from .read import NO_LABEL

log = logging.getLogger(__name__)

QUEUE_ACTIONS = {
    "up": "queue_up",
    "down": "queue_down",
    "top": "queue_top",
    "bottom": "queue_bottom",
}


class BadRequest(ValueError):
    pass


class Conflict(RuntimeError):
    pass


def set_session_paused(core, paused):
    if paused:
        core.pause_session()
    else:
        core.resume_session()
    try:
        actual = bool(core.session.is_paused())
    except (AttributeError, KeyError):
        actual = bool(paused)
    return {"paused": actual}


def pause(core, torrent_id):
    torrent = _torrent(core, torrent_id)
    if torrent.state == "Error":
        raise Conflict("Torrent is in Error state; cannot pause")
    core.pause_torrent(torrent_id)
    return {"id": torrent_id, "state": torrent.state}


def resume(core, torrent_id):
    torrent = _torrent(core, torrent_id)
    core.resume_torrent(torrent_id)
    return {"id": torrent_id, "state": torrent.state}


def remove(core, torrent_id, remove_data=False):
    _torrent(core, torrent_id)
    try:
        removed = core.remove_torrent(torrent_id, bool(remove_data))
    except InvalidTorrentError as ex:
        raise KeyError(torrent_id) from ex
    if not removed:
        raise Conflict("Deluge refused to remove the torrent")
    return {"id": torrent_id, "removed": True, "remove_data": bool(remove_data)}


def queue(core, torrent_id, action):
    method = QUEUE_ACTIONS.get(action)
    if method is None:
        raise BadRequest(
            "action must be one of: " + ", ".join(sorted(QUEUE_ACTIONS))
        )
    _torrent(core, torrent_id)
    getattr(core, method)([torrent_id])
    return {"id": torrent_id, "action": action}


def set_label(core, label_plugin, torrent_id, label):
    _torrent(core, torrent_id)
    if label_plugin is None:
        raise Conflict("Label plugin is not enabled")
    if label in (None, "", NO_LABEL):
        label_id = None
    else:
        if label not in label_plugin.labels:
            raise BadRequest(f"unknown label: {label}")
        label_id = label
    label_plugin.set_torrent(torrent_id, label_id)
    return {"id": torrent_id, "label": label_id or NO_LABEL}


def add(
    core,
    label_plugin,
    magnet=None,
    filename=None,
    filedump=None,
    label=None,
    download_location=None,
    add_paused=False,
):
    if bool(magnet) == bool(filedump):
        raise BadRequest("exactly one of magnet or torrent file is required")
    if magnet and not str(magnet).startswith("magnet:?"):
        raise BadRequest("magnet must start with magnet:?")
    if download_location:
        if not os.path.isabs(download_location):
            raise BadRequest("download_location must be an absolute path")
    if not isinstance(add_paused, bool):
        raise BadRequest("add_paused must be a bool")

    label_id = None
    if label and label != NO_LABEL:
        if label_plugin is None:
            raise Conflict("Label plugin is not enabled")
        if label not in label_plugin.labels:
            raise BadRequest(f"unknown label: {label}")
        label_id = label

    options = {}
    if download_location:
        options["download_location"] = download_location
    if add_paused:
        options["add_paused"] = True

    try:
        if magnet:
            torrent_id = core.add_torrent_magnet(magnet, options)
        else:
            encoded = base64.b64encode(filedump).decode("ascii")
            torrent_id = core.add_torrent_file(
                filename or "upload.torrent", encoded, options
            )
    except AddTorrentError as ex:
        message = str(ex)
        if "already" in message.lower():
            raise Conflict(message) from ex
        raise BadRequest(message) from ex
    except (TypeError, ValueError) as ex:
        raise BadRequest(str(ex)) from ex

    if not torrent_id:
        raise Conflict("Deluge did not return a torrent id")

    if label_id:
        label_plugin.set_torrent(torrent_id, label_id)

    return {
        "id": torrent_id,
        "label": label_id or NO_LABEL,
        "download_location": download_location or "",
    }


def _torrent(core, torrent_id):
    if not torrent_id:
        raise KeyError(torrent_id)
    try:
        return core.torrentmanager[torrent_id]
    except KeyError:
        raise KeyError(torrent_id) from None
