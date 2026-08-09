import threading
from dataclasses import dataclass

from PySide6.QtCore import QObject, Signal


@dataclass(frozen=True, slots=True)
class OperationToken:
    """Opaque capability used to mutate or finish one active operation."""

    _owner: object
    _sequence: int
    kind: str


class OperationCoordinator(QObject):
    """Serialises database operations and publishes their UI blocking state."""

    state_changed = Signal(bool, str, str, bool)
    operation_rejected = Signal(str, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._lock = threading.RLock()
        self._owner = object()
        self._sequence = 0
        self._token = None
        self._message = ""
        self._blocking = False

    @property
    def is_busy(self):
        with self._lock:
            return self._token is not None

    @property
    def active_kind(self):
        with self._lock:
            return self._token.kind if self._token else ""

    @property
    def active_message(self):
        with self._lock:
            return self._message

    @property
    def is_blocking(self):
        with self._lock:
            return self._blocking

    def begin(self, kind, message="", blocking=True):
        kind = str(kind).strip()
        if not kind:
            raise ValueError("Operation kind cannot be empty")
        with self._lock:
            if self._token is not None:
                active_kind = self._token.kind
                self.operation_rejected.emit(kind, active_kind)
                return None
            self._sequence += 1
            token = OperationToken(self._owner, self._sequence, kind)
            self._token = token
            self._message = str(message)
            self._blocking = bool(blocking)
            state = self._state_unlocked()
        self.state_changed.emit(*state)
        return token

    def update(self, token, message):
        with self._lock:
            if not self._owns_unlocked(token):
                return False
            self._message = str(message)
            state = self._state_unlocked()
        self.state_changed.emit(*state)
        return True

    def transition(self, token, kind, message="", blocking=True):
        """Atomically replace the active operation without an idle UI frame."""
        kind = str(kind).strip()
        if not kind:
            raise ValueError("Operation kind cannot be empty")
        with self._lock:
            if not self._owns_unlocked(token):
                return None
            self._sequence += 1
            replacement = OperationToken(self._owner, self._sequence, kind)
            self._token = replacement
            self._message = str(message)
            self._blocking = bool(blocking)
            state = self._state_unlocked()
        self.state_changed.emit(*state)
        return replacement

    def set_blocking(self, token, blocking):
        with self._lock:
            if not self._owns_unlocked(token):
                return False
            self._blocking = bool(blocking)
            state = self._state_unlocked()
        self.state_changed.emit(*state)
        return True

    def finish(self, token):
        with self._lock:
            if not self._owns_unlocked(token):
                return False
            self._token = None
            self._message = ""
            self._blocking = False
        self.state_changed.emit(False, "", "", False)
        return True

    def owns(self, token):
        with self._lock:
            return self._owns_unlocked(token)

    def _owns_unlocked(self, token):
        return (
            isinstance(token, OperationToken)
            and token._owner is self._owner
            and token == self._token
        )

    def _state_unlocked(self):
        return True, self._token.kind, self._message, self._blocking
