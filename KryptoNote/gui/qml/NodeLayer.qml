pragma ComponentBehavior: Bound
import QtQuick

Item {
    id: nodeLayer
    required property var viewportModel
    required property var canvasRoot
    required property var nodeModel
    required property var canvasController
    required property var viewerController
    required property Item contentLayer
    required property var appTheme
    required property bool framesOnly
    signal contextMenuRequested(int nodeId, string nodeType, var sourceItem, real localX, real localY)

    Repeater {
        model: nodeLayer.viewportModel
        delegate: Loader {
            id: delegateLoader
            required property var model
            active: nodeLayer.framesOnly
                    ? delegateLoader.model.nodeType === "frame"
                    : delegateLoader.model.nodeType !== "frame"

            sourceComponent: Component {
                NodeDelegate {
                    model: delegateLoader.model
                    canvasRoot: nodeLayer.canvasRoot
                    nodeModel: nodeLayer.nodeModel
                    canvasController: nodeLayer.canvasController
                    viewerController: nodeLayer.viewerController
                    contentLayer: nodeLayer.contentLayer
                    appTheme: nodeLayer.appTheme
                    renderFrames: nodeLayer.framesOnly
                    onContextMenuRequested: function(
                        nodeId, nodeType, sourceItem, localX, localY
                    ) {
                        nodeLayer.contextMenuRequested(
                            nodeId, nodeType, sourceItem, localX, localY
                        )
                    }
                }
            }
        }
    }
}
