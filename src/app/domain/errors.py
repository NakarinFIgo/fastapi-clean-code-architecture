class DomainError(Exception):
    """Base for errors the usecases raise; handlers map them to HTTP."""


class ValidationError(DomainError):
    pass


class NotFoundError(DomainError):
    pass


class ConflictError(DomainError):
    pass


class AuthError(DomainError):
    pass
