import QtQuick

Item {
    id: dragController
    required property var canvasRoot
    required property var nodeModel
    required property Item contentLayer
    property Item delegateItem
    property int nodeId: 0
    property bool nodeIsSelected: false
    property bool resizeHovered: false
    property bool resizing: false

    DragHandler {
        id: dragHandler
        target: null
        acceptedButtons: Qt.LeftButton
        dragThreshold: 1
        grabPermissions: PointerHandler.CanTakeOverFromAnything
        enabled: !dragController.canvasRoot.isLinkMode && !dragController.canvasRoot.isPanning && !dragController.canvasRoot.isEditorResizing
                 && !dragController.resizeHovered && !dragController.resizing

        property real lastDx: 0
        property real lastDy: 0
        property var dragNodes: []

        onActiveChanged: {
            if (active) {
                dragController.nodeModel.clear_hovered()
                lastDx = 0
                lastDy = 0
                if (!dragController.canvasRoot.isCtrlHeld) {
                    if (!dragController.nodeIsSelected) {
                        dragController.nodeModel.clear_selection()
                        dragController.nodeModel.set_selected(dragController.nodeId, true)
                    }
                } else if (!dragController.nodeIsSelected) {
                    dragController.nodeModel.set_selected(dragController.nodeId, true)
                }
                dragNodes = dragController.nodeModel.get_selected_node_positions()
                if (!dragNodes || dragNodes.length === 0) {
                    dragNodes = [{ "id": dragController.nodeId, "x": dragController.delegateItem.x, "y": dragController.delegateItem.y }]
                }
            } else {
                for (var i = 0; i < dragNodes.length; i++) {
                    var node = dragNodes[i]
                    var finalX = node.x + lastDx
                    var finalY = node.y + lastDy
                    if (dragController.canvasRoot.snapToGrid) {
                        finalX = Math.round(finalX / dragController.canvasRoot.gridSize) * dragController.canvasRoot.gridSize
                        finalY = Math.round(finalY / dragController.canvasRoot.gridSize) * dragController.canvasRoot.gridSize
                    }
                    // Commit only on release; live drag uses preview_position.
                    dragController.nodeModel.update_position(node.id, finalX, finalY)
                }
                dragNodes = []
            }
        }

        onTranslationChanged: {
            var scale = Math.max(dragController.canvasRoot.contentScale, 0.01)
            lastDx = (centroid.scenePosition.x - centroid.scenePressPosition.x) / scale
            lastDy = (centroid.scenePosition.y - centroid.scenePressPosition.y) / scale

            for (var i = 0; i < dragNodes.length; i++) {
                var node = dragNodes[i]
                var newX = node.x + lastDx
                var newY = node.y + lastDy

                if (dragController.canvasRoot.snapToGrid) {
                    newX = Math.round(newX / dragController.canvasRoot.gridSize) * dragController.canvasRoot.gridSize
                    newY = Math.round(newY / dragController.canvasRoot.gridSize) * dragController.canvasRoot.gridSize
                }


                dragController.nodeModel.preview_position(node.id, newX, newY)
            }
        }
    }
}
