import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QObject, QPoint, QUrl, Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlComponent, QQmlEngine, QQmlExpression
from PySide6.QtTest import QTest

from KryptoNote.gui.controllers.command_palette_controller import (
    CommandPaletteController,
    RightShiftDoublePressDetector,
)

ROOT = Path(__file__).resolve().parents[1]
QML_DIR = ROOT / "KryptoNote" / "gui" / "qml"


class _FakeAction:
    def __init__(self, enabled=True):
        self.enabled = enabled
        self.trigger_count = 0

    def isEnabled(self):
        return self.enabled

    def trigger(self):
        self.trigger_count += 1


class _FakeOperations:
    is_busy = False


class _FakeRoot:
    def property(self, _name):
        return False


class _FakeView:
    def rootObject(self):
        return _FakeRoot()


class _FakeWindow:
    view = _FakeView()

    def __init__(self):
        self.dashboard_count = 0

    def open_dashboard(self):
        self.dashboard_count += 1


class _FakeNodeModel:
    def __init__(self, nodes=()):
        self._nodes = {node["id"]: dict(node) for node in nodes}
        self.selected = [node["id"] for node in nodes if node.get("selected")]

    def get_selected_ids(self):
        return list(self.selected)

    def get_node_data(self, node_id):
        return self._nodes.get(node_id)


class _FakeCanvas:
    def __getattr__(self, _name):
        return lambda *args, **kwargs: True

    def is_frame_locked(self, _node_id):
        return False


class _FakeKeyEvent:
    def __init__(self, scan=0, virtual=0, *, auto_repeat=False, key=Qt.Key.Key_Shift):
        self._scan = scan
        self._virtual = virtual
        self._auto_repeat = auto_repeat
        self._key = key

    def key(self):
        return self._key

    def nativeScanCode(self):
        return self._scan

    def nativeVirtualKey(self):
        return self._virtual

    def isAutoRepeat(self):
        return self._auto_repeat


def _controller(nodes=()):
    window = _FakeWindow()
    controller = CommandPaletteController(
        _FakeNodeModel(nodes),
        _FakeCanvas(),
        _FakeOperations(),
        window,
    )
    return controller, window


def test_command_ranking_favorites_and_action_execution():
    controller, _window = _controller()
    triggered = []
    controller.register_command(
        "add-text",
        lambda: triggered.append("text"),
        label="Add text node",
        aliases=("add note",),
        keywords=("create",),
        favorite=True,
    )
    controller.register_command(
        "add-frame",
        lambda: triggered.append("frame"),
        label="Add frame",
        keywords=("group",),
        favorite=True,
    )
    controller.register_command(
        "select-all",
        lambda: triggered.append("select"),
        label="Select all nodes",
        keywords=("canvas",),
    )
    controller.register_command(
        "about",
        lambda: triggered.append("about"),
        label="About KryptoNote",
        favorite=True,
    )

    assert [row["id"] for row in controller.query_commands("")] == [
        "add-text",
        "add-frame",
        "about",
    ]
    assert [row["id"] for row in controller.query_commands("add")] == [
        "add-text",
        "add-frame",
    ]
    assert [row["id"] for row in controller.query_commands("fr")] == [
        "add-frame"
    ]
    assert [row["id"] for row in controller.query_commands("abo")] == [
        "about"
    ]

    action = _FakeAction()
    controller.register_action(
        "save",
        action,
        label="Save project",
        shortcut="Ctrl+S",
    )
    assert controller.execute_command("save")
    assert action.trigger_count == 1
    action.enabled = False
    assert not controller.execute_command("save")
    assert controller.query_commands("save")[0]["enabled"] is False


def test_context_commands_follow_the_current_selection():
    controller, _window = _controller(
        ({"id": 7, "type": "frame", "selected": True},)
    )
    controller.register_context_commands()

    frame_commands = {
        row["id"] for row in controller.query_commands("frame")
    }
    assert {
        "edit-selected-frame",
        "toggle-selected-frame-lock",
        "select-frame-contents",
    }.issubset(frame_commands)

    controller._node_model.selected = []
    assert "delete-selection" not in {
        row["id"] for row in controller.query_commands("delete")
    }


def test_double_right_shift_requires_release_and_rejects_left_or_repeat():
    now = [1000.0]
    detector = RightShiftDoublePressDetector(lambda: now[0])
    right = _FakeKeyEvent(scan=0x36)
    left = _FakeKeyEvent(scan=0x2A)

    assert not detector.handle_press(right, "win32")
    assert not detector.handle_press(right, "win32")
    detector.handle_release(right, "win32")
    now[0] += 200
    assert detector.handle_press(right, "win32")

    detector.reset()
    assert not detector.handle_press(left, "win32")
    detector.handle_release(left, "win32")
    now[0] += 100
    assert not detector.handle_press(left, "win32")

    detector.reset()
    repeated = _FakeKeyEvent(scan=0x36, auto_repeat=True)
    assert not detector.handle_press(repeated, "win32")
    assert RightShiftDoublePressDetector.is_right_shift_event(
        _FakeKeyEvent(virtual=0xFFE2), "linux"
    )
    assert RightShiftDoublePressDetector.is_right_shift_event(
        _FakeKeyEvent(virtual=0x3C), "darwin"
    )


def _load_palette():
    QGuiApplication.instance() or QGuiApplication([])
    engine = QQmlEngine()
    qml_dir = QML_DIR.resolve().as_uri()
    source = f'''
import QtQuick
import QtQuick.Controls.Basic
import "{qml_dir}" as App

ApplicationWindow {{
    id: root
    objectName: "paletteHarness"
    width: 900
    height: 720
    visible: true
    color: "#121212"
    property string executedCommand: ""
    property int centeredNode: 0
    property string fullSearchQuery: ""
    property int backgroundClicks: 0
    property bool priorFocused: priorFocus.activeFocus

    TextField {{
        id: priorFocus
        objectName: "priorFocus"
        width: 120
        height: 30
        focus: true
    }}

    MouseArea {{
        anchors.fill: parent
        onClicked: root.backgroundClicks += 1
    }}

    QtObject {{
        id: theme
        property bool motionEnabled: true
        property int durationPress: 80
        property int durationState: 140
        property int durationPanel: 220
        property int durationExit: 80
        property color overlayDim: "#99000000"
        property color bgPopover: "#232425"
        property color borderHover: "#555b62"
        property color bgInput: "#161616"
        property color accentMain: "#e6158b"
        property color borderDefault: "#3a3e43"
        property color textDim: "#bbbbbb"
        property color textMain: "#efefef"
        property color textMuted: "#92979f"
        property color borderSubtle: "#303337"
        property color accentLow: "#3a1025"
        property color bgControlHover: "#35393e"
        property color textDisabled: "#666666"
    }}

    QtObject {{
        id: commandController
        function commandRow(id, label) {{
            return {{
                "id": id,
                "label": label,
                "shortcut": "",
                "icon": "",
                "enabled": true,
                "reason": ""
            }}
        }}
        function query_commands(query) {{
            if (query === "") return [
                commandRow("add-text", "Add text node"),
                commandRow("select-all", "Select all nodes"),
                commandRow("about", "About KryptoNote")
            ]
            if (query === "many") {{
                var commands = []
                for (var i = 0; i < 30; i++)
                    commands.push(commandRow("many-" + i, "Many command " + i))
                return commands
            }}
            if (query === "frame")
                return [commandRow("add-frame", "Add frame")]
            return []
        }}
        function execute_command(commandId) {{
            root.executedCommand = commandId
            return true
        }}
    }}

    QtObject {{
        id: nodeModel
        property int lastLimit: 0
        function search_nodes_by_filters(
            query, tags, minChars, maxChars, after, before, sortKey, limit
        ) {{
            lastLimit = limit
            var rows = []
            for (var i = 0; i < Math.min(12, limit); i++) {{
                rows.push({{
                    "nodeId": i + 1,
                    "type": "text",
                    "title": "Needle note " + (i + 1),
                    "preview": "A needle appears in this result " + (i + 1)
                }})
            }}
            return rows
        }}
    }}

    App.CommandPalette {{
        id: palette
        appTheme: theme
        commandController: commandController
        nodeModel: nodeModel
        onRequestedCenter: function(nodeId) {{ root.centeredNode = nodeId }}
        onRequestedFullSearch: function(query) {{ root.fullSearchQuery = query }}
        onRestoreFocusRequested: priorFocus.forceActiveFocus()
    }}
}}
'''.encode()
    component = QQmlComponent(engine)
    component.setData(
        source,
        QUrl.fromLocalFile(str(ROOT / "tests" / "CommandPaletteHarness.qml")),
    )
    assert component.status() == QQmlComponent.Status.Ready, [
        error.toString() for error in component.errors()
    ]
    window = component.create()
    assert window is not None
    palette = window.findChild(QObject, "commandPalette")
    assert palette is not None
    QTest.qWait(30)
    return window, palette, engine, component


def _load_context_menu():
    QGuiApplication.instance() or QGuiApplication([])
    engine = QQmlEngine()
    qml_dir = QML_DIR.resolve().as_uri()
    source = f'''
import QtQuick
import QtQuick.Controls
import "{qml_dir}" as App

ApplicationWindow {{
    id: root
    width: 640
    height: 480
    visible: true
    property bool shiftHeld: false

    Item {{ id: sourceItem; width: 120; height: 80 }}

    QtObject {{
        id: theme
        property bool motionEnabled: false
        property int durationState: 0
        property int durationExit: 0
        property color bgPopover: "#232425"
        property color borderDefault: "#3a3e43"
        property color accentMain: "#e6158b"
        property color accentLow: "#3a1025"
        property color bgControlHover: "#35393e"
        property color bgControlPressed: "#44484e"
        property color textMain: "#efefef"
        property color textMuted: "#92979f"
        property color btnCancelText: "#ff7777"
    }}

    QtObject {{
        id: canvasController
        property bool snap_to_grid: false
        function is_frame_locked(nodeId) {{ return false }}
        function request_open_editor(nodeId) {{}}
        function rename_node(nodeId) {{}}
        function auto_fit_node(nodeId) {{}}
        function duplicate_node(nodeId) {{}}
        function copy_nodes(nodeId) {{}}
        function paste_nodes() {{}}
        function copy_to_system_clipboard(nodeId) {{}}
        function paste_from_system_clipboard() {{}}
        function show_node_properties(nodeId) {{}}
        function request_animated_delete(nodeId) {{}}
        function delete_node_from_context(nodeId, bypassConfirmation) {{}}
    }}

    App.NodeContextMenu {{
        id: contextMenu
        objectName: "nodeContextMenu"
        appTheme: theme
        canvasController: canvasController
        shiftHeld: root.shiftHeld
    }}

    function openNodeMenu() {{
        contextMenu.openForNode(1, "text", sourceItem, 8, 8)
    }}
    function focusedMenuIndex() {{
        return contextMenu.menuEntries().indexOf(root.activeFocusItem)
    }}
}}
'''.encode()
    component = QQmlComponent(engine)
    component.setData(
        source,
        QUrl.fromLocalFile(str(ROOT / "tests" / "NodeContextMenuHarness.qml")),
    )
    assert component.status() == QQmlComponent.Status.Ready, [
        error.toString() for error in component.errors()
    ]
    window = component.create()
    assert window is not None
    menu = window.findChild(QObject, "nodeContextMenu")
    assert menu is not None
    QTest.qWait(20)
    return window, menu, engine, component


def test_qml_palette_focus_navigation_search_limit_and_modal_close():
    window, palette, _engine, _component = _load_palette()
    palette.openPalette()
    QTest.qWait(40)

    assert palette.property("visible")
    assert palette.property("actionCount") == 3
    assert palette.property("selectedTitle") == "Add text node"
    assert palette.property("inputFocused")

    QTest.keyClick(window, Qt.Key.Key_Down)
    assert palette.property("selectedTitle") == "Select all nodes"
    QTest.keyClick(window, Qt.Key.Key_Tab)
    assert palette.property("queryText") == "Select all nodes"

    palette.setProperty("queryText", "needle")
    QTest.qWait(90)
    assert palette.property("actionCount") == 11
    assert palette.property("selectedKind") == "search"
    QTest.keyClick(window, Qt.Key.Key_Return)
    QTest.qWait(240)
    assert not palette.property("visible")
    assert window.property("centeredNode") == 1
    assert window.property("priorFocused")

    palette.openPalette()
    QTest.qWait(30)
    QTest.mouseClick(window, Qt.MouseButton.LeftButton, pos=QPoint(5, 5))
    QTest.qWait(240)
    assert not palette.property("visible")
    assert window.property("backgroundClicks") == 0


def test_pointer_opened_context_menu_starts_neutral_and_accepts_down():
    window, menu, _engine, _component = _load_context_menu()
    window.openNodeMenu()
    QTest.qWait(30)

    assert menu.property("visible")
    assert not menu.property("keyboardNavigationActive")
    assert window.focusedMenuIndex() == -1

    QTest.keyClick(window, Qt.Key.Key_Down)
    assert menu.property("keyboardNavigationActive")
    assert window.focusedMenuIndex() == 0


def test_qml_palette_caps_the_viewport_and_keeps_overflow_scrollable():
    window, palette, _engine, _component = _load_palette()
    window.setHeight(1200)
    palette.openPalette()
    palette.setProperty("queryText", "many")
    QTest.qWait(90)

    assert palette.property("actionCount") == 41
    assert palette.property("height") <= window.height() - 32
    assert palette.property("listContentHeight") > palette.property("listViewportHeight")

    first_index = palette.property("selectedIndex")
    QTest.keyClick(window, Qt.Key.Key_PageDown)
    page_down_index = palette.property("selectedIndex")
    assert page_down_index > first_index

    QTest.keyClick(window, Qt.Key.Key_PageUp)
    assert palette.property("selectedIndex") == first_index
    QTest.keyClick(window, Qt.Key.Key_PageUp)
    assert palette.property("selectedIndex") == first_index

    palette.selectBoundary(False)
    last_index = palette.property("selectedIndex")
    QTest.keyClick(window, Qt.Key.Key_PageDown)
    assert palette.property("selectedIndex") == last_index


def test_qml_palette_search_rebuild_highlights_the_selected_delegate_only():
    window, palette, _engine, _component = _load_palette()
    palette.openPalette()
    palette.setProperty("queryText", "frame")
    QTest.qWait(100)

    result_list = palette.findChild(QObject, "commandPaletteResults")
    assert result_list is not None
    expression = QQmlExpression(
        QQmlEngine.contextForObject(result_list),
        result_list,
        """
        (function() {
            var highlighted = []
            for (var index = 0; index < count; ++index) {
                var item = itemAtIndex(index)
                if (item && item.visuallyHighlighted)
                    highlighted.push(index)
            }
            return highlighted.join(",")
        })()
        """,
    )
    highlighted_indexes, undefined = expression.evaluate()

    assert not undefined
    assert not expression.hasError(), expression.error().toString()
    assert highlighted_indexes == str(palette.property("selectedIndex"))
    assert palette.property("selectedKind") == "command"

    source = (QML_DIR / "CommandPalette.qml").read_text(encoding="utf-8")
    assert "keyboardHighlightMotion" not in source
