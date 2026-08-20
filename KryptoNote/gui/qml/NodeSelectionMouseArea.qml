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

    // QQuickItem containment masks require a C++/Python QObject with an
    // invokable contains() method.  A QML QtObject function is ignored by Qt,
    // so keep the same hit rule local to the event handlers instead.
    function containsLocalPoint(x, y) {
        if (x < 0 || y < 0 || x > selector.width || y > selector.height) {
            return false
        }
        var exclusion = selector.bottomRightExclusion
        return exclusion <= 0
                || x < selector.width - exclusion
                || y < selector.height - exclusion
    }

    HoverHandler {
        id: selectionHover
        onHoveredChanged: selector.nodeModel.set_hovered(
            selector.nodeId,
            hovered
        )
    }

    onPressed: function(mouse) {
        if (!containsLocalPoint(mouse.x, mouse.y)) {
            mouse.accepted = false
            return
        }
        _pressPos = Qt.point(mouse.x, mouse.y)
        if (mouse.button === Qt.LeftButton && selector.canvasRoot.isLinkMode) {
            selector.canvasController.handle_link_click(nodeId)
            mouse.accepted = true
        }
    }

    onClicked: function(mouse) {
        if (!containsLocalPoint(mouse.x, mouse.y)) {
            mouse.accepted = false
            return
        }
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
                selector.nodeModel.set_selection([nodeId])
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
