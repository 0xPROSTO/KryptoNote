class KryptoNoteError(Exception):
    """Base exception for all KryptoNote errors."""
    pass


class CryptoError(KryptoNoteError):
    """Raised on encryption/decryption failures."""
    pass


class AuthError(KryptoNoteError):
    """Raised on authentication failures (wrong password, cancelled input)."""
    pass


class UnverifiableLegacyPassword(AuthError):
    """Raised when an empty legacy database has no ciphertext to verify."""
    pass


class DatabaseError(KryptoNoteError):
    """Raised on database-level failures (corruption, lock timeout)."""
    pass


class ProjectInUseError(DatabaseError):
    """Raised when another application instance owns the project session."""
    pass


class OperationCancelledError(KryptoNoteError):
    """Raised when a cooperative background operation is cancelled."""
    pass


class InsufficientDiskSpaceError(DatabaseError):
    """Raised when a database operation cannot be completed safely."""
    pass
