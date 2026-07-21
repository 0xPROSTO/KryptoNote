pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls


Popup {
    id: contextPopup
    required property var canvasController
    required property var appTheme
    width: 160
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
    signal requestedTags(int nodeId, var anchorItem)

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
        contextPopup.connId = 0
        contextPopup.openAt(sourceItem, localX, localY)
    }

    function openForConnection(targetConnId, sourceItem, localX, localY) {
        contextPopup.targetKind = "connection"
        contextPopup.nodeId = 0
        contextPopup.nodeType = ""
        contextPopup.connId = targetConnId
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
        width: parent ? parent.width : 160

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
            active: contextPopup.targetKind === "node" && (contextPopup.nodeType === "image" || contextPopup.nodeType === "video")
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
            onClicked: {
                contextPopup.requestedTags(contextPopup.nodeId, tagsMenuButton)
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

    component MenuButton: Rectangle {
        id: menuButton
        width: parent ? parent.width : 152
        height: 28
        activeFocusOnTab: true
        color: menuMouseArea.containsMouse ? contextPopup.appTheme.bgControlHover
             : activeFocus ? contextPopup.appTheme.bgControl : "transparent"
        radius: 3
        border.width: activeFocus ? 1 : 0
        border.color: contextPopup.appTheme.accentMain

        property alias text: label.text
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
            anchors.right: parent.right
            anchors.rightMargin: 8
            anchors.verticalCenter: parent.verticalCenter
            color: menuButton.textColor
            font.family: "Segoe UI"
            font.pointSize: 9
            elide: Text.ElideRight
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
            onPressed: menuButton.forceActiveFocus()
            onClicked: menuButton.clicked()
        }
    }
}
