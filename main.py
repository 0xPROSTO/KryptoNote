import sys

from PySide6.QtCore import QEventLoop, Qt
from PySide6.QtGui import QIcon, QImageReader
from PySide6.QtWidgets import QApplication, QDialog

from KryptoNote.config import Config
from KryptoNote.gui.widgets.launcher import ProjectLauncher
from KryptoNote.gui.windows.main_window import ZeroXXWindow


def main():
    app = QApplication(sys.argv)
    QImageReader.setAllocationLimit(0)
    app.setStyle("Fusion")

    app_icon = QIcon(Config.ICON_PATH)
    app.setWindowIcon(app_icon)

    while True:
        launcher = ProjectLauncher()
        if launcher.exec() == QDialog.DialogCode.Accepted:
            if hasattr(launcher, 'auth_data') and launcher.auth_data:
                db_path, db_conn, crypto, repo, service = launcher.auth_data
                try:
                    window = ZeroXXWindow(db_path, db_conn, crypto, repo, service)
                    window.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
                    window.show()

                    loop = QEventLoop()
                    window.destroyed.connect(loop.quit)
                    loop.exec()
                except Exception as e:
                    print(f"Application error: {e}")
                    try:
                        db_conn.conn.close()
                    except Exception:
                        pass
        else:
            break

    sys.exit()


if __name__ == "__main__":
    main()
