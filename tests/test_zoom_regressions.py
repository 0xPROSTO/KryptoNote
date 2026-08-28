import os
from pathlib import Path

import pytest
from PySide6.QtCore import QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlComponent, QQmlEngine


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]
QML_DIR = ROOT / "KryptoNote" / "gui" / "qml"


def _load_viewport():
    QGuiApplication.instance() or QGuiApplication([])
    engine = QQmlEngine()
    qml_dir = QML_DIR.resolve().as_uri()
    source = f'''
import QtQuick
import "{qml_dir}" as App

Item {{
    id: root
    property int terminalCount: 0

    App.CanvasViewport {{
        id: viewport
        width: 800
        height: 600
        contentLayer: Item {{ id: layer }}
    }}

    Connections {{
        target: viewport
        function onZoomFinished(scale) {{ root.terminalCount += 1 }}
    }}

    function mouseWheel(x, y, angle) {{
        return viewport.handleWheel({{
            x: x,
            y: y,
            angleDelta: Qt.point(0, angle),
            pixelDelta: Qt.point(0, 0)
        }}, true)
    }}
    function highResolutionAngleWheel(x, y, angle) {{
        return viewport.handleWheel({{
            x: x,
            y: y,
            angleDelta: Qt.point(0, angle),
            pixelDelta: Qt.point(0, 0)
        }}, true)
    }}
    function pixelWheel(x, y, pixels) {{
        return viewport.handleWheel({{
            x: x,
            y: y,
            angleDelta: Qt.point(0, 0),
            pixelDelta: Qt.point(0, pixels)
        }}, true)
    }}
    function advance(dt) {{ viewport.advanceFrame(dt) }}
    function stopMotion() {{ viewport.stopMotion() }}
    function pan(dx, dy) {{ viewport.panBy(dx, dy) }}
    function agePointerPan(milliseconds) {{
        viewport._lastPointerPanTime = Date.now() - milliseconds
    }}
    function releasePan() {{ return viewport.startInertiaIfNeeded() }}
    function inertiaRunning() {{ return viewport._inertiaRunning }}
    function inertiaReleaseWindow() {{
        return viewport.inertiaReleaseWindowMs
    }}
    function layerX() {{ return viewport.contentLayer.x }}
    function pointerVelocityX() {{ return viewport.velocityX }}
    function contentScale() {{ return viewport.contentScale }}
    function targetScale() {{ return viewport._zoomTo }}
    function sourceScale() {{ return viewport._zoomFrom }}
    function zoomElapsed() {{ return viewport._zoomElapsed }}
    function zoomVelocity() {{ return viewport._zoomVelocity }}
    function zoomStartVelocity() {{ return viewport._zoomStartVelocity }}
    function zoomActive() {{ return viewport.zoomActive }}
    function continuousPending() {{ return viewport._continuousZoomPending }}
    function finishedCount() {{ return root.terminalCount }}
    function canvasAt(x, y) {{ return viewport.screenToCanvas(x, y) }}
}}
'''.encode()
    component = QQmlComponent(engine)
    component.setData(
        source,
        QUrl.fromLocalFile(str(ROOT / "tests" / "ZoomHarness.qml")),
    )
    assert component.status() == QQmlComponent.Status.Ready, [
        error.toString() for error in component.errors()
    ]
    harness = component.create()
    assert harness is not None
    return harness, engine, component


def _load_connection():
    QGuiApplication.instance() or QGuiApplication([])
    engine = QQmlEngine()
    qml_dir = QML_DIR.resolve().as_uri()
    source = f'''
import QtQuick
import "{qml_dir}" as App

Item {{
    id: root
    width: 800
    height: 600
    property real contentScale: 1.0
    property real visualDetailScale: 1.0
    readonly property real minimumScale: 0.1
    property int hoveredConnectionId: 0
    function visibleCanvasRect(margin) {{
        return Qt.rect(-1000, -1000, 2000, 2000)
    }}

    QtObject {{
        id: connectionModel
        property int connId: 1
        property real connStartEdgeX: 20
        property real connStartEdgeY: 30
        property real connEndEdgeX: 420
        property real connEndEdgeY: 260
        property bool connIsHighlighted: false
        property bool connIsDeleting: false
        property bool connDeleteFinalizes: true
    }}

    QtObject {{
        id: controller
        function perform_delete_connection(connId) {{}}
    }}

    QtObject {{
        id: theme
        property bool motionEnabled: true
        property bool colorMotionEnabled: true
        property int durationState: 140
        property int durationPanel: 220
        property real connectionStrokeWidth: 2
        property real connectionHighlightWidth: 4
        property string connectionStyle: "curved"
        property string connectionCurveFormula: "bezier"
        property string connectionCornerStyle: "rounded"
        property string connectionPattern: "solid"
        property color textMuted: "#888888"
        property color accentMain: "#ffffff"
        property color accentHigh: "#ffffff"
        property color borderDefault: "#777777"
        property color borderHover: "#999999"
        property color dangerHover: "#ff5555"
    }}

    App.Connection {{
        id: connection
        model: connectionModel
        canvasRoot: root
        canvasController: controller
        appTheme: theme
    }}

    function setContentScale(scale) {{ root.contentScale = scale }}
    function setVisualDetailScale(scale) {{
        root.visualDetailScale = scale
    }}
    function geometry() {{
        return [
            connection.x,
            connection.y,
            connection.width,
            connection.height,
            connection.pathGeometry.path
        ]
    }}
    function strokeWidth() {{ return connection.effectiveStrokeWidth }}
}}
'''.encode()
    component = QQmlComponent(engine)
    component.setData(
        source,
        QUrl.fromLocalFile(str(ROOT / "tests" / "ConnectionHarness.qml")),
    )
    assert component.status() == QQmlComponent.Status.Ready, [
        error.toString() for error in component.errors()
    ]
    harness = component.create()
    assert harness is not None
    return harness, engine, component


def _advance_until_finished(viewport):
    for _ in range(30):
        if not viewport.zoomActive():
            return
        viewport.advance(1.0 / 120.0)
    raise AssertionError("zoom gesture did not reach its terminal state")


def test_mouse_notches_accumulate_from_the_in_flight_target():
    viewport, _engine, _component = _load_viewport()

    assert viewport.mouseWheel(200, 150, 120)
    assert viewport.contentScale() == pytest.approx(1.0)
    assert viewport.targetScale() == pytest.approx(1.20)

    viewport.advance(1.0 / 60.0)
    displayed_scale = viewport.contentScale()
    assert displayed_scale > 1.0
    velocity_before_retarget = viewport.zoomVelocity()
    assert velocity_before_retarget > 0.0

    assert viewport.mouseWheel(200, 150, 120)
    assert viewport.sourceScale() == pytest.approx(displayed_scale)
    assert viewport.targetScale() == pytest.approx(1.44)
    assert viewport.zoomElapsed() == pytest.approx(0.0)
    assert viewport.zoomStartVelocity() == pytest.approx(
        velocity_before_retarget
    )


def test_mouse_zoom_eases_in_without_a_large_first_frame_jump():
    viewport, _engine, _component = _load_viewport()

    viewport.mouseWheel(200, 150, 120)
    viewport.advance(1.0 / 120.0)

    assert 1.0 < viewport.contentScale() < 1.01


def test_mouse_zoom_preserves_the_latest_cursor_anchor_and_finishes_once():
    viewport, _engine, _component = _load_viewport()
    anchor_before = viewport.canvasAt(240, 175)

    viewport.mouseWheel(240, 175, 120)
    viewport.mouseWheel(240, 175, 120)
    _advance_until_finished(viewport)

    anchor_after = viewport.canvasAt(240, 175)
    assert viewport.contentScale() == pytest.approx(1.44)
    assert anchor_after.x() == pytest.approx(anchor_before.x())
    assert anchor_after.y() == pytest.approx(anchor_before.y())
    assert viewport.finishedCount() == 1

    viewport.advance(1.0 / 60.0)
    assert viewport.finishedCount() == 1


def test_high_resolution_deltas_are_batched_into_one_frame_without_backlog():
    viewport, _engine, _component = _load_viewport()
    anchor_before = viewport.canvasAt(120, 90)

    assert viewport.highResolutionAngleWheel(120, 90, 30)
    assert viewport.highResolutionAngleWheel(120, 90, 30)
    assert viewport.contentScale() == pytest.approx(1.0)
    assert viewport.continuousPending()

    viewport.advance(1.0 / 120.0)

    assert viewport.contentScale() == pytest.approx(1.20**0.5)
    assert not viewport.continuousPending()
    anchor_after = viewport.canvasAt(120, 90)
    assert anchor_after.x() == pytest.approx(anchor_before.x())
    assert anchor_after.y() == pytest.approx(anchor_before.y())

    scale_after_batch = viewport.contentScale()
    viewport.advance(1.0 / 120.0)
    assert viewport.contentScale() == pytest.approx(scale_after_batch)

    _advance_until_finished(viewport)
    assert viewport.finishedCount() == 1


def test_pixel_delta_is_only_a_zero_angle_fallback():
    viewport, _engine, _component = _load_viewport()

    assert viewport.pixelWheel(100, 100, 120)
    assert viewport.contentScale() == pytest.approx(1.0)
    viewport.advance(1.0 / 120.0)

    assert viewport.contentScale() == pytest.approx(1.20)


def test_stop_motion_clears_pending_zoom_and_emits_one_terminal_signal():
    viewport, _engine, _component = _load_viewport()

    viewport.highResolutionAngleWheel(100, 100, 30)
    assert viewport.zoomActive()
    viewport.stopMotion()

    assert not viewport.zoomActive()
    assert not viewport.continuousPending()
    assert viewport.finishedCount() == 1

    viewport.stopMotion()
    assert viewport.finishedCount() == 1


def test_pointer_pan_inertia_requires_recent_movement():
    viewport, _engine, _component = _load_viewport()

    viewport.pan(12, 0)
    stopped_x = viewport.layerX()
    viewport.agePointerPan(viewport.inertiaReleaseWindow() + 1)

    assert not viewport.releasePan()
    assert not viewport.inertiaRunning()
    assert viewport.pointerVelocityX() == pytest.approx(0.0)
    viewport.advance(1.0 / 60.0)
    assert viewport.layerX() == pytest.approx(stopped_x)

    viewport.pan(12, 0)
    released_x = viewport.layerX()
    viewport.agePointerPan(0)

    assert viewport.releasePan()
    assert viewport.inertiaRunning()
    viewport.advance(1.0 / 60.0)
    assert viewport.layerX() > released_x


def test_visual_detail_and_connection_geometry_do_not_follow_tween_frames():
    canvas_source = (QML_DIR / "Canvas.qml").read_text(encoding="utf-8")
    delegate_source = (QML_DIR / "NodeDelegate.qml").read_text(
        encoding="utf-8"
    )
    connection_source = (QML_DIR / "Connection.qml").read_text(
        encoding="utf-8"
    )

    assert "readonly property real visualDetailScale" in canvas_source
    assert "onZoomFinished: function(scale)" in canvas_source
    assert canvas_source.count("root._visualDetailScale =") == 2
    assert "canvasScale: delegateRoot.canvasRoot.visualDetailScale" in (
        delegate_source
    )
    assert "Behavior on strokeWidth" not in connection_source
    assert "property real renderPadding" in connection_source
    bounds_source = connection_source.split(
        "property real renderPadding", 1
    )[1].split("property var pathGeometry", 1)[0]
    assert "contentScale" not in bounds_source
    assert "visibleCanvasRect" not in connection_source
    assert "isInViewport" not in connection_source
    assert "segments:" not in connection_source
    assert "appendSegment" not in connection_source


def test_zoom_overlay_bridge_is_only_called_after_motion_finishes():
    canvas_source = (QML_DIR / "Canvas.qml").read_text(encoding="utf-8")
    viewport_block = canvas_source.split("CanvasViewport {", 1)[1].split(
        "CanvasInputLayer {", 1
    )[0]

    assert "onZoomChanged" not in viewport_block
    terminal_block = viewport_block.split(
        "onZoomFinished: function(scale)", 1
    )[1].split("onZoomActiveChanged", 1)[0]
    assert "root.canvasController.report_zoom(scale)" in terminal_block


def test_viewport_models_are_flushed_once_zoom_finishes():
    canvas_source = (QML_DIR / "Canvas.qml").read_text(encoding="utf-8")

    scheduler_source = canvas_source.split(
        "function scheduleViewportUpdate()", 1
    )[1].split("function openTagPickerForNode", 1)[0]
    assert "if (viewport.zoomActive)" in scheduler_source
    assert "viewportUpdateTimer.stop()" in scheduler_source

    timer_source = canvas_source.split("id: viewportUpdateTimer", 1)[1].split(
        "Connections {", 1
    )[0]
    assert "viewport.zoomActive" in timer_source

    zoom_finished_source = canvas_source.split(
        "onZoomFinished: function(scale)", 1
    )[1].split("onZoomActiveChanged", 1)[0]
    assert "root.scheduleViewportUpdate()" in zoom_finished_source


def test_connection_bounds_and_path_ignore_intermediate_content_scale():
    connection, _engine, _component = _load_connection()
    geometry_before = connection.geometry().toVariant()
    stroke_before = connection.strokeWidth()

    connection.setContentScale(1.37)

    assert connection.geometry().toVariant() == geometry_before
    assert connection.strokeWidth() == pytest.approx(stroke_before)

    connection.setVisualDetailScale(1.37)
    assert connection.geometry().toVariant() == geometry_before
    assert connection.strokeWidth() != pytest.approx(stroke_before)


def test_connection_context_menu_uses_the_shared_spatial_hit_test():
    canvas_source = (QML_DIR / "Canvas.qml").read_text(encoding="utf-8")
    connection_source = (QML_DIR / "Connection.qml").read_text(
        encoding="utf-8"
    )
    layer_source = (QML_DIR / "ConnectionLayer.qml").read_text(
        encoding="utf-8"
    )

    assert "MouseArea" not in connection_source
    assert "contextMenuRequested" not in connection_source
    assert "contextMenuRequested" not in layer_source
    assert "root.connectionModel.hit_test_connection(" in canvas_source
    assert "canvasContextMenu.openForConnection(" in canvas_source
    assert "canvasContextMenu.openForCanvas(" in canvas_source
