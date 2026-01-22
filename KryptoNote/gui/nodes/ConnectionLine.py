from PyQt6.QtWidgets import QGraphicsLineItem, QMenu, QGraphicsItem
from PyQt6.QtGui import QPen, QColor, QPainter
from PyQt6.QtCore import Qt, QPointF


class ConnectionLine(QGraphicsLineItem):
    def __init__(self, conn_id, start_node, end_node, storage):
        super().__init__()
        self.conn_id = conn_id
        self.start_node = start_node
        self.end_node = end_node
        self.storage = storage

        pen = QPen(QColor("#ff4444"), 2)
        pen.setCosmetic(True)
        self.setPen(pen)

        self.setZValue(-1)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.update_position()

    def update_position(self):
        if self.start_node and self.end_node:
            p1 = self.start_node.sceneBoundingRect().center()
            p2 = self.end_node.sceneBoundingRect().center()
            self.setLine(p1.x(), p1.y(), p2.x(), p2.y())

    def contextMenuEvent(self, event):
        menu = QMenu()
        menu.setStyleSheet("QMenu { background-color: #333; color: white; }")
        delete_action = menu.addAction("Разорвать связь")
        action = menu.exec(event.screenPos())

        if action == delete_action:
            self.delete_connection()

    def delete_connection(self):
        self.storage.delete_connection(self.conn_id)

        if self.start_node: self.start_node.remove_connection(self)
        if self.end_node: self.end_node.remove_connection(self)

        if self.scene():
            self.scene().removeItem(self)

    def remove_from_scene_only(self):
        if self.start_node: self.start_node.remove_connection(self)
        if self.end_node: self.end_node.remove_connection(self)

        if self.scene():
            self.scene().removeItem(self)