"""Twisted HTTP resources for the MobileUi plugin."""

import base64
import json
import logging
from pathlib import Path

from twisted.web.resource import Resource
from twisted.web.static import File

from .version import __version__
from .write import BadRequest, Conflict

log = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parent / "data"


def json_bytes(payload):
    return json.dumps(payload, separators=(",", ":")).encode("utf-8")


def query_arg(request, name, default=None):
    args = getattr(request, "args", {})
    values = args.get(name.encode("utf-8"))
    if not values:
        return default
    return values[0].decode("utf-8")


def is_json_request(request):
    header = request.getHeader(b"content-type") or b""
    if isinstance(header, str):
        header = header.encode("utf-8")
    return header.split(b";")[0].strip().lower() == b"application/json"


def read_json_body(request):
    content = getattr(request, "content", None)
    raw = content.read() if content is not None else b""
    if not raw:
        return {}
    try:
        data = json.loads(raw)
    except (TypeError, ValueError, UnicodeDecodeError) as ex:
        raise BadRequest(f"invalid JSON body: {ex}") from ex
    if not isinstance(data, dict):
        raise BadRequest("JSON body must be an object")
    return data


class JsonResource(Resource):
    def write_json(self, request, status, payload, headers=None):
        request.setResponseCode(status)
        request.setHeader(b"content-type", b"application/json; charset=utf-8")
        request.setHeader(b"cache-control", b"no-store")
        for name, value in (headers or {}).items():
            request.setHeader(name, value)
        return json_bytes(payload)


class HealthResource(JsonResource):
    isLeaf = True

    def __init__(self, plugin):
        super().__init__()
        self.plugin = plugin

    def render_GET(self, request):
        config = self.plugin.config or {}
        return self.write_json(
            request,
            200,
            {
                "ok": True,
                "version": __version__,
                "port": config.get("port"),
            },
        )


class UnauthorizedResource(JsonResource):
    isLeaf = True

    def render(self, request):
        return self.write_json(
            request,
            401,
            {
                "error": "unauthorized",
                "message": "Missing or invalid bearer token",
            },
            {b"www-authenticate": b'Bearer realm="mobileui"'},
        )


class NotFoundResource(JsonResource):
    isLeaf = True

    def __init__(self, message="No such endpoint"):
        super().__init__()
        self.message = message

    def render(self, request):
        return self.write_json(
            request,
            404,
            {"error": "not_found", "message": self.message},
        )


class ApiJsonResource(JsonResource):
    def __init__(self, plugin):
        super().__init__()
        self.plugin = plugin

    def unauthorized(self, request):
        if self.plugin.is_authorized(request):
            return None
        return UnauthorizedResource().render(request)

    def api_error(self, request, ex):
        if isinstance(ex, KeyError):
            return self.write_json(
                request,
                404,
                {"error": "not_found", "message": "Unknown torrent"},
            )
        if isinstance(ex, Conflict):
            return self.write_json(
                request,
                409,
                {"error": "conflict", "message": str(ex)},
            )
        if isinstance(ex, (ValueError, TypeError)):
            return self.write_json(
                request,
                400,
                {"error": "bad_request", "message": str(ex)},
            )
        return self.internal_error(request)

    def internal_error(self, request):
        log.exception("MobileUi: API request failed")
        return self.write_json(
            request,
            500,
            {"error": "internal_error", "message": "Internal server error"},
        )


class SessionResource(ApiJsonResource):
    isLeaf = True

    def render_GET(self, request):
        unauthorized = self.unauthorized(request)
        if unauthorized is not None:
            return unauthorized
        try:
            payload = self.plugin.get_session()
        except Exception:
            return self.internal_error(request)
        return self.write_json(request, 200, payload)


class LabelsResource(ApiJsonResource):
    isLeaf = True

    def render_GET(self, request):
        unauthorized = self.unauthorized(request)
        if unauthorized is not None:
            return unauthorized
        try:
            payload = self.plugin.get_labels()
        except Exception:
            return self.internal_error(request)
        return self.write_json(request, 200, payload)


class TorrentActionResource(ApiJsonResource):
    isLeaf = True

    def __init__(self, plugin, torrent_id, action):
        super().__init__(plugin)
        self.torrent_id = torrent_id
        self.action = action

    def render_POST(self, request):
        unauthorized = self.unauthorized(request)
        if unauthorized is not None:
            return unauthorized
        try:
            if self.action == "pause":
                payload = self.plugin.pause_torrent(self.torrent_id)
            else:
                payload = self.plugin.resume_torrent(self.torrent_id)
        except (KeyError, Conflict, ValueError, TypeError) as ex:
            return self.api_error(request, ex)
        except Exception:
            return self.internal_error(request)
        return self.write_json(request, 200, payload)


class RemoveActionResource(ApiJsonResource):
    isLeaf = True

    def __init__(self, plugin, torrent_id):
        super().__init__(plugin)
        self.torrent_id = torrent_id

    def render_POST(self, request):
        unauthorized = self.unauthorized(request)
        if unauthorized is not None:
            return unauthorized
        try:
            body = read_json_body(request)
            remove_data = body.get("remove_data", False)
            if not isinstance(remove_data, bool):
                raise BadRequest("remove_data must be a bool")
            payload = self.plugin.remove_torrent(self.torrent_id, remove_data)
        except (KeyError, Conflict, ValueError, TypeError) as ex:
            return self.api_error(request, ex)
        except Exception:
            return self.internal_error(request)
        return self.write_json(request, 200, payload)


class QueueActionResource(ApiJsonResource):
    isLeaf = True

    def __init__(self, plugin, torrent_id):
        super().__init__(plugin)
        self.torrent_id = torrent_id

    def render_POST(self, request):
        unauthorized = self.unauthorized(request)
        if unauthorized is not None:
            return unauthorized
        try:
            body = read_json_body(request)
            action = body.get("action")
            if not isinstance(action, str):
                raise BadRequest("action is required")
            payload = self.plugin.queue_torrent(self.torrent_id, action)
        except (KeyError, Conflict, ValueError, TypeError) as ex:
            return self.api_error(request, ex)
        except Exception:
            return self.internal_error(request)
        return self.write_json(request, 200, payload)


class TorrentResource(ApiJsonResource):
    def __init__(self, plugin, torrent_id):
        super().__init__(plugin)
        self.torrent_id = torrent_id

    def getChild(self, path, request):
        if not self.plugin.is_authorized(request):
            return UnauthorizedResource()
        action = path.decode("utf-8")
        if action in {"pause", "resume"}:
            return TorrentActionResource(self.plugin, self.torrent_id, action)
        if action == "remove":
            return RemoveActionResource(self.plugin, self.torrent_id)
        if action == "queue":
            return QueueActionResource(self.plugin, self.torrent_id)
        return NotFoundResource()

    def render_GET(self, request):
        unauthorized = self.unauthorized(request)
        if unauthorized is not None:
            return unauthorized
        try:
            payload = self.plugin.get_torrent(self.torrent_id)
        except KeyError:
            return self.write_json(
                request,
                404,
                {"error": "not_found", "message": "Unknown torrent"},
            )
        except Exception:
            return self.internal_error(request)
        return self.write_json(request, 200, payload)

    def render_PATCH(self, request):
        unauthorized = self.unauthorized(request)
        if unauthorized is not None:
            return unauthorized
        try:
            body = read_json_body(request)
            if "label" not in body:
                raise BadRequest("label is required")
            payload = self.plugin.set_torrent_label(self.torrent_id, body["label"])
        except (KeyError, Conflict, ValueError, TypeError) as ex:
            return self.api_error(request, ex)
        except Exception:
            return self.internal_error(request)
        return self.write_json(request, 200, payload)


class TorrentsResource(ApiJsonResource):
    def getChild(self, path, request):
        if not self.plugin.is_authorized(request):
            return UnauthorizedResource()
        return TorrentResource(self.plugin, path.decode("utf-8"))

    def render_GET(self, request):
        unauthorized = self.unauthorized(request)
        if unauthorized is not None:
            return unauthorized
        try:
            offset = int(query_arg(request, "offset", "0"))
            limit = int(query_arg(request, "limit", "50"))
            payload = self.plugin.list_torrents(
                state=query_arg(request, "state"),
                label=query_arg(request, "label"),
                q=query_arg(request, "q"),
                sort=query_arg(request, "sort", "name"),
                offset=offset,
                limit=limit,
            )
        except (TypeError, ValueError) as ex:
            return self.api_error(request, ex)
        except Exception:
            return self.internal_error(request)
        return self.write_json(request, 200, payload)

    def render_POST(self, request):
        unauthorized = self.unauthorized(request)
        if unauthorized is not None:
            return unauthorized
        try:
            if is_json_request(request):
                body = read_json_body(request)
                filedump = None
                if body.get("file_base64") is not None:
                    try:
                        filedump = base64.b64decode(body["file_base64"], validate=True)
                    except (TypeError, ValueError) as ex:
                        raise BadRequest(f"invalid file_base64: {ex}") from ex
                payload = self.plugin.add_torrent(
                    magnet=body.get("magnet"),
                    filename=body.get("filename"),
                    filedump=filedump,
                    label=body.get("label"),
                    download_location=body.get("download_location"),
                    add_paused=body.get("add_paused", False),
                )
            else:
                content = getattr(request, "content", None)
                raw = content.read() if content is not None else b""
                if not raw:
                    raise BadRequest("empty torrent file")
                payload = self.plugin.add_torrent(
                    filename=query_arg(request, "filename", "upload.torrent"),
                    filedump=raw,
                    label=query_arg(request, "label"),
                    download_location=query_arg(request, "download_location"),
                    add_paused=query_arg(request, "add_paused", "false").lower()
                    == "true",
                )
        except (KeyError, Conflict, ValueError, TypeError) as ex:
            return self.api_error(request, ex)
        except Exception:
            return self.internal_error(request)
        return self.write_json(request, 201, payload)


class EventsResource(ApiJsonResource):
    isLeaf = True

    def render_GET(self, request):
        token = query_arg(request, "token")
        if not (
            self.plugin.is_authorized(request) or self.plugin.is_token_valid(token)
        ):
            return UnauthorizedResource().render(request)
        request.setHeader(b"content-type", b"text/event-stream; charset=utf-8")
        request.setHeader(b"cache-control", b"no-cache")
        request.setHeader(b"connection", b"keep-alive")
        request.setHeader(b"x-accel-buffering", b"no")
        try:
            return self.plugin.subscribe_events(request)
        except Exception:
            return self.internal_error(request)


class ApiRootResource(JsonResource):
    def __init__(self, plugin):
        super().__init__()
        self.plugin = plugin
        self.putChild(b"session", SessionResource(plugin))
        self.putChild(b"labels", LabelsResource(plugin))
        self.putChild(b"torrents", TorrentsResource(plugin))
        self.putChild(b"events", EventsResource(plugin))

    def getChild(self, path, request):
        if not self.plugin.is_authorized(request):
            return UnauthorizedResource()
        return NotFoundResource()

    def render(self, request):
        if not self.plugin.is_authorized(request):
            return UnauthorizedResource().render(request)
        return self.write_json(
            request,
            200,
            {
                "version": __version__,
                "endpoints": [
                    "/api/session",
                    "/api/labels",
                    "/api/torrents",
                    "/api/torrents/{id}",
                    "/api/events",
                ],
            },
        )


class RootResource(JsonResource):
    def __init__(self, plugin):
        super().__init__()
        self.plugin = plugin
        self.putChild(b"health", HealthResource(plugin))
        self.putChild(b"api", ApiRootResource(plugin))
        index_path = DATA_DIR / "index.html"
        self.static = File(str(DATA_DIR)) if index_path.is_file() else None
        self.index = File(str(index_path)) if index_path.is_file() else None

    def getChild(self, path, request):
        if self.static is not None:
            return self.static.getChild(path, request)
        return NotFoundResource()

    def render_GET(self, request):
        if self.index is not None:
            return self.index.render_GET(request)
        return self.write_json(
            request,
            404,
            {"error": "not_found", "message": "SPA is not built"},
        )

    def render_HEAD(self, request):
        return self.render_GET(request)


def build_root(plugin):
    return RootResource(plugin)
