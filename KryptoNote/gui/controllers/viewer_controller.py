from PySide6.QtCore import QObject, Slot
from PySide6.QtWidgets import QMessageBox

from ...config import Config


class ViewerController(QObject):
    """Handles opening media viewers.

    Extracted from ZeroXXWindow to decouple viewer launch
    logic from the main window.
    """

    def __init__(self, node_model, canvas_controller, service, parent=None):
        super().__init__(parent)
        self._node_model = node_model
        self._canvas_controller = canvas_controller
        self._service = service

    @Slot(int)
    def open_media_viewer(self, node_id):
        node = self._node_model.get_node_data(node_id)
        if not node:
            return

        if node["type"] == "video":
            self._open_video_player(node_id, node)
            return

        self._open_image_viewer(node_id)

    def _open_video_player(self, node_id, node):
        from ...gui.widgets.viewers import SecureVideoPlayer

        info = self._service.get_item_info(node_id)
        if not info or not info.is_chunked:
            QMessageBox.warning(self.parent(), "Video", "Unable to open this video.")
            return

        player = SecureVideoPlayer(
            self._service.repo,
            node_id,
            info.total_size,
            Config.CHUNK_SIZE,
            node.get("title") or "Secure Video",
            self.parent(),
        )
        player.exec()

    def _open_image_viewer(self, node_id):
        from ...gui.widgets.dialogs.media_viewer_dialog import MediaViewerDialog

        try:
            image = self._service.read_image_preview(node_id, (4096, 4096))
        except Exception as exc:
            QMessageBox.warning(self.parent(), "Image", f"Unable to open this image.\n{exc}")
            return
        dialog = MediaViewerDialog(image, self.parent())
        dialog.exec()
