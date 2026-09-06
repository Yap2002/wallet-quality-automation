class DomainError(ValueError):
    """Base class for invalid domain operations."""


class InvalidMoneyError(DomainError):
    """Raised when a monetary value violates wallet rules."""


class InvalidStateTransitionError(DomainError):
    """Raised when a transaction attempts an illegal state transition."""
