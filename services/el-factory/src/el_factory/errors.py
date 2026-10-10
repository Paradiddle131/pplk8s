class ApiError(Exception):
    """A request-level failure that maps to an HTTP status and a JSON error body."""

    def __init__(self, status: int, message: str, retryable: bool = False) -> None:
        super().__init__(message)
        self.status = status
        self.message = message
        self.retryable = retryable
        self.extra: dict[str, object] = {}


class NotFound(ApiError):
    def __init__(self, message: str) -> None:
        super().__init__(404, message)


class BadRequest(ApiError):
    def __init__(self, message: str) -> None:
        super().__init__(400, message)


class UpstreamError(ApiError):
    """A transient failure talking to a source; the caller may retry."""

    def __init__(self, message: str) -> None:
        super().__init__(503, message, retryable=True)


class UpstreamRejected(ApiError):
    """The source refused our request (4xx): a bug on our side, so retrying cannot help."""

    def __init__(self, message: str) -> None:
        super().__init__(502, message, retryable=False)


class InvalidFile(ApiError):
    """A landed file does not match its entity's contract; reloading the same bytes cannot help."""

    def __init__(self, message: str) -> None:
        super().__init__(422, message)


class Superseded(ApiError):
    """The requested object generation was overwritten; the newer generation has its own event."""

    def __init__(self, message: str) -> None:
        super().__init__(409, message)
        self.extra = {"superseded": True}
