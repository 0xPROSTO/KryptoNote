from ..handles import ResizeHandle

from PyQt6.QtWidgets import QGraphicsRectItem, QMenu, QGraphicsItem
from PyQt6.QtGui import QColor, QBrush, QPen
from PyQt6.QtCore import Qt

from KryptoNote.config import Config


class BaseNode(QGraphicsRectItem):
    def __init__(self, item_id, x, y, w, h, repo):
        super().__init__(0, 0, w, h)
        self.setPos(x, y)
        self.setBrush(QBrush(QColor(Config.COLOR_NODE_BG)))
        self.setPen(QPen(Qt.PenStyle.NoPen))
        self.setFlags(QGraphicsItem.GraphicsItemFlag.ItemIsMovable |
                      QGraphicsItem.GraphicsItemFlag.ItemIsSelectable |
                      QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges)
        self.item_id = item_id
        self.repo = repo

        self.resizer = ResizeHandle(self)
        self.update_resizer_pos()

        self.connections = []


    def add_connection(self, line):
        if line not in self.connections:
            self.connections.append(line)

    def remove_connection(self, line):
        if line in self.connections:
            self.connections.remove(line)

    def itemChange(self, change, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionChange:
            for line in self.connections:
                line.update_position()
        return super().itemChange(change, value)


    def update_resizer_pos(self):
        r = self.rect()
        self.resizer.setPos(r.width() - 10, r.height() - 10)

    def handle_resize(self, new_pos):
        new_w = max(100, new_pos.x())
        new_h = max(50, new_pos.y())
        self.setRect(0, 0, new_w, new_h)
        self.update_resizer_pos()
        self.update_content_layout()

        for line in self.connections:
            line.update_position()

    def finalize_resize(self):
        r = self.rect()
        self.repo.update_size(self.item_id, r.width(), r.height())

    def update_content_layout(self):
        pass

    def mouseReleaseEvent(self, event):
        super().mouseReleaseEvent(event)
        self.repo.update_pos(self.item_id, self.x(), self.y())
        for line in self.connections:
            line.update_position()

    def contextMenuEvent(self, event):
        menu = QMenu()
        menu.setStyleSheet("QMenu { background-color: #333; color: white; }")
        self.extend_context_menu(menu)
        menu.addSeparator()
        delete_action = menu.addAction("Delete")
        action = menu.exec(event.screenPos())
        if action == delete_action:
            self.delete_node()

    def extend_context_menu(self, menu):
        pass

    def delete_node(self):
        for line in list(self.connections):
            line.remove_from_scene_only()

        self.repo.delete_node_cascade(self.item_id)

        if self.scene():
            self.scene().removeItem(self)