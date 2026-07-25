import QtQuick


Item {
    id: frameSelection
    required property var canvasRoot
    required property var nodeModel
    required property var canvasController
    property int nodeId: 0
    signal contextMenuRequested(
        int nodeId,
        string nodeType,
        var sourceItem,
        real localX,
        real localY
    )

    readonly property real edgeThickness: 8

    NodeSelectionMouseArea {
        x: 0
        y: 0
        width: parent.width
        height: frameSelection.edgeThickness
        canvasRoot: frameSelection.canvasRoot
        nodeModel: frameSelection.nodeModel
        canvasController: frameSelection.canvasController
        nodeId: frameSelection.nodeId
        nodeType: "frame"
        onContextMenuRequested: function(
            nodeId, nodeType, sourceItem, localX, localY
        ) {
            frameSelection.contextMenuRequested(
                nodeId, nodeType, sourceItem, localX, localY
            )
        }
    }

    NodeSelectionMouseArea {
        x: 0
        y: Math.max(0, parent.height - height)
        width: Math.max(0, parent.width - 24)
        height: frameSelection.edgeThickness
        canvasRoot: frameSelection.canvasRoot
        nodeModel: frameSelection.nodeModel
        canvasController: frameSelection.canvasController
        nodeId: frameSelection.nodeId
        nodeType: "frame"
        onContextMenuRequested: function(
            nodeId, nodeType, sourceItem, localX, localY
        ) {
            frameSelection.contextMenuRequested(
                nodeId, nodeType, sourceItem, localX, localY
            )
        }
    }

    NodeSelectionMouseArea {
        x: 0
        y: frameSelection.edgeThickness
        width: frameSelection.edgeThickness
        height: Math.max(0, parent.height - 2 * frameSelection.edgeThickness)
        canvasRoot: frameSelection.canvasRoot
        nodeModel: frameSelection.nodeModel
        canvasController: frameSelection.canvasController
        nodeId: frameSelection.nodeId
        nodeType: "frame"
        onContextMenuRequested: function(
            nodeId, nodeType, sourceItem, localX, localY
        ) {
            frameSelection.contextMenuRequested(
                nodeId, nodeType, sourceItem, localX, localY
            )
        }
    }

    NodeSelectionMouseArea {
        x: Math.max(0, parent.width - width)
        y: frameSelection.edgeThickness
        width: frameSelection.edgeThickness
        height: Math.max(
            0,
            parent.height - frameSelection.edgeThickness - 24
        )
        canvasRoot: frameSelection.canvasRoot
        nodeModel: frameSelection.nodeModel
        canvasController: frameSelection.canvasController
        nodeId: frameSelection.nodeId
        nodeType: "frame"
        onContextMenuRequested: function(
            nodeId, nodeType, sourceItem, localX, localY
        ) {
            frameSelection.contextMenuRequested(
                nodeId, nodeType, sourceItem, localX, localY
            )
        }
    }
}
