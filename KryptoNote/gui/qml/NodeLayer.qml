pragma ComponentBehavior: Bound
import QtQuick

Item {
    id: nodeLayer
    required property var viewportModel
    required property var canvasRoot
    required property var nodeModel
    required property var canvasController
    required property Item contentLayer
    required property var appTheme
    signal contextMenuRequested(int nodeId, string nodeType, var sourceItem, real localX, real localY)
    Repeater {
        model: nodeLayer.viewportModel
        delegate: NodeDelegate {
            canvasRoot: nodeLayer.canvasRoot
            nodeModel: nodeLayer.nodeModel
            canvasController: nodeLayer.canvasController
            contentLayer: nodeLayer.contentLayer
            appTheme: nodeLayer.appTheme
            onContextMenuRequested: function(nodeId, nodeType, sourceItem, localX, localY) {
                nodeLayer.contextMenuRequested(nodeId, nodeType, sourceItem, localX, localY)
            }
        }
    }
}
