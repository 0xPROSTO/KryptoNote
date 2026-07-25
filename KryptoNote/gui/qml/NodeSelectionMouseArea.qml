import QtQuick

MouseArea {
    id: selector
    required property var canvasRoot
    required property var nodeModel
    required property var canvasController
    property int nodeId: 0
    property string nodeType: ""
    property real bottomRightExclusion: 0
    signal contextMenuRequested(int nodeId, string nodeType, var sourceItem, real localX, real localY)
    property point _pressPos: Qt.point(0, 0)

    acceptedButtons: Qt.LeftButton | Qt.RightButton
    hoverEnabled: true
    preventStealing: false
    containmentMask: QtObject {
        function contains(point) {
            if (point.x < 0 || point.y < 0
                    || point.x > selector.width
                    || point.y > selector.height) {
                return false
            }
            var exclusion = selector.bottomRightExclusion
            return exclusion <= 0
                    || point.x < selector.width - exclusion
                    || point.y < selector.height - exclusion
        }
    }

    onEntered: selector.nodeModel.set_hovered(nodeId, true)
    onExited: selector.nodeModel.set_hovered(nodeId, false)

    onPressed: function(mouse) {
        _pressPos = Qt.point(mouse.x, mouse.y)
        if (mouse.button === Qt.LeftButton && selector.canvasRoot.isLinkMode) {
            selector.canvasController.handle_link_click(nodeId)
            mouse.accepted = true
        }
    }

    onClicked: function(mouse) {
        if (mouse.button === Qt.LeftButton && selector.canvasRoot.isLinkMode) {
            return
        }

        var dx = mouse.x - _pressPos.x
        var dy = mouse.y - _pressPos.y
        if (Math.sqrt(dx*dx + dy*dy) > 2) {
            return
        }

        if (mouse.button === Qt.RightButton) {
            contextMenuRequested(nodeId, nodeType, selector, mouse.x, mouse.y)
        } else if (mouse.button === Qt.LeftButton) {
            if (selector.canvasRoot.isCtrlHeld) {
                selector.nodeModel.toggle_selected(nodeId)
            } else {
                selector.nodeModel.clear_selection()
                selector.nodeModel.clear_hovered()
                selector.nodeModel.set_selected(nodeId, true)
            }
        }
    }

    onDoubleClicked: function(mouse) {
        if (mouse.button === Qt.LeftButton) {
            selector.canvasController.request_open_editor(nodeId)
            mouse.accepted = true
        }
    }
}
