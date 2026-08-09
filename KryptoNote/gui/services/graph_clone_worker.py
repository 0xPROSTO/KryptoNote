from PySide6.QtCore import QObject, QThread, Signal, Slot

from ...core.database import DatabaseConnection, NodeRepository
from ...core.exceptions import OperationCancelledError


class GraphCloneWorker(QObject):
    """Materialise a prepared graph copy on a dedicated QThread.

    The GUI prepares the metadata-only blueprint before moving this object to
    a QThread.  ``preparation`` may be the dictionary returned by
    ``GraphClipboardService.prepare_paste``/``prepare_duplicate`` or a raw
    blueprint plus explicit offsets.
    """

    # Python integers avoid the 32-bit Qt ``int`` ceiling for multi-GB media.
    progress = Signal(object, object, str)
    finished = Signal(object)
    failed = Signal(str)
    cancelled = Signal()

    DEFAULT_PASTE_OFFSET = (32.0, 32.0)

    def __init__(
        self,
        db_path,
        crypto_manager=None,
        preparation=None,
        offset_x=None,
        offset_y=None,
        *,
        blueprint=None,
        offset=None,
        target_origin=None,
        crypto=None,
    ):
        super().__init__()
        if crypto_manager is None:
            crypto_manager = crypto
        elif crypto is not None and crypto is not crypto_manager:
            raise TypeError("Pass either crypto_manager or crypto, not both")
        if crypto_manager is None:
            raise TypeError("A crypto manager is required")
        if preparation is not None and blueprint is not None:
            raise TypeError(
                "Pass either preparation or blueprint, not both"
            )
        if blueprint is not None:
            preparation = blueprint

        self._db_path = db_path
        self._crypto_manager = crypto_manager
        self._blueprint, prepared_origin = self._split_preparation(
            preparation
        )
        self._offset_x, self._offset_y = self._resolve_origin(
            self._blueprint,
            prepared_origin,
            offset,
            target_origin,
            offset_x,
            offset_y,
        )

    @staticmethod
    def _split_preparation(preparation):
        if not isinstance(preparation, dict):
            raise TypeError("Graph clone preparation must be a mapping")
        if "blueprint" in preparation:
            blueprint = preparation["blueprint"]
            prepared_origin = (
                preparation.get("target_origin")
                or preparation.get("offset")
            )
        else:
            blueprint = preparation
            prepared_origin = preparation.get("target_origin")
        if not isinstance(blueprint, dict):
            raise TypeError("Graph clone blueprint must be a mapping")
        return blueprint, prepared_origin

    @classmethod
    def _coerce_pair(cls, value):
        if value is None:
            return None
        if isinstance(value, dict):
            try:
                return float(value.get("x", 0)), float(value.get("y", 0))
            except (TypeError, ValueError) as exc:
                raise ValueError(
                    "target origin must contain numeric x and y"
                ) from exc
        if isinstance(value, (int, float)):
            number = float(value)
            return number, number
        try:
            x, y = value
        except (TypeError, ValueError) as exc:
            raise ValueError(
                "target origin must be a number, pair or mapping"
            ) from exc
        return float(x), float(y)

    @classmethod
    def _resolve_origin(
        cls,
        blueprint,
        prepared_origin,
        offset,
        target_origin,
        offset_x,
        offset_y,
    ):
        explicit_pair = target_origin if target_origin is not None else offset
        if explicit_pair is not None:
            pair = cls._coerce_pair(explicit_pair)
            return pair
        if offset_x is not None or offset_y is not None:
            return float(offset_x or 0), float(offset_y or 0)
        if prepared_origin is not None:
            pair = cls._coerce_pair(prepared_origin)
            return pair
        origin = blueprint.get("origin") or {}
        return (
            float(origin.get("x", 0)) + cls.DEFAULT_PASTE_OFFSET[0],
            float(origin.get("y", 0)) + cls.DEFAULT_PASTE_OFFSET[1],
        )

    @staticmethod
    def _is_cancelled():
        try:
            return QThread.currentThread().isInterruptionRequested()
        except RuntimeError:
            return True

    @Slot()
    def run(self):
        db_connection = None
        repository = None
        try:
            if self._is_cancelled():
                raise OperationCancelledError("Graph paste cancelled")
            db_connection = DatabaseConnection(
                self._db_path, initialize=False, must_exist=True
            )
            clone_crypto = self._crypto_manager.create_clone()
            repository = NodeRepository(db_connection, clone_crypto)
            result = repository.clone_graph(
                self._blueprint,
                offset_x=self._offset_x,
                offset_y=self._offset_y,
                progress_callback=self.progress.emit,
                cancel_check=self._is_cancelled,
            )
            self.finished.emit(result)
        except OperationCancelledError:
            self.cancelled.emit()
        except Exception as exc:
            self.failed.emit(str(exc))
        finally:
            try:
                if repository is not None:
                    repository.close(wait=True)
            finally:
                if db_connection is not None:
                    db_connection.close()
