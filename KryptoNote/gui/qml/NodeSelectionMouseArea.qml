import QtQuick

MouseArea {
    id: selector
    property int nodeId: 0
    property string nodeType: ""
    property var contextMenu
    property point _pressPos: Qt.point(0, 0)

    acceptedButtons: Qt.LeftButton | Qt.RightButton
    hoverEnabled: true

    onEntered: nodeModel.set_hovered(nodeId, true)
    onExited: nodeModel.set_hovered(nodeId, false)

    onPressed: function(mouse) {
        _pressPos = Qt.point(mouse.x, mouse.y)
        if (mouse.button === Qt.LeftButton && root.isLinkMode) {
            canvasController.handle_link_click(nodeId)
            mouse.accepted = true
        }
    }

    onClicked: function(mouse) {
        if (mouse.button === Qt.LeftButton && root.isLinkMode) {
            return
        }

        var dx = mouse.x - _pressPos.x
        var dy = mouse.y - _pressPos.y
        if (Math.sqrt(dx*dx + dy*dy) > 2) {
            return
        }

        if (mouse.button === Qt.RightButton) {
            contextMenu.nodeId = nodeId
            contextMenu.nodeType = nodeType
            contextMenu.x = mouse.x
            contextMenu.y = mouse.y
            contextMenu.open()
        } else if (mouse.button === Qt.LeftButton) {
            if (root.isCtrlHeld) {
                nodeModel.toggle_selected(nodeId)
            } else {
                nodeModel.clear_selection()
                nodeModel.clear_hovered()
                nodeModel.set_selected(nodeId, true)
            }
        }
    }

    onDoubleClicked: function(mouse) {
        if (mouse.button === Qt.LeftButton) {
            canvasController.request_open_editor(nodeId)
        }
    }
}
