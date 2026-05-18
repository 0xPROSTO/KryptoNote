from PySide6.QtCore import QObject, Slot
from PySide6.QtWidgets import QMessageBox

from ...config import Config


class ViewerController(QObject):
    """Handles opening note editors and media viewers.

    Extracted from ZeroXXWindow to decouple viewer launch
    logic from the main window.
    """

    def __init__(self, node_model, canvas_controller, service, parent=None):
        super().__init__(parent)
        self._node_model = node_model
        self._canvas_controller = canvas_controller
        self._service = service

    @Slot(int)
    def open_note_editor(self, node_id):
        node = self._node_model.get_node_data(node_id)
        if not node:
            return

        from ...gui.widgets.dialogs.node_editor_dialog import NoteEditorDialog

        dialog = NoteEditorDialog(
            node["title"], node["content"],
            node.get("title_size", 14), node.get("text_size", 10),
            self.parent()
        )
        if dialog.exec():
            title, content, t_size, n_size = dialog.get_data()
            self._canvas_controller.save_text_content(node_id, title, content, t_size, n_size)

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
        from PySide6.QtGui import QImage

        image_data = self._service.get_item_data(node_id)
        if image_data:
            image = QImage.fromData(image_data)
            if image.isNull():
                QMessageBox.warning(self.parent(), "Image", "Unable to open this image.")
                return
            dialog = MediaViewerDialog(image, self.parent())
            dialog.exec()

    @Slot()
    def open_new_note_editor(self):
        from ...gui.widgets.dialogs.node_editor_dialog import NoteEditorDialog

        dialog = NoteEditorDialog("", "", 14, 10, self.parent())
        if dialog.exec():
            title, content, t_size, n_size = dialog.get_data()
            center = self._canvas_controller.get_viewport_center()
            x = center[0] - Config.NODE_DEFAULT_WIDTH / 2
            y = center[1] - Config.NODE_DEFAULT_HEIGHT / 2
            self._canvas_controller.create_text_node_at(
                x, y, title, content, t_size, n_size
            )
