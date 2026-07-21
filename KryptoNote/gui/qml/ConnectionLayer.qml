pragma ComponentBehavior: Bound
import QtQuick

Item {
    id: connectionLayer
    required property var viewportModel
    required property var canvasRoot
    required property var canvasController
    required property var appTheme
    signal contextMenuRequested(int connId, var sourceItem, real localX, real localY)

    Repeater {
        model: connectionLayer.viewportModel
        delegate: Connection {
            canvasRoot: connectionLayer.canvasRoot
            canvasController: connectionLayer.canvasController
            appTheme: connectionLayer.appTheme
            onContextMenuRequested: function(connId, sourceItem, localX, localY) {
                connectionLayer.contextMenuRequested(connId, sourceItem, localX, localY)
            }
        }
    }
}
