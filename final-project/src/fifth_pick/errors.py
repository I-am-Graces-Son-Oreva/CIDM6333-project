"""Typed errors for fail-closed Fifth Pick operations."""


class FifthPickError(Exception):
    """Base class for Fifth Pick errors."""


class ValidationError(FifthPickError, ValueError):
    """Raised when a typed domain value violates a safe invariant."""


class ReceiptError(ValidationError):
    """Raised when a receipt is malformed or cannot be redacted safely."""


class StorageError(FifthPickError):
    """Raised when durable run storage cannot be read or written safely."""


class UnsafeRunIdError(StorageError):
    """Raised when a run identifier could escape the injected storage root."""


class ReceiptConflictError(StorageError):
    """Raised when one event key is reused with different logical content."""
