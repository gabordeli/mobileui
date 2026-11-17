"""Auth primitives shared by the plugin core and the HTTP layer."""

AUTH_MODES = ("token", "password", "both")
SESSION_TTL = 30 * 24 * 60 * 60
LOGIN_WINDOW = 60
LOGIN_MAX_FAILURES = 5


class AuthError(Exception):
    pass


class AuthDisabled(AuthError):
    pass


class AuthUnavailable(AuthError):
    pass


class InvalidCredentials(AuthError):
    pass


class TooManyAttempts(AuthError):
    pass


def bearer_token(request):
    header = request.getHeader(b"authorization") or b""
    if isinstance(header, str):
        header = header.encode("utf-8")
    scheme, _, value = header.partition(b" ")
    if scheme.lower() != b"bearer":
        return None
    try:
        token = value.strip().decode("utf-8")
    except UnicodeDecodeError:
        return None
    return token or None
