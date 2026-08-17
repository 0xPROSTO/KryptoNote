"""Stable QObject contract shared by the QML canvas and its Python models."""

from __future__ import annotations

from PySide6.QtCore import QObject, Property
from PySide6.QtGui import QGuiApplication


class CanvasRuntime(QObject):
    """Keep all canvas dependencies alive behind one QML-facing object.

    QQuickWidget's QVariant-map initial-property conversion has proven brittle
    on some Linux/PySide combinations.  A single QObject exposed through the
    engine root context avoids converting independent Python objects and
    keeps the original QObject meta-objects visible to QML.
    """

    def __init__(
        self,
        *,
        app_theme,
        node_model,
        connection_model,
        node_viewport_model,
        connection_viewport_model,
        canvas_controller,
        viewer_controller,
        frame_clock,
        parent=None,
    ):
        super().__init__(parent)
        self._app_theme = app_theme
        self._node_model = node_model
        self._connection_model = connection_model
        self._node_viewport_model = node_viewport_model
        self._connection_viewport_model = connection_viewport_model
        self._canvas_controller = canvas_controller
        self._viewer_controller = viewer_controller
        self._frame_clock = frame_clock
        try:
            platform_name = str(QGuiApplication.platformName()).lower()
        except RuntimeError:
            platform_name = ""
        self._platform_name = platform_name
        self._prefer_angle_delta = platform_name == "xcb"

    # QObject is intentional here.  Property(object) marshals the Python
    # value as QVariant(PyObjectWrapper) in QML; that wrapper exposes neither
    # QObject slots nor model methods (the Linux symptom was
    # ``updateViewport is not a function``).  A QObject-typed property keeps
    # the original meta-object and its invokable methods visible to QML.
    @Property(QObject, constant=True)
    def appTheme(self):
        return self._app_theme

    @Property(QObject, constant=True)
    def nodeModel(self):
        return self._node_model

    @Property(QObject, constant=True)
    def connectionModel(self):
        return self._connection_model

    @Property(QObject, constant=True)
    def nodeViewportModel(self):
        return self._node_viewport_model

    @Property(QObject, constant=True)
    def connectionViewportModel(self):
        return self._connection_viewport_model

    @Property(QObject, constant=True)
    def canvasController(self):
        return self._canvas_controller

    @Property(QObject, constant=True)
    def viewerController(self):
        return self._viewer_controller

    @Property(QObject, constant=True)
    def frameClock(self):
        return self._frame_clock

    @Property(str, constant=True)
    def platformName(self):
        return self._platform_name

    @Property(bool, constant=True)
    def preferAngleDelta(self):
        return self._prefer_angle_delta
