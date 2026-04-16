from PySide6.QtWidgets import QInputDialog, QLineEdit
from PySide6.QtGui import QGuiApplication


def get_centered_input(parent, title, label, echo_mode=QLineEdit.EchoMode.Normal):
    dialog = QInputDialog(parent)
    dialog.setWindowTitle(title)
    dialog.setLabelText(label)
    dialog.setTextEchoMode(echo_mode)
    dialog.resize(400, 150)
    screen = QGuiApplication.primaryScreen()
    if screen:
        screen_geom = screen.availableGeometry()
        x = screen_geom.x() + (screen_geom.width() - dialog.width()) // 2
        y = screen_geom.y() + (screen_geom.height() - dialog.height()) // 2
        dialog.move(int(x), int(y))

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
