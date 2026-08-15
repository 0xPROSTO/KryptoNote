pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls


Popup {
    id: contextPopup
    required property var canvasController
    required property var appTheme
    width: 236
    parent: Overlay.overlay
    padding: 4
    modal: true
    dim: false
    focus: true
    closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside
    opacity: 0.0

    property int nodeId: 0
    property string targetKind: "node"
    property int connId: 0
    property string nodeType: "text"
    property bool frameLocked: false
    property real canvasX: 0
    property real canvasY: 0
    property bool snapToGrid: false
    signal requestedTags(int nodeId, var anchorItem)
    signal requestedSearch()

    function openAt(sourceItem, localX, localY) {
        var point = sourceItem.mapToItem(contextPopup.parent, localX, localY)
        contextPopup.x = Math.max(0, Math.min(point.x, contextPopup.parent.width - contextPopup.width))
        contextPopup.y = Math.max(0, Math.min(point.y, contextPopup.parent.height - contextPopup.height))
        contextPopup.open()
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
        NumberAnimation { property: "opacity"; from: 0.0; to: 1.0; duration: 140; easing.type: Easing.OutQuad }
    }

    exit: Transition {
        NumberAnimation { property: "opacity"; from: 1.0; to: 0.0; duration: 120; easing.type: Easing.OutQuad }
    }

    background: Rectangle {
        color: contextPopup.appTheme.bgPopover
        radius: 4
        border.color: contextPopup.appTheme.borderDefault
        border.width: 1
    }

    contentItem: Column {
        spacing: 2
        width: parent ? parent.width : 236

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
            text: "Delete"
            iconSource: "../assets/icons/delete.svg"
            textColor: contextPopup.appTheme.btnCancelText
            visible: contextPopup.targetKind === "node"
            onClicked: {
                contextPopup.canvasController.request_animated_delete(contextPopup.nodeId);
                contextPopup.close();
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
        color: menuMouseArea.containsMouse ? contextPopup.appTheme.bgControlHover
             : activeFocus ? contextPopup.appTheme.bgControl : "transparent"
        radius: 3
        border.width: activeFocus ? 1 : 0
        border.color: contextPopup.appTheme.accentMain

        property alias text: label.text
        property alias rightText: shortcutLabel.text
        property color textColor: contextPopup.appTheme.textMain
        property url iconSource: ""
        signal clicked()

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

        Keys.onPressed: function(event) {
            if (event.key === Qt.Key_Return || event.key === Qt.Key_Enter
                    || event.key === Qt.Key_Space) {
                menuButton.clicked()
                event.accepted = true
            }
        }
        Accessible.role: Accessible.Button
        Accessible.name: text
        Accessible.onPressAction: menuButton.clicked()

        MouseArea {
            id: menuMouseArea
            anchors.fill: parent
            hoverEnabled: true
            cursorShape: Qt.PointingHandCursor
            onClicked: menuButton.clicked()
        }
    }
}
