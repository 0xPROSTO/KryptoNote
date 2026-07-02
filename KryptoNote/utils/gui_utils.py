from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QInputDialog, QLineEdit


def center_on_parent_window(widget, parent=None):
    parent = parent or widget.parentWidget()
    host = parent.window() if parent else None

    if host:
        host_geo = host.frameGeometry()
        x = host_geo.x() + (host_geo.width() - widget.width()) // 2
        y = host_geo.y() + (host_geo.height() - widget.height()) // 2
        screen = host.screen() or QGuiApplication.screenAt(host_geo.center())
    else:
        screen = QGuiApplication.primaryScreen()
        if not screen:
            return
        host_geo = screen.availableGeometry()
        x = host_geo.x() + (host_geo.width() - widget.width()) // 2
        y = host_geo.y() + (host_geo.height() - widget.height()) // 2

    if screen:
        available = screen.availableGeometry()
        max_x = available.x() + max(0, available.width() - widget.width())
        max_y = available.y() + max(0, available.height() - widget.height())
        x = min(max(int(x), available.x()), max_x)
        y = min(max(int(y), available.y()), max_y)

    widget.move(int(x), int(y))


def get_centered_input(parent, title, label, echo_mode=QLineEdit.EchoMode.Normal):
    dialog = QInputDialog(parent)
    dialog.setWindowTitle(title)
    dialog.setLabelText(label)
    dialog.setTextEchoMode(echo_mode)
    dialog.resize(400, 150)
    center_on_parent_window(dialog, parent)

    if dialog.exec() == QInputDialog.DialogCode.Accepted:
        return dialog.textValue(), True
    return "", False


def adjust_window_to_screen(window, target_w=1440, target_h=900):
    screen = QGuiApplication.primaryScreen()
    if not screen:
        return
    available = screen.availableGeometry()
    if target_w > available.width() * 0.9:
        target_w = available.width() * 0.9
    if target_h > available.height() * 0.9:
        target_h = available.height() * 0.9

    x = available.x() + (available.width() - target_w) // 2
    y = available.y() + (available.height() - target_h) // 2
    window.setGeometry(int(x), int(y), int(target_w), int(target_h))
