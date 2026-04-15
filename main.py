import sys

from PySide6.QtCore import QEventLoop, Qt
from PySide6.QtGui import QIcon, QImageReader
from PySide6.QtWidgets import QApplication, QDialog

from KryptoNote.config import Config
from KryptoNote.gui.windows.main_window import ZeroXXWindow
from KryptoNote.gui.widgets.launcher import ProjectLauncher


def main():
    app = QApplication(sys.argv)
    QImageReader.setAllocationLimit(0)
    app.setStyle("Fusion")

    app_icon = QIcon(Config.ICON_PATH)
    app.setWindowIcon(app_icon)

    while True:
        launcher = ProjectLauncher()
        if launcher.exec() == QDialog.DialogCode.Accepted:
            db_path = launcher.selected_file
            if db_path:
                try:
                    window = ZeroXXWindow(db_path)
                    window.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
                    window.show()

                    loop = QEventLoop()
                    window.destroyed.connect(loop.quit)
                    loop.exec()
                except RuntimeError as e:
                    print(f"Returning to launcher: {e}")
        else:
            break

    sys.exit()


if __name__ == "__main__":
    main()
