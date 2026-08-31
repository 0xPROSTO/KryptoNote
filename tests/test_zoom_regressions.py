import math
import os
from pathlib import Path

import pytest
from PySide6.QtCore import QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlComponent, QQmlEngine

from KryptoNote.core.constants import CANVAS_INTERACTIVE_COORDINATE_LIMIT
from KryptoNote.core.crypto import CryptoManager
from KryptoNote.core.database.connection import DatabaseConnection
from KryptoNote.core.database.repository import NodeRepository
from KryptoNote.gui.models.connection_list_model import ConnectionListModel
from KryptoNote.gui.models.node_list_model import NodeListModel
from KryptoNote.gui.models.viewport_proxy_model import (
    ConnectionViewportProxyModel,
    NodeViewportProxyModel,
)
from KryptoNote.gui.services.media_import_service import (
    prepare_media_import_positions,
)
from KryptoNote.services.graph_clipboard_service import GraphClipboardService


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
    property int rebaseCount: 0
    property var savedCameraState: null

    App.CanvasViewport {{
        id: viewport
        width: 800
        height: 600
        contentLayer: Item {{ id: layer }}
    }}

    Connections {{
        target: viewport
        function onZoomFinished(scale) {{ root.terminalCount += 1 }}
        function onRenderOriginRebased(deltaX, deltaY) {{
            root.rebaseCount += 1
        }}
    }}
    Component.onCompleted: viewport.initialize()

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
    function setExactZoom(x, y, scale, animated) {{
        viewport.setZoomScale(x, y, scale, animated)
    }}
    function centerOn(x, y, screenX, screenY, animated) {{
        return viewport.setCenterOnScreen(
            x, y, screenX, screenY, animated
        )
    }}
    function agePointerPan(milliseconds) {{
        viewport._lastPointerPanTime = Date.now() - milliseconds
    }}
    function releasePan() {{ return viewport.startInertiaIfNeeded() }}
    function inertiaRunning() {{ return viewport._inertiaRunning }}
    function panRunning() {{ return viewport._panRunning }}
    function inertiaReleaseWindow() {{
        return viewport.inertiaReleaseWindowMs
    }}
    function layerX() {{ return viewport.contentLayer.x }}
    function layerY() {{ return viewport.contentLayer.y }}
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
    function screenAt(x, y) {{ return viewport.canvasToScreen(x, y) }}
    function originX() {{ return viewport.renderOriginX }}
    function originY() {{ return viewport.renderOriginY }}
    function rebaseTo(x, y) {{
        return viewport._replaceRenderOrigin(x, y, true)
    }}
    function captureState(x, y) {{
        root.savedCameraState = viewport.captureCameraState(x, y)
    }}
    function savedRenderX() {{ return root.savedCameraState.renderX }}
    function savedRenderY() {{ return root.savedCameraState.renderY }}
    function restoreState(animated) {{
        return viewport.restoreCameraState(root.savedCameraState, animated)
    }}
    function rebases() {{ return root.rebaseCount }}
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
    property double renderOriginX: 0.0
    property double renderOriginY: 0.0
    property rect renderViewportRect: Qt.rect(-1000, -1000, 2000, 2000)
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
    function setRenderOrigin(x, y) {{
        root.renderOriginX = x
        root.renderOriginY = y
    }}
    function setEndpoints(x1, y1, x2, y2) {{
        connectionModel.connStartEdgeX = x1
        connectionModel.connStartEdgeY = y1
        connectionModel.connEndEdgeX = x2
        connectionModel.connEndEdgeY = y2
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
    function viewportClipped() {{ return connection.usesViewportClip }}
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


def test_exact_zoom_preserves_its_anchor_and_emits_one_terminal_signal():
    viewport, _engine, _component = _load_viewport()
    anchor_before = viewport.canvasAt(400, 300)

    viewport.setExactZoom(400, 300, 2.0, False)

    anchor_after = viewport.canvasAt(400, 300)
    assert viewport.contentScale() == pytest.approx(2.0)
    assert anchor_after.x() == pytest.approx(anchor_before.x())
    assert anchor_after.y() == pytest.approx(anchor_before.y())
    assert viewport.finishedCount() == 1


def test_exact_zoom_clamps_to_five_percent_minimum():
    viewport, _engine, _component = _load_viewport()

    viewport.setExactZoom(400, 300, 0.01, False)

    assert viewport.contentScale() == pytest.approx(0.05)


def test_exact_center_preserves_zoom_for_animated_and_immediate_motion():
    viewport, _engine, _component = _load_viewport()
    viewport.setExactZoom(400, 300, 1.75, False)

    assert viewport.centerOn(125, -250, 400, 300, False)
    centered = viewport.canvasAt(400, 300)
    assert centered.x() == pytest.approx(125)
    assert centered.y() == pytest.approx(-250)
    assert viewport.contentScale() == pytest.approx(1.75)

    assert viewport.centerOn(-80, 95, 400, 300, True)
    for _ in range(30):
        if not viewport.panRunning():
            break
        viewport.advance(1.0 / 120.0)
    assert not viewport.panRunning()
    centered = viewport.canvasAt(400, 300)
    assert centered.x() == pytest.approx(-80)
    assert centered.y() == pytest.approx(95)
    assert viewport.contentScale() == pytest.approx(1.75)


@pytest.mark.parametrize("scale", [0.05, 1.0, 5.0])
@pytest.mark.parametrize("target", [20_000_000.25, -20_000_000.25])
def test_floating_origin_centers_large_world_coordinates_at_every_zoom(
    scale, target
):
    viewport, _engine, _component = _load_viewport()
    viewport.setExactZoom(400, 300, scale, False)

    assert viewport.centerOn(target, -target, 400, 300, False)

    centered = viewport.canvasAt(400, 300)
    assert centered.x() == pytest.approx(target)
    assert centered.y() == pytest.approx(-target)
    assert viewport.originX() % 32768 == pytest.approx(0.0)
    assert viewport.originY() % 32768 == pytest.approx(0.0)
    assert abs(viewport.layerX()) < 100_000


@pytest.mark.parametrize("scale", [0.05, 1.0, 5.0])
def test_animated_navigation_rebases_every_intermediate_large_world_frame(scale):
    viewport, _engine, _component = _load_viewport()
    target_x = CANVAS_INTERACTIVE_COORDINATE_LIMIT - 599.0
    target_y = CANVAS_INTERACTIVE_COORDINATE_LIMIT - 23.0
    viewport.setExactZoom(400, 300, scale, False)

    assert viewport.centerOn(target_x, target_y, 400, 300, True)
    for _ in range(30):
        if not viewport.panRunning():
            break
        viewport.advance(1.0 / 120.0)
        assert abs(viewport.layerX()) < 100_000
        assert abs(viewport.layerY()) < 100_000

    assert not viewport.panRunning()
    centered = viewport.canvasAt(400, 300)
    assert centered.x() == pytest.approx(target_x, abs=0.0625)
    assert centered.y() == pytest.approx(target_y, abs=0.0625)


def test_render_origin_rebase_preserves_screen_position_in_the_same_turn():
    viewport, _engine, _component = _load_viewport()
    viewport.centerOn(20_000_000, -20_000_000, 400, 300, False)
    world_x = 20_000_123.25
    world_y = -19_999_543.75
    before = viewport.screenAt(world_x, world_y)

    assert viewport.rebaseTo(viewport.originX() + 32768, viewport.originY() - 32768)

    after = viewport.screenAt(world_x, world_y)
    assert after.x() == pytest.approx(before.x(), abs=0.001)
    assert after.y() == pytest.approx(before.y(), abs=0.001)
    assert viewport.rebases() >= 2


@pytest.mark.parametrize(
    "target",
    [CANVAS_INTERACTIVE_COORDINATE_LIMIT - 1024.0, 1e38],
)
def test_camera_snapshot_restores_origin_and_render_local_offset(target):
    viewport, _engine, _component = _load_viewport()
    viewport.setExactZoom(400, 300, 2.0, False)
    assert viewport.centerOn(target, -target, 400, 300, False)
    before_layer_x = viewport.layerX()
    before_layer_y = viewport.layerY()

    viewport.captureState(520, 350)
    assert abs(viewport.savedRenderX()) < 65536.0
    assert abs(viewport.savedRenderY()) < 65536.0

    assert viewport.centerOn(0, 0, 400, 300, False)
    assert viewport.restoreState(False)

    centered = viewport.canvasAt(400, 300)
    assert centered.x() == target
    assert centered.y() == -target
    assert abs(target - viewport.originX()) < 65536.0
    assert abs(-target - viewport.originY()) < 65536.0
    assert viewport.layerX() == pytest.approx(before_layer_x, abs=0.001)
    assert viewport.layerY() == pytest.approx(before_layer_y, abs=0.001)


@pytest.mark.parametrize("coordinate", [1e38, -1e38])
def test_viewport_proxies_keep_extreme_world_delegates(coordinate):
    nodes = NodeListModel()
    nodes.add_node(1, "text", coordinate, -coordinate, 200, 120)
    nodes.add_node(2, "text", coordinate, -coordinate, 160, 90)
    connections = ConnectionListModel(nodes)
    assert connections.add_connection(1, 1, 2)

    node_proxy = NodeViewportProxyModel(nodes)
    connection_proxy = ConnectionViewportProxyModel(connections)
    node_proxy.updateViewportCentered(
        coordinate, -coordinate, 800.0, 600.0
    )
    connection_proxy.updateViewportCentered(
        coordinate, -coordinate, 800.0, 600.0
    )

    assert node_proxy.rowCount() == 2
    assert connection_proxy.rowCount() == 1
    assert nodes.get_nodes_bounds([1]) == [
        coordinate,
        -coordinate,
        200.0,
        120.0,
    ]


def test_render_relative_rubber_band_selects_legacy_geometry():
    nodes = NodeListModel()
    nodes.add_node(1, "text", 1e38, -1e38, 200, 120)
    nodes.add_node(2, "text", 0, 0, 200, 120)

    assert nodes.get_nodes_in_render_rect(
        1e38,
        -1e38,
        -10,
        -10,
        210,
        130,
    ) == [1]

    rubber_source = (QML_DIR / "RubberBandSelection.qml").read_text(
        encoding="utf-8"
    )
    assert "viewport.screenToRender(" in rubber_source
    assert "get_nodes_in_render_rect(" in rubber_source


def test_graph_clipboard_keeps_legacy_node_size_and_clamps_paste_origin():
    database = DatabaseConnection(":memory:")
    crypto = CryptoManager()
    crypto.load_data_key(bytes(range(32)))
    repository = NodeRepository(database, crypto)
    try:
        node_id = repository.add_item(
            "text",
            1e38,
            -1e38,
            200,
            120,
            title="Legacy",
        )
        blueprint = repository.build_graph_copy_blueprint([node_id])
        assert blueprint["bounds"] == {"width": 200.0, "height": 120.0}
        assert blueprint["nodes"][0]["relative_x"] == pytest.approx(0.0)
        assert blueprint["nodes"][0]["relative_y"] == pytest.approx(0.0)

        clipboard = GraphClipboardService(repository)
        preparation = clipboard.prepare_duplicate(
            [node_id],
            offset=(
                CANVAS_INTERACTIVE_COORDINATE_LIMIT + 1000.0,
                -CANVAS_INTERACTIVE_COORDINATE_LIMIT - 1000.0,
            ),
        )
        assert preparation["offset_x"] == pytest.approx(
            CANVAS_INTERACTIVE_COORDINATE_LIMIT
        )
        assert preparation["offset_y"] == pytest.approx(
            -CANVAS_INTERACTIVE_COORDINATE_LIMIT
        )
    finally:
        repository.close()
        database.close()


def test_media_import_positions_are_clamped_as_one_group():
    limit = CANVAS_INTERACTIVE_COORDINATE_LIMIT
    positions = prepare_media_import_positions(
        [("image", "a.png"), ("audio", "b.wav")],
        limit,
        -limit,
    )

    first_x, first_y, first_width, first_height = positions[0]
    second_x, second_y, second_width, second_height = positions[1]
    assert max(first_x, second_x) <= limit
    assert min(first_y, second_y) >= -limit
    assert second_x - first_x == pytest.approx(
        25.0 + first_width / 2.0 - second_width / 2.0
    )
    assert second_y - first_y == pytest.approx(
        25.0 + first_height / 2.0 - second_height / 2.0
    )

    with pytest.raises(ValueError, match="interactive canvas range"):
        prepare_media_import_positions(
            [("image", "legacy.png")],
            1e38,
            0,
        )


def test_far_world_zoom_preserves_the_cursor_anchor():
    viewport, _engine, _component = _load_viewport()
    viewport.centerOn(25_000_000, -25_000_000, 400, 300, False)
    anchor_before = viewport.canvasAt(240, 175)

    viewport.mouseWheel(240, 175, 120)
    _advance_until_finished(viewport)

    anchor_after = viewport.canvasAt(240, 175)
    assert anchor_after.x() == pytest.approx(anchor_before.x(), abs=0.001)
    assert anchor_after.y() == pytest.approx(anchor_before.y(), abs=0.001)


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
    assert "usesViewportClip" in connection_source
    assert "clipSegmentToRect" in connection_source
    assert "canvasRoot.renderViewportRect" in connection_source


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


def test_canvas_exposes_exact_zoom_and_coordinate_navigation_bridge():
    canvas_source = (QML_DIR / "Canvas.qml").read_text(encoding="utf-8")

    assert "readonly property real maximumScale: viewport.maxScale" in canvas_source
    assert "readonly property point navigationCenter" in canvas_source
    assert "function zoomToPercent(percent)" in canvas_source
    assert "viewport.setZoomScale(" in canvas_source
    assert "function goToCoordinates(targetX, targetY)" in canvas_source
    assert "viewport.setCenterOnScreen(" in canvas_source


def test_grid_uses_wrapped_world_phase_instead_of_large_world_uniforms():
    canvas_source = (QML_DIR / "Canvas.qml").read_text(encoding="utf-8")
    grid_source = (QML_DIR / "grid.frag").read_text(encoding="utf-8")

    assert "positiveModulo(root.renderOriginX, root.gridSize)" in canvas_source
    assert "positiveModulo(root.renderOriginY, root.gridMain)" in canvas_source
    assert "renderPos + gridPhase" in grid_source
    assert "renderPos + mainGridPhase" in grid_source


def test_viewport_models_are_flushed_once_zoom_finishes():
    canvas_source = (QML_DIR / "Canvas.qml").read_text(encoding="utf-8")

    render_rect_source = canvas_source.split(
        "function refreshRenderViewportRect()", 1
    )[1].split("function updateViewportModels()", 1)[0]
    assert "viewport.visibleRenderRect(" in render_rect_source
    assert "root.renderViewportRect = visible" in render_rect_source

    update_source = canvas_source.split(
        "function updateViewportModels()", 1
    )[1].split("function retainTransformNodes", 1)[0]
    assert "root.refreshRenderViewportRect()" in update_source
    assert update_source.count("updateViewportCentered(") == 2
    assert "visible.x + visible.width" not in update_source

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
    rebase_source = canvas_source.split(
        "onRenderOriginRebased:", 1
    )[1].split("CanvasInputLayer {", 1)[0]
    assert "root.refreshRenderViewportRect()" in rebase_source
    assert "root.scheduleViewportUpdate()" in rebase_source


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


def test_connection_geometry_is_local_and_distant_links_are_viewport_clipped():
    connection, _engine, _component = _load_connection()
    near_geometry = connection.geometry().toVariant()

    connection.setRenderOrigin(20_000_000, -20_000_000)
    connection.setEndpoints(
        20_000_020,
        -19_999_970,
        20_000_420,
        -19_999_740,
    )
    local_geometry = connection.geometry().toVariant()
    assert local_geometry == near_geometry
    assert not connection.viewportClipped()

    connection.setRenderOrigin(0, 0)
    connection.setEndpoints(-20_000_000, 0, 20_000_000, 0)
    clipped_geometry = connection.geometry().toVariant()
    assert connection.viewportClipped()
    assert clipped_geometry[2] < 10_000
    assert clipped_geometry[3] < 10_000
    assert "20000000" not in clipped_geometry[4]

    extreme = 1e38
    next_extreme = math.nextafter(extreme, math.inf)
    connection.setRenderOrigin(extreme, -extreme)
    connection.setEndpoints(
        extreme,
        -extreme,
        next_extreme,
        -extreme,
    )
    extreme_geometry = connection.geometry().toVariant()
    assert connection.viewportClipped()
    assert all(abs(value) < 10_000 for value in extreme_geometry[:4])


def test_long_connection_hit_index_stays_bounded_and_hits_in_world_space():
    nodes = NodeListModel()
    nodes.add_node(1, "text", -20_000_000, 0, 100, 100)
    nodes.add_node(2, "text", 20_000_000, 0, 100, 100)
    connections = ConnectionListModel(nodes)
    connections.set_connection_appearance(
        "straight", "horizontal", "smooth", "perimeter"
    )

    assert connections.add_connection(1, 1, 2)
    assert connections._long_hit_segments
    assert len(connections._hit_grid) < 100
    assert connections.hit_test_connection(50, 50, 10) == 1


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
