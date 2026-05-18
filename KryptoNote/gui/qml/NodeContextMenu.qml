import QtQuick
import QtQuick.Controls


Popup {
    id: contextPopup
    width: 160
    padding: 4
    modal: true
    closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside
    opacity: 0.0

    property int nodeId: 0
    property string nodeType: "text"

    enter: Transition {
        NumberAnimation { property: "opacity"; from: 0.0; to: 1.0; duration: 140; easing.type: Easing.OutQuad }
    }

    exit: Transition {
        NumberAnimation { property: "opacity"; from: 1.0; to: 0.0; duration: 120; easing.type: Easing.OutQuad }
    }

    Overlay.modal: Rectangle {
        color: "#1a000000"
        opacity: contextPopup.opened ? 1.0 : 0.0
        Behavior on opacity { NumberAnimation { duration: 140; easing.type: Easing.OutQuad } }
    }

    background: Rectangle {
        color: "#333333"
        radius: 4
        border.color: "#444444"
        border.width: 1
    }

    contentItem: Column {
        spacing: 2
        width: parent ? parent.width : 160

        Loader {
            width: parent.width
            active: contextPopup.nodeType === "text"
            visible: active
            height: active && item ? item.implicitHeight : 0
            sourceComponent: Component {
                Column {
                    spacing: 2
                    MenuButton {
                        text: "Edit"
                        onClicked: {
                            canvasController.request_open_editor(contextPopup.nodeId);
                            contextPopup.close();
                        }
                    }
                    // Separator
                    Rectangle {
                        width: parent.width - 8
                        height: 1
                        color: "#555555"
                        anchors.horizontalCenter: parent.horizontalCenter
                    }
                    MenuButton {
                        text: "Rename"
                        onClicked: {
                            canvasController.rename_node(contextPopup.nodeId, "");
                            contextPopup.close();
                        }
                    }
                    // Separator
                    Rectangle {
                        width: parent.width - 8
                        height: 1
                        color: "#555555"
                        anchors.horizontalCenter: parent.horizontalCenter
                    }
                    MenuButton {
                        text: "Auto-Fit"
                        onClicked: {
                            canvasController.auto_fit_node(contextPopup.nodeId);
                            contextPopup.close();
                        }
                    }
                }
            }
        }

        Loader {
            width: parent.width
            active: contextPopup.nodeType === "image" || contextPopup.nodeType === "video"
            visible: active
            height: active && item ? item.implicitHeight : 0
            sourceComponent: Component {
                Column {
                    spacing: 2
                    MenuButton {
                        text: "Open"
                        onClicked: {
                            canvasController.request_open_editor(contextPopup.nodeId);
                            contextPopup.close();
                        }
                    }
                    MenuButton {
                        text: "Rename"
                        onClicked: {
                            canvasController.rename_node(contextPopup.nodeId, "");
                            contextPopup.close();
                        }
                    }
                    Rectangle {
                        width: parent.width - 8
                        height: 1
                        color: "#555555"
                        anchors.horizontalCenter: parent.horizontalCenter
                    }
                    MenuButton {
                        text: "Auto-Fit"
                        onClicked: {
                            canvasController.auto_fit_node(contextPopup.nodeId);
                            contextPopup.close();
                        }
                    }
                    Rectangle {
                        width: parent.width - 8
                        height: 1
                        color: "#555555"
                        anchors.horizontalCenter: parent.horizontalCenter
                    }
                    MenuButton {
                        text: "Export to Disk"
                        onClicked: {
                            canvasController.export_node_to_disk(contextPopup.nodeId);
                            contextPopup.close();
                        }
                    }
                }
            }
        }

        Rectangle {
            width: parent.width - 8
            height: 1
            color: "#555555"
            anchors.horizontalCenter: parent.horizontalCenter
        }

        MenuButton {
            text: "Properties"
            onClicked: {
                canvasController.show_node_properties(contextPopup.nodeId);
                contextPopup.close();
            }
        }

        Rectangle {
            width: parent.width - 8
            height: 1
            color: "#555555"
            anchors.horizontalCenter: parent.horizontalCenter
        }

        MenuButton {
            text: "Delete"
            textColor: "#ff6666"
            onClicked: {
                canvasController.request_animated_delete(contextPopup.nodeId);
                contextPopup.close();
            }
        }
    }

    component MenuButton: Rectangle {
        width: parent ? parent.width : 152
        height: 28
        color: menuMouseArea.containsMouse ? "#444444" : "transparent"
        radius: 3

        property alias text: label.text
        property color textColor: "#ffffff"
        signal clicked()

        Text {
            id: label
            anchors.verticalCenter: parent.verticalCenter
            x: 10
            color: parent.textColor
            font.family: "Segoe UI"
            font.pointSize: 9
        }

        MouseArea {
            id: menuMouseArea
            anchors.fill: parent
            hoverEnabled: true
            onClicked: parent.clicked()
        }
    }
}
