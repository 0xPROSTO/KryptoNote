import QtQuick

Item {
    id: dragController
    property Item delegateItem
    property int nodeId: 0
    property bool nodeIsSelected: false
    property bool resizeHovered: false
    property bool resizing: false

    DragHandler {
        id: dragHandler
        target: null
        dragThreshold: 1
        enabled: !root.isLinkMode && !root.isPanning && !root.isEditorResizing
                 && !dragController.resizeHovered && !dragController.resizing

        property real lastDx: 0
        property real lastDy: 0
        property point startContentPos: Qt.point(0, 0)
        property var dragNodes: []

        onActiveChanged: {
            if (active) {
                nodeModel.clear_hovered()
                lastDx = 0
                lastDy = 0
                startContentPos = dragController.mapToItem(
                    contentLayer,
                    centroid.position.x,
                    centroid.position.y
                )
                if (!root.isCtrlHeld) {
                    if (!dragController.nodeIsSelected) {
                        nodeModel.clear_selection()
                        nodeModel.set_selected(dragController.nodeId, true)
                    }
                } else if (!dragController.nodeIsSelected) {
                    nodeModel.set_selected(dragController.nodeId, true)
                }
                dragNodes = nodeModel.get_selected_node_positions()
                if (!dragNodes || dragNodes.length === 0) {
                    dragNodes = [{ "id": dragController.nodeId, "x": delegateItem.x, "y": delegateItem.y }]
                }
            } else {
                for (var i = 0; i < dragNodes.length; i++) {
                    var node = dragNodes[i]
                    var finalX = node.x + lastDx
                    var finalY = node.y + lastDy
                    if (root.snapToGrid) {
                        finalX = Math.round(finalX / root.gridSize) * root.gridSize
                        finalY = Math.round(finalY / root.gridSize) * root.gridSize
                    }
                    // Commit only on release; live drag uses preview_position.
                    nodeModel.update_position(node.id, finalX, finalY)
                }
                dragNodes = []
            }
        }

        onTranslationChanged: {
            var currentContentPos = dragController.mapToItem(
                contentLayer,
                centroid.position.x,
                centroid.position.y
            )
            lastDx = currentContentPos.x - startContentPos.x
            lastDy = currentContentPos.y - startContentPos.y

            for (var i = 0; i < dragNodes.length; i++) {
                var node = dragNodes[i]
                var newX = node.x + lastDx
                var newY = node.y + lastDy

                if (root.snapToGrid) {
                    newX = Math.round(newX / root.gridSize) * root.gridSize
                    newY = Math.round(newY / root.gridSize) * root.gridSize
                }


                nodeModel.preview_position(node.id, newX, newY)
            }
        }
    }
}
