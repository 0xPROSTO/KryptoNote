from pathlib import Path

import pytest
from PySide6.QtCore import QCoreApplication, QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlComponent, QQmlEngine
from PySide6.QtQuick import QQuickItem

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


def _load_resize_handle():
    qml_dir = QML_DIR.resolve().as_uri()
    source = f'''
import QtQuick
import "{qml_dir}" as App

Item {{
    id: root
    width: 400
    height: 300

    QtObject {{
        id: canvasRoot
        property real contentScale: 1.0
        property real visualDetailScale: 1.0
        property bool snapToGrid: false
        property real gridSize: 100.0
        property bool isLinkMode: false
        property bool isPanning: false
        property bool isEditorResizing: false
        property var activeNodeResizeController: null
        function screenToCanvas(x, y) {{ return Qt.point(x, y) }}
    }}

    QtObject {{
        id: nodeModel
        function preview_position(nodeId, x, y) {{}}
        function preview_size(nodeId, width, height) {{}}
        function update_position(nodeId, x, y) {{}}
        function update_size(nodeId, width, height) {{}}
    }}

    QtObject {{
        id: theme
        property bool motionEnabled: true
        property color accentMain: "#ffffff"
        property color resizeHandle: "#aaaaaa"
    }}

    Item {{
        id: delegateItem
        x: 20
        y: 20
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
    property int propertiesFocusNodeId: 0
    property bool isLinkMode: false
    property bool isPanning: false
    property bool isEditorResizing: false
    property bool isCtrlHeld: false
    property bool snapToGrid: false
    property real gridSize: 100.0
    property var activeNodeDragController: null
    property var activeNodeResizeController: null

    function visibleCanvasRect(margin) {{
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
}}
'''
    return _load_component(source, "NodeLayerHarness.qml")


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


def test_resize_handle_keeps_its_existing_pointer_handler_implementation():
    resize_source = (QML_DIR / "ResizeHandle.qml").read_text(encoding="utf-8")
    delegate_source = (QML_DIR / "NodeDelegate.qml").read_text(encoding="utf-8")

    assert resize_source.count("ResizeRegion {") == 9
    assert "HoverHandler" in resize_source
    assert "DragHandler" in resize_source
    assert "nodeHover.hovered || _isHovered" in resize_source
    assert "_resizer._pointerHovered" in delegate_source
    assert "|| delegateRoot._resizePointerHovered" in delegate_source
