import sys
from PyQt6.QtWidgets import QApplication, QDialog
from PyQt6.QtCore import QEventLoop, Qt
from KryptoNote.gui.widgets.launcher import ProjectLauncher
from KryptoNote.gui.main_window import ZeroXXWindow
from KryptoNote.config import Config
from PyQt6.QtGui import QIcon


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    app_icon = QIcon(Config.ICON_PATH)
    app.setWindowIcon(app_icon)

    while True:
        launcher = ProjectLauncher()
        if launcher.exec() == QDialog.DialogCode.Accepted:
            db_path = launcher.selected_file
            if db_path:
                window = ZeroXXWindow(db_path)
                window.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
                window.show()

                loop = QEventLoop()
                window.destroyed.connect(loop.quit)
                loop.exec()
        else:
            break

    sys.exit()


if __name__ == "__main__":
    main()