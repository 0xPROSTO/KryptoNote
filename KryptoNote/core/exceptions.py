class KryptoNoteError(Exception):
    """Base exception for all KryptoNote errors."""
    pass


class CryptoError(KryptoNoteError):
    """Raised on encryption/decryption failures."""
    pass


class AuthError(KryptoNoteError):
    """Raised on authentication failures (wrong password, cancelled input)."""
    pass


class DatabaseError(KryptoNoteError):
    """Raised on database-level failures (corruption, lock timeout)."""
    pass


class OperationCancelledError(KryptoNoteError):
    """Raised when a cooperative background operation is cancelled."""
    pass
