class AddTorrentError(Exception):
    pass


class InvalidTorrentError(Exception):
    pass


class _UsernameBasedPassthroughError(Exception):
    def __init__(self, message, username):
        super().__init__(message)
        self.username = username


class BadLoginError(_UsernameBasedPassthroughError):
    pass


class AuthenticationRequired(_UsernameBasedPassthroughError):
    pass
