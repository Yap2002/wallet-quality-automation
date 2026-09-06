from typing import Any


class ApplicationError(Exception):
    """A safe business error that can be returned by the API."""

    def __init__(
        self,
        code: str,
        message: str,
        status_code: int,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details or {}


class ResourceNotFoundError(ApplicationError):
    def __init__(self, resource: str) -> None:
        super().__init__(
            code="RESOURCE_NOT_FOUND",
            message=f"{resource} was not found",
            status_code=404,
        )


class AuthenticationError(ApplicationError):
    def __init__(self) -> None:
        super().__init__(
            code="AUTHENTICATION_REQUIRED",
            message="a valid Bearer API key is required",
            status_code=401,
        )


class PermissionDeniedError(ApplicationError):
    def __init__(self) -> None:
        super().__init__(
            code="PERMISSION_DENIED",
            message="the authenticated user cannot access this resource",
            status_code=403,
        )


class ConflictError(ApplicationError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(code=code, message=message, status_code=409)


class InsufficientBalanceError(ConflictError):
    def __init__(self) -> None:
        super().__init__(
            code="INSUFFICIENT_BALANCE",
            message="wallet balance is insufficient",
        )
