from PySide6.QtCore import QObject, QThread, Signal, Slot

from ...core.exceptions import OperationCancelledError
from ...services.graph_export_service import GraphExportService


class GraphExportWorker(QObject):
    progress = Signal(float, str)
    finished = Signal(str)
    cancelled = Signal()
    failed = Signal(str)

    def __init__(
        self,
        db_path,
        crypto,
        output_path,
        export_format,
        appearance,
        case_name,
        password=None,
        selected_ids=None,
    ):
        super().__init__()
        self.db_path = db_path
        self.crypto = crypto
        self.output_path = output_path
        self.export_format = export_format
        self.appearance = appearance
        self.case_name = case_name
        self.password = password
        self.selected_ids = selected_ids

    @staticmethod
    def _is_cancelled():
        return QThread.currentThread().isInterruptionRequested()

    @Slot()
    def run(self):
        try:
            exporter = GraphExportService(
                self.db_path,
                self.crypto,
                appearance=self.appearance,
                case_name=self.case_name,
                selected_ids=self.selected_ids,
                cancel_check=self._is_cancelled,
                progress_callback=self.progress.emit,
            )
            result = exporter.export(
                self.output_path,
                self.export_format,
                password=self.password,
            )
            self.finished.emit(result)
        except OperationCancelledError:
            self.cancelled.emit()
        except Exception as exc:
            self.failed.emit(str(exc))
