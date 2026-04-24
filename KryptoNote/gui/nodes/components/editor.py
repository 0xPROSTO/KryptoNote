from PySide6.QtGui import QFont

from KryptoNote.gui.theme import Theme
from KryptoNote.gui.widgets.dialogs.node_editor_dialog import NoteEditorDialog
from KryptoNote.utils.text_utils import process_markdown_for_pyside
from .base import NodeComponent


class EditorComponent(NodeComponent):
    def __init__(self, editor_type="text"):
        super().__init__()
        self.editor_type = editor_type

    def on_attached(self, node):
        super().on_attached(node)

    def on_event(self, event_type: str, *args, **kwargs):
        if event_type == "double_click":
            if self.editor_type == "text":
                self._handle_text_edit()
        elif event_type == "extend_context_menu":
            menu = kwargs.get("menu")
            if menu and self.editor_type == "text":
                edit_action = menu.addAction("Edit")
                edit_action.triggered.connect(self._handle_text_edit)

                menu.addSeparator()

                autofit_action = menu.addAction("Auto-Fit")
                autofit_action.triggered.connect(lambda: self.node.dispatch_event("auto_fit"))

    def _handle_text_edit(self):
        node = self.node
        title = getattr(node, "title", "")
        text_content = getattr(node, "text_content", "")
        title_size = getattr(node, "title_size", 14)
        text_size = getattr(node, "text_size", 10)

        dialog = NoteEditorDialog(title, text_content, title_size, text_size)
        if dialog.exec():
            new_title, new_text, new_title_size, new_text_size = dialog.get_data()

            node.title = new_title.strip()
            node.text_content = new_text
            node.title_size = new_title_size
            node.text_size = new_text_size

            if hasattr(node, "title_item"):
                node.title_item.setPlainText(node.title)
                node.title_item.setFont(QFont(Theme.Typography.FONT_DISPLAY, node.title_size, QFont.Weight.Bold))

            if hasattr(node, "body_item"):
                node.body_item.setFont(QFont(Theme.Typography.FONT_BODY, node.text_size))
                node.body_item.document().setMarkdown(process_markdown_for_pyside(node.text_content))

            if hasattr(node, "update_content_layout"):
                node.update_content_layout()

            node.dispatch_event("check_pending_fit")

            if hasattr(node, "service") and hasattr(node, "item_id"):
                node.service.update_text_content(
                    node.item_id, node.title, node.text_content, node.title_size, node.text_size
                )
        else:
            if not title.strip() and not text_content.strip():
                if hasattr(node, "delete_node"):
                    node.delete_node()


class MediaActionComponent(NodeComponent):
    def on_attached(self, node):
        super().on_attached(node)

    def on_event(self, event_type: str, *args, **kwargs):
        if event_type == "double_click":
            if hasattr(self.node, "open_content"):
                self.node.open_content()
        elif event_type == "extend_context_menu":
            menu = kwargs.get("menu")
            if menu:
                open_action = menu.addAction("Open")
                if hasattr(self.node, "open_content"):
                    open_action.triggered.connect(self.node.open_content)

                rename_action = menu.addAction("Rename")
                if hasattr(self.node, "rename_node"):
                    rename_action.triggered.connect(self.node.rename_node)

                menu.addSeparator()

                autofit_action = menu.addAction("Auto-Fit")
                if hasattr(self.node, "auto_fit_to_media"):
                    autofit_action.triggered.connect(self.node.auto_fit_to_media)

                menu.addSeparator()
                save_action = menu.addAction("Export to Disk")
                if hasattr(self.node, "export_file"):
                    save_action.triggered.connect(self.node.export_file)
