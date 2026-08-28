pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls
import QtQuick.Window


Popup {
    id: contextPopup
    required property var canvasController
    required property var appTheme
    required property bool shiftHeld
    width: 236
    parent: Overlay.overlay
    padding: 4
    modal: true
    dim: false
    focus: true
    closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside
    opacity: 1.0
    scale: 1.0
    transformOrigin: Item.TopLeft

    property int nodeId: 0
    property string targetKind: "node"
    property int connId: 0
    property string nodeType: "text"
    property bool frameLocked: false
    property real canvasX: 0
    property real canvasY: 0
    property real motionOffset: 0
    property bool snapToGrid: false
    property var previousFocusItem: null
    property bool keyboardNavigationActive: true
    property var hoveredMenuEntry: null
    property bool pointerHoverArmed: false
    property real openPointerX: 0
    property real openPointerY: 0
    property int pendingDeleteNodeId: 0
    property bool pendingDeleteBypass: false
    readonly property var hostWindow: menuContent.hostWindow
    signal requestedTags(int nodeId, var anchorItem)
    signal requestedSearch()

    function openAt(sourceItem, localX, localY) {
        var hostWindow = contextPopup.hostWindow
        previousFocusItem = hostWindow ? hostWindow.activeFocusItem : null
        // A pointer-opened menu starts neutral.  Hover or the first
        // navigation key chooses an entry; merely opening it must not imply
        // that the first action is selected.
        keyboardNavigationActive = false
        hoveredMenuEntry = null
        var point = sourceItem.mapToItem(contextPopup.parent, localX, localY)
        pointerHoverArmed = false
        openPointerX = point.x
        openPointerY = point.y
        contextPopup.x = Math.max(0, Math.min(point.x, contextPopup.parent.width - contextPopup.width))
        contextPopup.y = Math.max(0, Math.min(point.y, contextPopup.parent.height - contextPopup.height))
        contextPopup.open()
    }

    function menuEntries() {
        var entries = []
        collectMenuEntries(menuContent, entries)
        return entries
    }

    function collectMenuEntries(item, entries) {
        if (!item) return
        if (item.menuEntry === true && item.visible && item.enabled)
            entries.push(item)
        var children = item.children || []
        for (var i = 0; i < children.length; i++)
            collectMenuEntries(children[i], entries)
    }

    function updatePointerHover(entry, localX, localY) {
        var point = entry.mapToItem(contextPopup.parent, localX, localY)
        if (!pointerHoverArmed) {
            var deltaX = point.x - openPointerX
            var deltaY = point.y - openPointerY
            // Opening/enter motion can change local coordinates under a
            // stationary cursor.  Compare in overlay coordinates so only a
            // real pointer move arms hover highlighting.
            if (deltaX * deltaX + deltaY * deltaY <= 1) return
            pointerHoverArmed = true
        }
        keyboardNavigationActive = false
        hoveredMenuEntry = entry
    }

    function focusMenuEntry(step, edge) {
        var entries = menuEntries()
        if (entries.length === 0) return
        var continuingKeyboardNavigation = keyboardNavigationActive
        keyboardNavigationActive = true
        hoveredMenuEntry = null
        var hostWindow = contextPopup.hostWindow
        var focused = hostWindow ? hostWindow.activeFocusItem : null
        var index = continuingKeyboardNavigation ? entries.indexOf(focused) : -1
        if (edge === "first") index = 0
        else if (edge === "last") index = entries.length - 1
        else if (index < 0) index = step > 0 ? 0 : entries.length - 1
        else index = (index + step + entries.length) % entries.length
        entries[index].forceActiveFocus()
    }

    function focusMenuPage(direction) {
        var entries = menuEntries()
        if (entries.length === 0) return
        var continuingKeyboardNavigation = keyboardNavigationActive
        keyboardNavigationActive = true
        hoveredMenuEntry = null
        var hostWindow = contextPopup.hostWindow
        var focused = hostWindow ? hostWindow.activeFocusItem : null
        var index = continuingKeyboardNavigation ? entries.indexOf(focused) : -1
        if (index < 0) index = direction > 0 ? 0 : entries.length - 1
        else index = Math.max(
            0,
            Math.min(entries.length - 1, index + direction * 5)
        )
        entries[index].forceActiveFocus()
    }

    function isNavigationKey(key) {
        return key === Qt.Key_Down
                || key === Qt.Key_Up
                || key === Qt.Key_Home
                || key === Qt.Key_End
                || key === Qt.Key_PageDown
                || key === Qt.Key_PageUp
                || key === Qt.Key_Return
                || key === Qt.Key_Enter
                || key === Qt.Key_Space
                || key === Qt.Key_Escape
    }

    function handleNavigationKey(event) {
        if (event.key === Qt.Key_Down) {
            contextPopup.focusMenuEntry(1, "")
        } else if (event.key === Qt.Key_Up) {
            contextPopup.focusMenuEntry(-1, "")
        } else if (event.key === Qt.Key_Home) {
            contextPopup.focusMenuEntry(0, "first")
        } else if (event.key === Qt.Key_End) {
            contextPopup.focusMenuEntry(0, "last")
        } else if (event.key === Qt.Key_PageDown) {
            contextPopup.focusMenuPage(1)
        } else if (event.key === Qt.Key_PageUp) {
            contextPopup.focusMenuPage(-1)
        } else {
            return false
        }
        event.accepted = true
        return true
    }

    onOpened: Qt.callLater(function() {
        if (!contextPopup.visible) return
        contextPopup.keyboardNavigationActive = false
        contextPopup.hoveredMenuEntry = null
        menuContent.forceActiveFocus(Qt.PopupFocusReason)
    })

    onClosed: {
        hoveredMenuEntry = null
        pointerHoverArmed = false
        var focusItem = previousFocusItem
        var deleteNodeId = pendingDeleteNodeId
        var bypassDeleteConfirmation = pendingDeleteBypass
        previousFocusItem = null
        pendingDeleteNodeId = 0
        pendingDeleteBypass = false
        Qt.callLater(function() {
            if (focusItem && focusItem.visible && focusItem.enabled
                    && typeof focusItem.forceActiveFocus === "function") {
                focusItem.forceActiveFocus()
            }
            if (deleteNodeId > 0) {
                contextPopup.canvasController.delete_node_from_context(
                    deleteNodeId,
                    bypassDeleteConfirmation
                )
            }
        })
    }

    Keys.onShortcutOverride: function(event) {
        if (contextPopup.isNavigationKey(event.key)) event.accepted = true
    }

    Keys.onPressed: function(event) {
        contextPopup.handleNavigationKey(event)
    }

    function openForNode(targetNodeId, targetNodeType, sourceItem, localX, localY) {
        contextPopup.targetKind = "node"
        contextPopup.nodeId = targetNodeId
        contextPopup.nodeType = targetNodeType
        contextPopup.frameLocked = targetNodeType === "frame"
                ? contextPopup.canvasController.is_frame_locked(targetNodeId)
                : false
        contextPopup.connId = 0
        contextPopup.openAt(sourceItem, localX, localY)
    }

    function openForConnection(targetConnId, sourceItem, localX, localY) {
        contextPopup.targetKind = "connection"
        contextPopup.nodeId = 0
        contextPopup.nodeType = ""
        contextPopup.frameLocked = false
        contextPopup.connId = targetConnId
        contextPopup.openAt(sourceItem, localX, localY)
    }

    function openForCanvas(
        sourceItem, localX, localY, contentX, contentY
    ) {
        contextPopup.targetKind = "canvas"
        contextPopup.nodeId = 0
        contextPopup.nodeType = ""
        contextPopup.frameLocked = false
        contextPopup.connId = 0
        contextPopup.canvasX = contentX
        contextPopup.canvasY = contentY
        contextPopup.snapToGrid = contextPopup.canvasController.snap_to_grid
        contextPopup.openAt(sourceItem, localX, localY)
    }

    enter: Transition {
        ParallelAnimation {
            NumberAnimation {
                property: "opacity"; from: 0.0; to: 1.0
                duration: contextPopup.appTheme.durationState
                easing.type: Easing.OutCubic
            }
            NumberAnimation {
                property: "scale"; from: 0.98; to: 1.0
                duration: contextPopup.appTheme.motionEnabled
                          ? contextPopup.appTheme.durationState : 0
                easing.type: Easing.OutCubic
            }
            NumberAnimation {
                target: contextPopup; property: "motionOffset"; from: -4; to: 0
                duration: contextPopup.appTheme.motionEnabled
                          ? contextPopup.appTheme.durationState : 0
                easing.type: Easing.OutCubic
            }
        }
    }

    exit: Transition {
        ParallelAnimation {
            NumberAnimation {
                property: "opacity"; from: 1.0; to: 0.0
                duration: contextPopup.appTheme.durationExit
                easing.type: Easing.InCubic
            }
            NumberAnimation {
                property: "scale"; from: 1.0; to: 0.99
                duration: contextPopup.appTheme.motionEnabled
                          ? contextPopup.appTheme.durationExit : 0
                easing.type: Easing.InCubic
            }
            NumberAnimation {
                target: contextPopup; property: "motionOffset"; from: 0; to: -2
                duration: contextPopup.appTheme.motionEnabled
                          ? contextPopup.appTheme.durationExit : 0
                easing.type: Easing.InCubic
            }
        }
    }

    background: Rectangle {
        color: contextPopup.appTheme.bgPopover
        radius: 4
        border.color: contextPopup.appTheme.borderDefault
        border.width: 1
        transform: Translate { y: contextPopup.motionOffset }
    }

    contentItem: Column {
        id: menuContent
        readonly property var hostWindow: Window.window
        focus: true
        spacing: 2
        width: parent ? parent.width : 236
        transform: Translate { y: contextPopup.motionOffset }

        Keys.onShortcutOverride: function(event) {
            if (contextPopup.isNavigationKey(event.key)) event.accepted = true
        }
        Keys.onPressed: function(event) {
            contextPopup.handleNavigationKey(event)
        }

        Loader {
            width: parent.width
            active: contextPopup.targetKind === "canvas"
            visible: active
            height: active && item ? (item as Column).implicitHeight : 0
            sourceComponent: Component {
                Column {
                    spacing: 2

                    SectionLabel { text: "Create" }

                    MenuButton {
                        text: "New Note"
                        rightText: "Ctrl+N"
                        iconSource: "../assets/icons/note.svg"
                        onClicked: {
                            contextPopup.close()
                            contextPopup.canvasController.add_text_node_at(
                                contextPopup.canvasX,
                                contextPopup.canvasY
                            )
                        }
                    }

                    MenuButton {
                        text: "Image…"
                        rightText: "Ctrl+M"
                        iconSource: "../assets/icons/image.svg"
                        onClicked: {
                            contextPopup.close()
                            contextPopup.canvasController.add_media_node_at(
                                "image",
                                contextPopup.canvasX,
                                contextPopup.canvasY
                            )
                        }
                    }

                    MenuButton {
                        text: "Video…"
                        rightText: "Ctrl+Shift+M"
                        iconSource: "../assets/icons/video.svg"
                        onClicked: {
                            contextPopup.close()
                            contextPopup.canvasController.add_media_node_at(
                                "video",
                                contextPopup.canvasX,
                                contextPopup.canvasY
                            )
                        }
                    }

                    MenuButton {
                        text: "Audio…"
                        iconSource: "../assets/icons/play.svg"
                        onClicked: {
                            contextPopup.close()
                            contextPopup.canvasController.add_media_node_at(
                                "audio",
                                contextPopup.canvasX,
                                contextPopup.canvasY
                            )
                        }
                    }

                    MenuButton {
                        text: "Frame"
                        iconSource: "../assets/icons/frame.svg"
                        onClicked: {
                            contextPopup.close()
                            contextPopup.canvasController.add_frame_at(
                                contextPopup.canvasX,
                                contextPopup.canvasY
                            )
                        }
                    }

                    MenuSeparator {}

                    MenuButton {
                        text: "Paste"
                        rightText: "Ctrl+V"
                        iconSource: "../assets/icons/open.svg"
                        onClicked: {
                            contextPopup.close()
                            contextPopup.canvasController.paste_nodes_at(
                                contextPopup.canvasX,
                                contextPopup.canvasY
                            )
                        }
                    }

                    MenuButton {
                        text: "Paste from System"
                        rightText: "Ctrl+Shift+V"
                        iconSource: "../assets/icons/database.svg"
                        onClicked: {
                            contextPopup.close()
                            contextPopup.canvasController
                                .paste_from_system_clipboard_at(
                                    contextPopup.canvasX,
                                    contextPopup.canvasY
                                )
                        }
                    }

                    MenuSeparator {}
                    SectionLabel { text: "Canvas" }

                    MenuButton {
                        text: "Select All"
                        rightText: "Ctrl+A"
                        iconSource: "../assets/icons/select-all.svg"
                        onClicked: {
                            contextPopup.canvasController.select_all_nodes()
                            contextPopup.close()
                        }
                    }

                    MenuButton {
                        text: "Find Node…"
                        rightText: "Ctrl+F"
                        iconSource: "../assets/icons/search.svg"
                        onClicked: {
                            contextPopup.close()
                            contextPopup.requestedSearch()
                        }
                    }

                    MenuButton {
                        text: "Clear Selection"
                        rightText: "Esc"
                        iconSource: "../assets/icons/remove.svg"
                        onClicked: {
                            contextPopup.canvasController.clear_selection()
                            contextPopup.close()
                        }
                    }

                    MenuButton {
                        text: "Snap to Grid"
                        rightText: contextPopup.snapToGrid ? "On · G" : "Off · G"
                        iconSource: "../assets/icons/grid.svg"
                        onClicked: {
                            contextPopup.canvasController.toggle_snap_to_grid()
                            contextPopup.close()
                        }
                    }
                }
            }
        }

        MenuButton {
            visible: contextPopup.targetKind === "connection"
            text: "Remove Link"
            iconSource: "../assets/icons/unlink.svg"
            textColor: contextPopup.appTheme.btnCancelText
            onClicked: {
                contextPopup.canvasController.delete_connection(contextPopup.connId)
                contextPopup.close()
            }
        }

        Loader {
            width: parent.width
            active: contextPopup.targetKind === "node" && contextPopup.nodeType === "text"
            visible: active
            height: active && item ? (item as Column).implicitHeight : 0
            sourceComponent: Component {
                Column {
                    spacing: 2
                    MenuButton {
                        text: "Edit"
                        iconSource: "../assets/icons/edit.svg"
                        onClicked: {
                            contextPopup.canvasController.request_open_editor(contextPopup.nodeId);
                            contextPopup.close();
                        }
                    }
                    // Separator
                    Rectangle {
                        width: parent.width - 8
                        height: 1
                        color: contextPopup.appTheme.borderDefault
                        anchors.horizontalCenter: parent.horizontalCenter
                    }
                    MenuButton {
                        text: "Rename"
                        iconSource: "../assets/icons/rename.svg"
                        onClicked: {
                            contextPopup.canvasController.rename_node(contextPopup.nodeId, "");
                            contextPopup.close();
                        }
                    }
                    // Separator
                    Rectangle {
                        width: parent.width - 8
                        height: 1
                        color: contextPopup.appTheme.borderDefault
                        anchors.horizontalCenter: parent.horizontalCenter
                    }
                    MenuButton {
                        text: "Auto-Fit"
                        iconSource: "../assets/icons/fit.svg"
                        onClicked: {
                            contextPopup.canvasController.auto_fit_node(contextPopup.nodeId);
                            contextPopup.close();
                        }
                    }
                }
            }
        }

        Loader {
            width: parent.width
            active: contextPopup.targetKind === "node"
                    && (contextPopup.nodeType === "image"
                        || contextPopup.nodeType === "video"
                        || contextPopup.nodeType === "audio")
            visible: active
            height: active && item ? (item as Column).implicitHeight : 0
            sourceComponent: Component {
                Column {
                    spacing: 2
                    MenuButton {
                        text: "Open"
                        iconSource: "../assets/icons/open.svg"
                        onClicked: {
                            contextPopup.canvasController.request_open_editor(contextPopup.nodeId);
                            contextPopup.close();
                        }
                    }
                    MenuButton {
                        text: "Rename"
                        iconSource: "../assets/icons/rename.svg"
                        onClicked: {
                            contextPopup.canvasController.rename_node(contextPopup.nodeId, "");
                            contextPopup.close();
                        }
                    }
                    Rectangle {
                        width: parent.width - 8
                        height: 1
                        color: contextPopup.appTheme.borderDefault
                        anchors.horizontalCenter: parent.horizontalCenter
                    }
                    MenuButton {
                        text: "Auto-Fit"
                        iconSource: "../assets/icons/fit.svg"
                        onClicked: {
                            contextPopup.canvasController.auto_fit_node(contextPopup.nodeId);
                            contextPopup.close();
                        }
                    }
                    Rectangle {
                        width: parent.width - 8
                        height: 1
                        color: contextPopup.appTheme.borderDefault
                        anchors.horizontalCenter: parent.horizontalCenter
                    }
                    MenuButton {
                        text: "Export to Disk"
                        iconSource: "../assets/icons/export.svg"
                        onClicked: {
                            contextPopup.canvasController.export_node_to_disk(contextPopup.nodeId);
                            contextPopup.close();
                        }
                    }
                }
            }
        }

        Loader {
            width: parent.width
            active: contextPopup.targetKind === "node"
                    && contextPopup.nodeType === "frame"
            visible: active
            height: active && item ? (item as Column).implicitHeight : 0
            sourceComponent: Component {
                Column {
                    spacing: 2
                    MenuButton {
                        text: contextPopup.frameLocked
                              ? "Unlock Frame"
                              : "Lock Frame"
                        iconSource: contextPopup.frameLocked
                                    ? "../assets/icons/unlock.svg"
                                    : "../assets/icons/lock.svg"
                        onClicked: {
                            contextPopup.frameLocked =
                                contextPopup.canvasController.toggle_frame_locked(
                                    contextPopup.nodeId
                                )
                            contextPopup.close()
                        }
                    }
                    MenuButton {
                        text: "Properties…"
                        iconSource: "../assets/icons/edit.svg"
                        onClicked: {
                            contextPopup.canvasController.request_open_editor(
                                contextPopup.nodeId
                            )
                            contextPopup.close()
                        }
                    }
                    MenuButton {
                        text: "Select Contents"
                        iconSource: "../assets/icons/select-all.svg"
                        onClicked: {
                            contextPopup.canvasController.select_frame_contents(
                                contextPopup.nodeId
                            )
                            contextPopup.close()
                        }
                    }
                }
            }
        }

        Rectangle {
            width: parent.width - 8
            height: 1
            visible: contextPopup.targetKind === "node"
            color: contextPopup.appTheme.borderDefault
            anchors.horizontalCenter: parent.horizontalCenter
        }

        MenuButton {
            text: "Duplicate"
            iconSource: "../assets/icons/add.svg"
            visible: contextPopup.targetKind === "node"
            onClicked: {
                contextPopup.canvasController.duplicate_node(contextPopup.nodeId)
                contextPopup.close()
            }
        }

        MenuButton {
            text: "Copy"
            iconSource: "../assets/icons/export.svg"
            visible: contextPopup.targetKind === "node"
            onClicked: {
                contextPopup.canvasController.copy_nodes(contextPopup.nodeId)
                contextPopup.close()
            }
        }

        MenuButton {
            text: "Paste"
            iconSource: "../assets/icons/open.svg"
            visible: contextPopup.targetKind === "node"
            onClicked: {
                contextPopup.canvasController.paste_nodes()
                contextPopup.close()
            }
        }

        Rectangle {
            width: parent.width - 8
            height: 1
            visible: contextPopup.targetKind === "node"
            color: contextPopup.appTheme.borderDefault
            anchors.horizontalCenter: parent.horizontalCenter
        }

        MenuButton {
            text: "Copy to System Clipboard"
            iconSource: "../assets/icons/export.svg"
            visible: contextPopup.targetKind === "node"
                     && (contextPopup.nodeType === "text"
                         || contextPopup.nodeType === "image")
            onClicked: {
                contextPopup.canvasController.copy_to_system_clipboard(
                    contextPopup.nodeId
                )
                contextPopup.close()
            }
        }

        MenuButton {
            text: "Paste from System Clipboard"
            iconSource: "../assets/icons/open.svg"
            visible: contextPopup.targetKind === "node"
            onClicked: {
                contextPopup.canvasController.paste_from_system_clipboard()
                contextPopup.close()
            }
        }

        Rectangle {
            width: parent.width - 8
            height: 1
            visible: contextPopup.targetKind === "node"
            color: contextPopup.appTheme.borderDefault
            anchors.horizontalCenter: parent.horizontalCenter
        }

        MenuButton {
            id: tagsMenuButton
            text: "Tags…"
            iconSource: "../assets/icons/tag.svg"
            visible: contextPopup.targetKind === "node"
                     && contextPopup.nodeType !== "frame"
            onClicked: {
                contextPopup.requestedTags(contextPopup.nodeId, tagsMenuButton)
                contextPopup.close()
            }
        }

        Rectangle {
            width: parent.width - 8
            height: 1
            visible: contextPopup.targetKind === "node"
                     && contextPopup.nodeType !== "frame"
            color: contextPopup.appTheme.borderDefault
            anchors.horizontalCenter: parent.horizontalCenter
        }

        MenuButton {
            text: "Properties"
            iconSource: "../assets/icons/info.svg"
            visible: contextPopup.targetKind === "node"
            onClicked: {
                contextPopup.canvasController.show_node_properties(contextPopup.nodeId);
                contextPopup.close();
            }
        }

        Rectangle {
            width: parent.width - 8
            height: 1
            visible: contextPopup.targetKind === "node"
            color: contextPopup.appTheme.borderDefault
            anchors.horizontalCenter: parent.horizontalCenter
        }

        MenuButton {
            id: deleteMenuButton
            text: contextPopup.shiftHeld ? "Delete Immediately" : "Delete"
            iconSource: "../assets/icons/delete.svg"
            textColor: contextPopup.appTheme.btnCancelText
            visible: contextPopup.targetKind === "node"
            onClicked: {
                contextPopup.pendingDeleteNodeId = contextPopup.nodeId
                contextPopup.pendingDeleteBypass = Boolean(
                    deleteMenuButton.activationModifiers & Qt.ShiftModifier
                )
                contextPopup.close()
            }
        }
    }

    component SectionLabel: Text {
        width: parent ? parent.width : 228
        height: 22
        leftPadding: 10
        verticalAlignment: Text.AlignVCenter
        color: contextPopup.appTheme.textMuted
        font.family: "Segoe UI"
        font.pointSize: 8
        font.weight: Font.DemiBold
        Accessible.ignored: true
    }

    component MenuSeparator: Item {
        width: parent ? parent.width : 228
        height: 7

        Rectangle {
            width: parent.width - 8
            height: 1
            anchors.centerIn: parent
            color: contextPopup.appTheme.borderDefault
        }
    }

    component MenuButton: Rectangle {
        id: menuButton
        width: parent ? parent.width : 228
        height: 28
        activeFocusOnTab: true
        property bool menuEntry: true
        color: menuMouseArea.pressed ? contextPopup.appTheme.bgControlPressed
             : contextPopup.keyboardNavigationActive
               ? (activeFocus ? contextPopup.appTheme.accentLow : "transparent")
             : contextPopup.hoveredMenuEntry === menuButton
               ? contextPopup.appTheme.bgControlHover : "transparent"
        radius: 3
        border.width: activeFocus && contextPopup.keyboardNavigationActive ? 1 : 0
        border.color: contextPopup.appTheme.accentMain

        property alias text: label.text
        property alias rightText: shortcutLabel.text
        property color textColor: contextPopup.appTheme.textMain
        property url iconSource: ""
        property int activationModifiers: Qt.NoModifier
        signal clicked()

        function activate(modifiers) {
            menuButton.activationModifiers = modifiers
            menuButton.clicked()
        }

        ToolButton {
            id: menuIcon
            visible: menuButton.iconSource.toString().length > 0
            anchors.left: parent.left
            anchors.leftMargin: 5
            anchors.verticalCenter: parent.verticalCenter
            width: 24
            height: 24
            hoverEnabled: false
            focusPolicy: Qt.NoFocus
            display: AbstractButton.IconOnly
            icon.source: menuButton.iconSource
            icon.width: 15
            icon.height: 15
            icon.color: menuButton.textColor
            background: Item {}
            Accessible.ignored: true
        }

        Text {
            id: label
            anchors.left: menuIcon.visible ? menuIcon.right : parent.left
            anchors.leftMargin: menuIcon.visible ? 2 : 10
            anchors.right: shortcutLabel.visible
                           ? shortcutLabel.left
                           : parent.right
            anchors.rightMargin: shortcutLabel.visible ? 10 : 8
            anchors.verticalCenter: parent.verticalCenter
            color: menuButton.textColor
            font.family: "Segoe UI"
            font.pointSize: 9
            elide: Text.ElideRight
        }

        Text {
            id: shortcutLabel
            visible: text.length > 0
            anchors.right: parent.right
            anchors.rightMargin: 9
            anchors.verticalCenter: parent.verticalCenter
            color: contextPopup.appTheme.textMuted
            font.family: "Segoe UI"
            font.pointSize: 8
            horizontalAlignment: Text.AlignRight
        }

        Keys.onShortcutOverride: function(event) {
            if (contextPopup.isNavigationKey(event.key)) event.accepted = true
        }

        Keys.onPressed: function(event) {
            if (contextPopup.handleNavigationKey(event)) return
            if (event.key === Qt.Key_Return || event.key === Qt.Key_Enter
                    || event.key === Qt.Key_Space) {
                menuButton.activate(event.modifiers)
                event.accepted = true
            }
        }
        Accessible.role: Accessible.Button
        Accessible.name: text
        Accessible.onPressAction: menuButton.activate(Qt.NoModifier)

        MouseArea {
            id: menuMouseArea
            anchors.fill: parent
            hoverEnabled: true
            cursorShape: Qt.PointingHandCursor
            onEntered: {
                if (contextPopup.pointerHoverArmed) {
                    contextPopup.keyboardNavigationActive = false
                    contextPopup.hoveredMenuEntry = menuButton
                }
            }
            onPositionChanged: function(mouse) {
                contextPopup.updatePointerHover(menuButton, mouse.x, mouse.y)
            }
            onExited: {
                if (contextPopup.hoveredMenuEntry === menuButton)
                    contextPopup.hoveredMenuEntry = null
            }
            onClicked: function(mouse) {
                menuButton.activate(mouse.modifiers)
            }
        }
    }
}
