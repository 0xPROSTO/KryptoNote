import sys

from KryptoNote.utils.secure_temp import (
    METADATA_TEMP_WATCHDOG_ARG,
    cleanup_stale_metadata_temp_dirs,
    run_metadata_temp_watchdog,
)


def main(argv=None):
    argv = list(sys.argv if argv is None else argv)
    if len(argv) > 1 and argv[1] == METADATA_TEMP_WATCHDOG_ARG:
        if len(argv) != 4:
            return 2
        return run_metadata_temp_watchdog(argv[2], argv[3])

    from PySide6.QtCore import QEventLoop, Qt
    from PySide6.QtGui import QIcon, QImageReader
    from PySide6.QtWidgets import QApplication, QDialog

    from KryptoNote.config import Config
    from KryptoNote.gui.theme.theme_manager import get_theme_manager

    cleanup_stale_metadata_temp_dirs()
    app = QApplication(argv)
    QImageReader.setAllocationLimit(256)
    app.setStyle("Fusion")

    get_theme_manager().load()

    from KryptoNote.gui.widgets.launcher import ProjectLauncher
    from KryptoNote.gui.windows.main_window import ZeroXXWindow

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
                        repo.close(wait=False)
                    except Exception:
                        pass
                    try:
                        db_conn.close()
                    except Exception:
                        pass
        else:
            break

    return 0


if __name__ == "__main__":
    sys.exit(main())
