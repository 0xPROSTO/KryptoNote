from pathlib import Path

import pytest
from PySide6.QtCore import QCoreApplication, QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlComponent, QQmlEngine
from PySide6.QtQuick import QQuickItem

from KryptoNote.core.constants import CANVAS_INTERACTIVE_COORDINATE_LIMIT
from KryptoNote.gui.models.node_list_model import NodeListModel
from KryptoNote.gui.models.viewport_proxy_model import NodeViewportProxyModel

ROOT = Path(__file__).resolve().parents[1]
QML_DIR = ROOT / "KryptoNote" / "gui" / "qml"


def _walk_items(parent):
    for child in parent.childItems():
        yield child
        yield from _walk_items(child)


def _class_items(parent, class_name):
    return [
        item
        for item in _walk_items(parent)
        if class_name in item.metaObject().className()
    ]


def _load_component(source, harness_name):
    QGuiApplication.instance() or QGuiApplication([])
    engine = QQmlEngine()
    component = QQmlComponent(engine)
    component.setData(
        source.encode(),
        QUrl.fromLocalFile(str(ROOT / "tests" / harness_name)),
    )
    assert component.status() == QQmlComponent.Status.Ready, [
        error.toString() for error in component.errors()
    ]
    root = component.create()
    assert root is not None
    QCoreApplication.processEvents()
    return root, engine, component


def _load_transform_badge():
    qml_dir = QML_DIR.resolve().as_uri()
    source = f'''
import QtQuick
import "{qml_dir}" as App

Item {{
    id: root
    width: 800
    height: 600
    property real contentScale: 2.0

    QtObject {{
        id: theme
        property color bgPopover: "#222222"
        property color accentMain: "#ff0088"
        property color textMain: "#ffffff"
        property color accentLow: "#331122"
        property color textAccent: "#ff55aa"
        property int durationState: 0
        property int durationExit: 0
    }}

    Item {{
        id: contentLayer
        x: 30
        y: 40

        Item {{
            id: delegateItem
            x: 100
            y: 50
            width: 200
            height: 100
        }}
    }}

    App.TransformBadge {{
        id: badge
        appTheme: theme
        active: true
        line1: "X: 0"
        anchorX: contentLayer.x
                + (delegateItem.x + delegateItem.width / 2.0)
                * root.contentScale
        anchorY: contentLayer.y
                + (delegateItem.y + delegateItem.height / 2.0)
                * root.contentScale
    }}

    function setGeometry(x, y, width, height, scale) {{
        delegateItem.x = x
        delegateItem.y = y
        delegateItem.width = width
        delegateItem.height = height
        root.contentScale = scale
    }}
    function badgeCenter() {{
        return Qt.point(badge.x + badge.width / 2.0,
                        badge.y + badge.height / 2.0)
    }}
}}
'''
    return _load_component(source, "TransformBadgeHarness.qml")


def _load_resize_handle():
    qml_dir = QML_DIR.resolve().as_uri()
    source = f'''
import QtQuick
import "{qml_dir}" as App

Item {{
    id: root
    width: 400
    height: 300
    property real previewX: 0
    property real previewY: 0
    property real previewWidth: 0
    property real previewHeight: 0
    property real savedX: 0
    property real savedY: 0
    property real savedWidth: 0
    property real savedHeight: 0
    property bool geometryAllowed: true

    QtObject {{
        id: canvasRoot
        property real contentScale: 1.0
        property real visualDetailScale: 1.0
        property double renderOriginX: 0.0
        property double renderOriginY: 0.0
        property double interactiveCoordinateLimit: 281474976710656.0
        property bool snapToGrid: false
        property real gridSize: 100.0
        property bool isLinkMode: false
        property bool isPanning: false
        property bool isEditorResizing: false
        property bool canvasInputBlocked: false
        property bool isNodeDragging: false
        property var activeNodeResizeController: null
        function screenToCanvas(x, y) {{
            return Qt.point(renderOriginX + x, renderOriginY + y)
        }}
    }}

    QtObject {{
        id: nodeModel
        function set_hovered(nodeId, hovered) {{}}
        function preview_position(nodeId, x, y) {{
            root.previewX = x
            root.previewY = y
            delegateItem.x = x - canvasRoot.renderOriginX
            delegateItem.y = y - canvasRoot.renderOriginY
        }}
        function preview_size(nodeId, width, height) {{
            root.previewWidth = width
            root.previewHeight = height
            delegateItem.width = width
            delegateItem.height = height
        }}
        function update_position(nodeId, x, y) {{
            root.savedX = x
            root.savedY = y
            delegateItem.x = x - canvasRoot.renderOriginX
            delegateItem.y = y - canvasRoot.renderOriginY
        }}
        function update_size(nodeId, width, height) {{
            root.savedWidth = width
            root.savedHeight = height
            delegateItem.width = width
            delegateItem.height = height
        }}
    }}

    QtObject {{
        id: theme
        property bool motionEnabled: true
        property int durationState: 140
        property color accentMain: "#ffffff"
        property color resizeHandle: "#aaaaaa"
    }}

    Item {{
        id: delegateItem
        x: 20
        y: 20
        property double worldX: canvasRoot.renderOriginX + x
        property double worldY: canvasRoot.renderOriginY + y
        width: 200
        height: 100
        property bool _isResizing: false
    }}

    App.ResizeHandle {{
        id: handle
        x: 20
        y: 20
        width: 200
        height: 100
        canvasRoot: canvasRoot
        nodeModel: nodeModel
        appTheme: theme
        nodeId: 1
        delegateItem: delegateItem
        nodeWorldX: delegateItem.worldX
        nodeWorldY: delegateItem.worldY
        geometryInteractive: root.geometryAllowed
        topEdgeExclusionWidth: 60
        topEdgeExclusionHeight: 10
    }}

    function inverseScale() {{ return handle._inverseCanvasScale }}
    function iconSize() {{ return handle._iconSize }}
    function iconGeometryScale() {{ return handle._iconGeometryScale }}
    function setHandleSize(width, height) {{
        handle.width = width
        handle.height = height
    }}
    function setContentScale(scale) {{ canvasRoot.contentScale = scale }}
    function setVisualDetailScale(scale) {{
        canvasRoot.visualDetailScale = scale
    }}
    function setSnap(enabled) {{ canvasRoot.snapToGrid = enabled }}
    function setRenderOrigin(x, y) {{
        canvasRoot.renderOriginX = x
        canvasRoot.renderOriginY = y
    }}
    function setWorldPosition(x, y, originX, originY) {{
        canvasRoot.renderOriginX = originX
        canvasRoot.renderOriginY = originY
        delegateItem.x = x - originX
        delegateItem.y = y - originY
    }}
    function setGeometryInteractive(interactive) {{
        root.geometryAllowed = interactive
    }}
    function setNodeDragging(dragging) {{
        canvasRoot.isNodeDragging = dragging
    }}
    function startResize(region) {{ handle.beginResize(region) }}
    function updateResize(region, dx, dy) {{
        handle.updateResize(region, {{
            centroid: {{
                scenePosition: Qt.point(20 + dx, 20 + dy),
                scenePressPosition: Qt.point(20, 20)
            }}
        }})
    }}
    function finishResize() {{ handle.finishResize() }}
    function cancelResize(region) {{ handle.cancelResize(region) }}
    function pendingGeometry() {{
        return [
            handle._pendingX,
            handle._pendingY,
            handle._pendingWidth,
            handle._pendingHeight
        ]
    }}
    function canResize() {{ return handle._canResize }}
    function resizing() {{ return handle._resizing }}
}}
'''
    return _load_component(source, "ResizeHarness.qml")


def _load_node_layers():
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
    property double renderOriginX: 0.0
    property double renderOriginY: 0.0
    property double interactiveCoordinateLimit: 281474976710656.0
    property int propertiesFocusNodeId: 0
    property bool isLinkMode: false
    property bool isPanning: false
    property bool isEditorResizing: false
    property bool canvasInputBlocked: false
    property bool isCtrlHeld: false
    property bool snapToGrid: false
    property real gridSize: 100.0
    property var activeNodeDragController: null
    property var activeNodeResizeController: null
    readonly property bool isNodeDragging:
            activeNodeDragController !== null

    function visibleCanvasRect(margin) {{
        return Qt.rect(
            renderOriginX - 1000,
            renderOriginY - 1000,
            2000,
            2000
        )
    }}
    function visibleRenderRect(margin) {{
        return Qt.rect(-1000, -1000, 2000, 2000)
    }}
    function screenToCanvas(x, y) {{ return Qt.point(x, y) }}

    QtObject {{
        id: nodeModel
        function set_hovered(nodeId, hovered) {{}}
        function clear_hovered() {{}}
        function set_selection(nodeIds) {{}}
        function add_selection(nodeIds) {{}}
        function toggle_selected(nodeId) {{}}
        function get_drag_node_positions(nodeId) {{ return {{}} }}
        function preview_positions(positions) {{}}
        function update_positions(positions) {{}}
        function preview_position(nodeId, x, y) {{}}
        function preview_size(nodeId, width, height) {{}}
        function update_position(nodeId, x, y) {{}}
        function update_size(nodeId, width, height) {{}}
    }}

    QtObject {{
        id: controller
        function handle_link_click(nodeId) {{}}
        function request_open_editor(nodeId) {{}}
        function perform_delete(nodeId) {{}}
    }}

    QtObject {{ id: viewer }}

    QtObject {{
        id: theme
        property bool motionEnabled: true
        property int durationState: 140
        property int durationPanel: 220
        property color accentHigh: "#ffffff"
        property color accentLow: "#221122"
        property color dangerHover: "#ff5555"
        property color bgNode: "#222222"
        property color accentMain: "#ffffff"
        property color borderDefault: "#555555"
        property color borderHover: "#777777"
        property color textMain: "#ffffff"
        property color textDim: "#aaaaaa"
        property color resizeHandle: "#aaaaaa"
        property string textFontFamily: "Segoe UI"
    }}

    Item {{ id: contentLayer }}
    ListModel {{ id: nodes; dynamicRoles: true }}

    App.NodeLayer {{
        anchors.fill: parent
        viewportModel: nodes
        canvasRoot: root
        nodeModel: nodeModel
        canvasController: controller
        viewerController: viewer
        contentLayer: contentLayer
        appTheme: theme
        framesOnly: true
    }}

    App.NodeLayer {{
        anchors.fill: parent
        viewportModel: nodes
        canvasRoot: root
        nodeModel: nodeModel
        canvasController: controller
        viewerController: viewer
        contentLayer: contentLayer
        appTheme: theme
        framesOnly: false
    }}

    Component.onCompleted: nodes.append({{
        nodeId: 1,
        nodeX: 20,
        nodeY: 20,
        nodeWidth: 200,
        nodeHeight: 120,
        nodeType: "text",
        nodeIsSelected: false,
        nodeIsHovered: false,
        nodeIsDeleting: false,
        nodeTitle: "Node",
        nodeContent: "",
        nodeTitleSize: 14,
        nodeTextSize: 12,
        nodeTags: [],
        nodeFrameLocked: false,
        nodeFrameColor: "",
        nodeFrameOpacity: 0.2,
        nodeMediaType: "",
        nodeMetaSummary: "",
        nodeMediaDuration: 0,
        audioWaveform: []
    }})

    function setHovered(hovered) {{
        nodes.setProperty(0, "nodeIsHovered", hovered)
    }}
    function setFrameSelected(selected) {{
        nodes.setProperty(0, "nodeType", "frame")
        nodes.setProperty(0, "nodeIsSelected", selected)
    }}
    function setWorldPosition(x, y, originX, originY) {{
        root.renderOriginX = originX
        root.renderOriginY = originY
        nodes.setProperty(0, "nodeX", x)
        nodes.setProperty(0, "nodeY", y)
    }}
}}
'''
    return _load_component(source, "NodeLayerHarness.qml")


def _load_drag_controller():
    qml_dir = QML_DIR.resolve().as_uri()
    source = f'''
import QtQuick
import "{qml_dir}" as App

Item {{
    id: root
    width: 800
    height: 600
    property real previewX: 0
    property real previewY: 0
    property real savedX: 0
    property real savedY: 0
    property double baseWorldX: 20
    property double baseWorldY: 20
    property bool geometryAllowed: true

    QtObject {{
        id: canvasRoot
        property bool canvasInputBlocked: false
        property bool isLinkMode: false
        property bool isPanning: false
        property bool isEditorResizing: false
        property bool isCtrlHeld: false
        property bool snapToGrid: true
        property real gridSize: 100
        property real contentScale: 1.0
        property var activeNodeDragController: null
        property double renderOriginX: 0.0
        property double renderOriginY: 0.0
        property double interactiveCoordinateLimit: 281474976710656.0
        function screenToCanvas(x, y) {{
            return Qt.point(renderOriginX + x, renderOriginY + y)
        }}
    }}

    QtObject {{
        id: nodeModel
        function clear_hovered() {{}}
        function set_selection(nodeIds) {{}}
        function add_selection(nodeIds) {{}}
        function get_drag_node_positions(nodeId) {{
            return [{{
                "id": nodeId,
                "x": root.baseWorldX,
                "y": root.baseWorldY
            }}]
        }}
        function preview_positions(positions) {{
            if (positions.length <= 0) return
            root.previewX = positions[0].x
            root.previewY = positions[0].y
            delegateItem.x = positions[0].x - canvasRoot.renderOriginX
            delegateItem.y = positions[0].y - canvasRoot.renderOriginY
        }}
        function update_positions(positions) {{
            if (positions.length <= 0) return
            root.savedX = positions[0].x
            root.savedY = positions[0].y
        }}
    }}

    Item {{ id: contentLayer }}
    Item {{
        id: delegateItem
        x: 20
        y: 20
        property double worldX: canvasRoot.renderOriginX + x
        property double worldY: canvasRoot.renderOriginY + y
        width: 200
        height: 100
    }}

    App.NodeDragController {{
        id: dragController
        width: delegateItem.width
        height: delegateItem.height
        canvasRoot: canvasRoot
        nodeModel: nodeModel
        contentLayer: contentLayer
        delegateItem: delegateItem
        nodeWorldX: delegateItem.worldX
        nodeWorldY: delegateItem.worldY
        geometryInteractive: root.geometryAllowed
        nodeId: 1
        nodeType: "text"
        nodeIsSelected: true
    }}

    function beginDrag() {{ dragController.beginDrag() }}
    function setRenderOrigin(x, y) {{
        canvasRoot.renderOriginX = x
        canvasRoot.renderOriginY = y
        root.baseWorldX = x + 20
        root.baseWorldY = y + 20
    }}
    function setWorldPosition(x, y, originX, originY) {{
        canvasRoot.renderOriginX = originX
        canvasRoot.renderOriginY = originY
        root.baseWorldX = x
        root.baseWorldY = y
        delegateItem.x = x - originX
        delegateItem.y = y - originY
    }}
    function setGeometryInteractive(interactive) {{
        root.geometryAllowed = interactive
    }}
    function movePointer(x, y) {{
        dragController.updateDrag({{
            centroid: {{
                scenePosition: Qt.point(x, y),
                scenePressPosition: Qt.point(40, 40)
            }}
        }})
    }}
    function setResizeHovered(hovered) {{
        dragController.resizeHovered = hovered
    }}
    function canDrag() {{ return dragController.canDrag }}
    function finishDrag() {{ dragController.finishDrag() }}
    function cancelDrag() {{ dragController.cancelDrag() }}
}}
'''
    return _load_component(source, "NodeDragHarness.qml")


def _regions(handle):
    return [
        child
        for child in _walk_items(handle)
        if child.property("horizontalDirection") is not None
        and child.property("verticalDirection") is not None
    ]


def _contains(region, x, y):
    return (
        region.property("x") <= x <= region.property("x") + region.property("width")
        and region.property("y") <= y <= region.property("y") + region.property("height")
    )


def test_resize_regions_remain_unchanged_and_leave_the_content_clear():
    root, _engine, _component = _load_resize_handle()
    handle = _class_items(root, "ResizeHandle")[0]
    regions = _regions(handle)

    assert len(regions) == 9
    expected_points = {
        (-1, -1): (2, 2),
        (1, -1): (198, 2),
        (-1, 0): (2, 50),
        (1, 0): (198, 50),
        (-1, 1): (2, 98),
        (1, 1): (198, 98),
    }
    for direction, point in expected_points.items():
        assert any(
            region.property("horizontalDirection") == direction[0]
            and region.property("verticalDirection") == direction[1]
            and _contains(region, *point)
            for region in regions
        )

    assert not any(_contains(region, 100, 4) for region in regions)
    assert not any(_contains(region, 100, 50) for region in regions)


def test_resize_geometry_uses_frozen_visual_detail_scale():
    root, _engine, _component = _load_resize_handle()

    assert root.inverseScale() == pytest.approx(1.0)
    root.setContentScale(2.0)
    assert root.inverseScale() == pytest.approx(1.0)
    root.setVisualDetailScale(0.5)
    assert root.inverseScale() == pytest.approx(2.0)


def test_resize_grip_geometry_shrinks_to_fit_a_zoomed_out_node():
    root, _engine, _component = _load_resize_handle()

    root.setHandleSize(100, 50)
    root.setVisualDetailScale(0.1)
    QCoreApplication.processEvents()

    assert root.inverseScale() == pytest.approx(4.0)
    assert root.iconSize() == pytest.approx(25.0)
    assert root.iconGeometryScale() == pytest.approx(1.25)


def test_snap_resize_keeps_preview_and_persists_top_left_geometry():
    root, _engine, _component = _load_resize_handle()
    handle = _class_items(root, "ResizeHandle")[0]
    top_left = next(
        region
        for region in _regions(handle)
        if region.property("horizontalDirection") == -1
        and region.property("verticalDirection") == -1
    )

    root.setSnap(True)
    root.startResize(top_left)
    assert root.resizing()

    root.setNodeDragging(True)
    assert root.canResize()
    root.updateResize(top_left, -71, -71)
    first = root.pendingGeometry().toVariant()
    root.updateResize(top_left, -119, -119)
    second = root.pendingGeometry().toVariant()

    assert first == pytest.approx([-80, -80, 300, 200])
    assert second == pytest.approx(first)

    root.finishResize()
    assert not root.resizing()
    assert root.property("savedX") == pytest.approx(-80)
    assert root.property("savedY") == pytest.approx(-80)
    assert root.property("savedWidth") == pytest.approx(300)
    assert root.property("savedHeight") == pytest.approx(200)


def test_resize_persists_world_geometry_with_a_large_render_origin():
    root, _engine, _component = _load_resize_handle()
    handle = _class_items(root, "ResizeHandle")[0]
    top_left = next(
        region
        for region in _regions(handle)
        if region.property("horizontalDirection") == -1
        and region.property("verticalDirection") == -1
    )
    origin_x = 20_000_000
    origin_y = -20_000_000

    root.setRenderOrigin(origin_x, origin_y)
    root.setSnap(True)
    root.startResize(top_left)
    root.updateResize(top_left, -71, -71)
    root.finishResize()

    assert root.property("savedX") == pytest.approx(origin_x - 80)
    assert root.property("savedY") == pytest.approx(origin_y - 80)
    assert root.property("savedWidth") == pytest.approx(300)
    assert root.property("savedHeight") == pytest.approx(200)


def test_resize_clamps_top_left_at_the_interactive_boundary_and_can_cancel():
    root, _engine, _component = _load_resize_handle()
    handle = _class_items(root, "ResizeHandle")[0]
    top_left = next(
        region
        for region in _regions(handle)
        if region.property("horizontalDirection") == -1
        and region.property("verticalDirection") == -1
    )
    limit = CANVAS_INTERACTIVE_COORDINATE_LIMIT
    root.setWorldPosition(-limit + 20, -limit + 20, -limit, -limit)
    root.setSnap(True)

    root.startResize(top_left)
    root.updateResize(top_left, -1000, -1000)
    pending = root.pendingGeometry().toVariant()

    assert pending == pytest.approx([-limit, -limit, 220, 120])

    root.cancelResize(top_left)
    assert not root.resizing()
    assert root.property("previewX") == pytest.approx(-limit + 20)
    assert root.property("previewY") == pytest.approx(-limit + 20)
    assert root.property("previewWidth") == pytest.approx(200)
    assert root.property("previewHeight") == pytest.approx(100)
    assert root.property("savedWidth") == pytest.approx(0)


def test_resize_clamps_top_left_at_the_positive_interactive_boundary():
    root, _engine, _component = _load_resize_handle()
    handle = _class_items(root, "ResizeHandle")[0]
    top_left = next(
        region
        for region in _regions(handle)
        if region.property("horizontalDirection") == -1
        and region.property("verticalDirection") == -1
    )
    limit = CANVAS_INTERACTIVE_COORDINATE_LIMIT
    root.setWorldPosition(limit - 20, limit - 20, limit, limit)

    root.startResize(top_left)
    root.updateResize(top_left, 1000, 1000)
    pending = root.pendingGeometry().toVariant()

    assert pending == pytest.approx([limit, limit, 180, 80])

    root.finishResize()
    assert root.property("savedX") == pytest.approx(limit)
    assert root.property("savedY") == pytest.approx(limit)
    assert root.property("savedWidth") == pytest.approx(180)
    assert root.property("savedHeight") == pytest.approx(80)


def test_viewport_retains_transform_node_until_resize_commit_unwinds():
    model = NodeListModel()
    model.add_node(1, "text", 0, 0, 200, 100)
    proxy = NodeViewportProxyModel(model)
    proxy.updateViewport(-100, -100, 100, 100)
    QCoreApplication.processEvents()
    assert proxy.rowCount() == 1

    proxy.retainTransformNodes([1])
    model.preview_position(1, 10_000, 10_000)
    model.update_position(1, 10_000, 10_000)
    QCoreApplication.processEvents()
    assert proxy.rowCount() == 1

    proxy.releaseTransformNodes()
    QCoreApplication.processEvents()
    assert proxy.rowCount() == 0


def test_fast_snap_drag_remains_active_outside_node_and_persists():
    root, _engine, _component = _load_drag_controller()

    root.beginDrag()
    root.movePointer(410, 310)
    assert root.property("previewX") == pytest.approx(400)
    assert root.property("previewY") == pytest.approx(300)

    root.setResizeHovered(True)
    assert root.canDrag()
    root.movePointer(690, 550)
    assert root.property("previewX") == pytest.approx(700)
    assert root.property("previewY") == pytest.approx(500)

    root.finishDrag()
    assert root.property("savedX") == pytest.approx(700)
    assert root.property("savedY") == pytest.approx(500)


def test_drag_persists_world_coordinates_with_a_large_render_origin():
    root, _engine, _component = _load_drag_controller()
    origin_x = 20_000_000
    origin_y = -20_000_000

    root.setRenderOrigin(origin_x, origin_y)
    root.beginDrag()
    root.movePointer(410, 310)
    root.finishDrag()

    assert root.property("savedX") == pytest.approx(origin_x + 400)
    assert root.property("savedY") == pytest.approx(origin_y + 300)


def test_drag_clamps_to_the_interactive_boundary_without_distorting_delta():
    root, _engine, _component = _load_drag_controller()
    limit = CANVAS_INTERACTIVE_COORDINATE_LIMIT
    root.setWorldPosition(limit - 20, -limit + 20, limit, -limit)

    root.beginDrag()
    root.movePointer(1040, -960)

    assert root.property("previewX") == pytest.approx(limit)
    assert root.property("previewY") == pytest.approx(-limit)

    root.finishDrag()
    assert root.property("savedX") == pytest.approx(limit)
    assert root.property("savedY") == pytest.approx(-limit)


def test_legacy_geometry_is_read_only_without_persistence_signals():
    model = NodeListModel()
    model.add_node(1, "text", 1e38, -1e38, 200, 100)
    position_writes = []
    size_writes = []
    model.node_position_changed.connect(
        lambda *values: position_writes.append(values)
    )
    model.node_size_changed.connect(lambda *values: size_writes.append(values))

    assert not model.is_geometry_interactive(1)
    model.preview_position(1, 10, 20)
    model.update_position(1, 10, 20)
    model.preview_size(1, 400, 300)
    model.update_size(1, 400, 300)

    node = model.get_node_data(1)
    assert node["x"] == pytest.approx(1e38)
    assert node["y"] == pytest.approx(-1e38)
    assert node["width"] == pytest.approx(200)
    assert node["height"] == pytest.approx(100)
    assert position_writes == []
    assert size_writes == []


def test_model_clamps_a_position_batch_with_one_shared_translation():
    model = NodeListModel()
    limit = CANVAS_INTERACTIVE_COORDINATE_LIMIT
    model.add_node(1, "text", limit - 50, 0, 200, 100)
    model.add_node(2, "text", limit - 10, 40, 200, 100)

    model.preview_positions([
        {"id": 1, "x": limit + 100, "y": -limit - 100},
        {"id": 2, "x": limit + 140, "y": -limit - 60},
    ])

    first = model.get_node_data(1)
    second = model.get_node_data(2)
    assert first["x"] == pytest.approx(limit - 40)
    assert second["x"] == pytest.approx(limit)
    assert first["y"] == pytest.approx(-limit)
    assert second["y"] == pytest.approx(-limit + 40)
    assert second["x"] - first["x"] == pytest.approx(40)
    assert second["y"] - first["y"] == pytest.approx(40)


def test_only_matching_layer_loads_a_full_delegate_and_resize_is_lazy():
    root, _engine, _component = _load_node_layers()

    delegates = _class_items(root, "NodeDelegate")
    assert len(delegates) == 1
    assert _class_items(root, "ResizeHandle") == []

    root.setHovered(True)
    QCoreApplication.processEvents()
    assert len(_class_items(root, "ResizeHandle")) == 1

    delegate = delegates[0]
    delegate.setProperty("_isResizing", True)
    root.setHovered(False)
    QCoreApplication.processEvents()
    assert len(_class_items(root, "ResizeHandle")) == 1

    delegate.setProperty("_isResizing", False)
    QCoreApplication.processEvents()
    assert _class_items(root, "ResizeHandle") == []

    root.setFrameSelected(True)
    QCoreApplication.processEvents()
    assert len(_class_items(root, "ResizeHandle")) == 1


def test_node_delegate_exposes_only_render_local_item_coordinates():
    root, _engine, _component = _load_node_layers()
    delegate = _class_items(root, "NodeDelegate")[0]

    root.setWorldPosition(
        20_000_123.25,
        -19_999_543.75,
        20_000_000,
        -20_000_000,
    )
    QCoreApplication.processEvents()

    assert delegate.property("worldX") == pytest.approx(20_000_123.25)
    assert delegate.property("worldY") == pytest.approx(-19_999_543.75)
    assert delegate.x() == pytest.approx(123.25)
    assert delegate.y() == pytest.approx(456.25)


@pytest.mark.parametrize("coordinate", [1e38, -1e38])
def test_node_delegate_remains_visible_at_extreme_world_coordinates(
    coordinate,
):
    root, _engine, _component = _load_node_layers()
    delegate = _class_items(root, "NodeDelegate")[0]

    root.setWorldPosition(coordinate, -coordinate, coordinate, -coordinate)
    QCoreApplication.processEvents()

    assert delegate.property("worldX") == pytest.approx(coordinate)
    assert delegate.property("worldY") == pytest.approx(-coordinate)
    assert delegate.x() == pytest.approx(0.0)
    assert delegate.y() == pytest.approx(0.0)
    assert delegate.property("isInViewport")
    assert delegate.isVisible()
    assert not delegate.property("geometryInteractive")
    assert _class_items(root, "ResizeHandle") == []


def test_transform_badge_tracks_delegate_local_geometry_bindings():
    canvas_source = (QML_DIR / "Canvas.qml").read_text(encoding="utf-8")
    anchor_source = canvas_source.split(
        "function transformAnchor()", 1
    )[1].split("// Drag & Drop", 1)[0]

    assert "viewport.renderToScreen(" in anchor_source
    assert "controller.delegateItem.x" in anchor_source
    assert "controller.delegateItem.y" in anchor_source
    assert "controller.delegateItem.width / 2.0" in anchor_source
    assert "controller.delegateItem.height / 2.0" in anchor_source
    assert "mapToItem(" not in anchor_source
    assert "controller.nodeWorldX" not in anchor_source
    assert "controller.nodeWorldY" not in anchor_source

    root, _engine, _component = _load_transform_badge()
    center = root.badgeCenter()
    assert center.x() == pytest.approx(430.0)
    assert center.y() == pytest.approx(240.0)

    root.setGeometry(170.0, -20.0, 300.0, 120.0, 0.5)
    QCoreApplication.processEvents()
    center = root.badgeCenter()
    assert center.x() == pytest.approx(190.0)
    assert center.y() == pytest.approx(60.0)


def test_resize_handle_keeps_its_existing_pointer_handler_implementation():
    resize_source = (QML_DIR / "ResizeHandle.qml").read_text(encoding="utf-8")
    delegate_source = (QML_DIR / "NodeDelegate.qml").read_text(encoding="utf-8")

    assert resize_source.count("ResizeRegion {") == 9
    assert resize_source.count(
        "grabPermissions: PointerHandler.CanTakeOverFromItems"
    ) == 1
    assert "HoverHandler" in resize_source
    assert "DragHandler" in resize_source
    assert "handle._resizing" in resize_source
    end_session = resize_source.split(
        "function _endResizeSession()", 1
    )[1].split("\n    Component.onDestruction:", 1)[0]
    assert end_session.index("handle._resizing = false") < end_session.index(
        "handle.delegateItem._isResizing = false"
    )
    assert "retainTransformNodes([handle.nodeId])" in resize_source
    assert "releaseTransformNodes()" in resize_source
    drag_source = (QML_DIR / "NodeDragController.qml").read_text(
        encoding="utf-8"
    )
    assert drag_source.count(
        "grabPermissions: PointerHandler.CanTakeOverFromItems"
    ) == 5
    assert "dragController.dragging" in drag_source
    frame_source = (QML_DIR / "FrameNode.qml").read_text(encoding="utf-8")
    assert "grabPermissions: PointerHandler.CanTakeOverFromItems" in frame_source
    assert "_resizer._pointerHovered" in delegate_source
    assert "|| delegateRoot._resizePointerHovered" in delegate_source
    assert "|| delegateRoot.nodeTransforming" in delegate_source
