import sys
from PyQt6.QtWidgets import QApplication
from KryptoNote.gui.launcher import ProjectLauncher
from KryptoNote.gui.main_window import ZeroXXWindow

if __name__ == "__main__":
    app = QApplication(sys.argv)

    app.setStyle("Fusion")

    launcher = ProjectLauncher()
    if launcher.exec():
        db_path = launcher.selected_file
        if db_path:
            window = ZeroXXWindow(db_path)
            window.show()
            sys.exit(app.exec())
    else:
        sys.exit()