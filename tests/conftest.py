import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtGui import QGuiApplication


@pytest.fixture(scope="session", autouse=True)
def qt_application():
    app = QGuiApplication.instance()
    if app is None:
        app = QGuiApplication([])
    if not isinstance(app, QGuiApplication):
        raise RuntimeError("Tests require QGuiApplication as the shared Qt application")
    return app
