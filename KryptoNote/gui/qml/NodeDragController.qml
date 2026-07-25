import QtQuick


Item {
    id: dragController
    required property var canvasRoot
    required property var nodeModel
    required property Item contentLayer
    property Item delegateItem
    property int nodeId: 0
    property string nodeType: ""
    property bool nodeIsSelected: false
    property bool resizeHovered: false
    property bool resizing: false
    property real lastDx: 0
    property real lastDy: 0
    property var dragNodes: []

    readonly property real edgeThickness: 8
    readonly property bool canDrag:
        !dragController.canvasRoot.isLinkMode
        && !dragController.canvasRoot.isPanning
        && !dragController.canvasRoot.isEditorResizing
        && !dragController.resizeHovered
        && !dragController.resizing

    function beginDrag() {
        dragController.nodeModel.clear_hovered()
        dragController.lastDx = 0
        dragController.lastDy = 0
        if (!dragController.canvasRoot.isCtrlHeld) {
            if (!dragController.nodeIsSelected) {
                dragController.nodeModel.clear_selection()
                dragController.nodeModel.set_selected(
                    dragController.nodeId, true
                )
            }
        } else if (!dragController.nodeIsSelected) {
            dragController.nodeModel.set_selected(dragController.nodeId, true)
        }
        dragController.dragNodes =
            dragController.nodeModel.get_drag_node_positions(
                dragController.nodeId
            )
        if (!dragController.dragNodes
                || dragController.dragNodes.length === 0) {
            dragController.dragNodes = [{
                "id": dragController.nodeId,
                "x": dragController.delegateItem.x,
                "y": dragController.delegateItem.y
            }]
        }
    }

    function appliedDragDelta() {
        var appliedX = dragController.lastDx
        var appliedY = dragController.lastDy
        if (!dragController.canvasRoot.snapToGrid
                || dragController.nodeType !== "frame") {
            return Qt.point(appliedX, appliedY)
        }
        for (var i = 0; i < dragController.dragNodes.length; i++) {
            var draggedFrame = dragController.dragNodes[i]
            if (draggedFrame.id === dragController.nodeId) {
                appliedX = Math.round(
                    (draggedFrame.x + appliedX)
                    / dragController.canvasRoot.gridSize
                ) * dragController.canvasRoot.gridSize - draggedFrame.x
                appliedY = Math.round(
                    (draggedFrame.y + appliedY)
                    / dragController.canvasRoot.gridSize
                ) * dragController.canvasRoot.gridSize - draggedFrame.y
                break
            }
        }
        return Qt.point(appliedX, appliedY)
    }

    function updateDrag(handler) {
        var scale = Math.max(dragController.canvasRoot.contentScale, 0.01)
        dragController.lastDx = (
            handler.centroid.scenePosition.x
            - handler.centroid.scenePressPosition.x
        ) / scale
        dragController.lastDy = (
            handler.centroid.scenePosition.y
            - handler.centroid.scenePressPosition.y
        ) / scale

        var applied = dragController.appliedDragDelta()
        var snapAsGroup = dragController.canvasRoot.snapToGrid
                          && dragController.nodeType === "frame"

        for (var i = 0; i < dragController.dragNodes.length; i++) {
            var node = dragController.dragNodes[i]
            var newX = node.x + applied.x
            var newY = node.y + applied.y
            if (dragController.canvasRoot.snapToGrid && !snapAsGroup) {
                newX = Math.round(
                    newX / dragController.canvasRoot.gridSize
                ) * dragController.canvasRoot.gridSize
                newY = Math.round(
                    newY / dragController.canvasRoot.gridSize
                ) * dragController.canvasRoot.gridSize
            }
            dragController.nodeModel.preview_position(node.id, newX, newY)
        }
    }

    function finishDrag() {
        if (!dragController.dragNodes
                || dragController.dragNodes.length === 0) {
            return
        }
        var applied = dragController.appliedDragDelta()
        var snapAsGroup = dragController.canvasRoot.snapToGrid
                          && dragController.nodeType === "frame"
        for (var i = 0; i < dragController.dragNodes.length; i++) {
            var node = dragController.dragNodes[i]
            var finalX = node.x + applied.x
            var finalY = node.y + applied.y
            if (dragController.canvasRoot.snapToGrid && !snapAsGroup) {
                finalX = Math.round(
                    finalX / dragController.canvasRoot.gridSize
                ) * dragController.canvasRoot.gridSize
                finalY = Math.round(
                    finalY / dragController.canvasRoot.gridSize
                ) * dragController.canvasRoot.gridSize
            }
            dragController.nodeModel.update_position(
                node.id, finalX, finalY
            )
        }
        dragController.dragNodes = []
    }

    DragHandler {
        id: nodeDrag
        target: null
        acceptedButtons: Qt.LeftButton
        dragThreshold: 1
        grabPermissions: PointerHandler.CanTakeOverFromAnything
        enabled: dragController.nodeType !== "frame"
                 && dragController.canDrag
        onActiveChanged: {
            if (active) dragController.beginDrag()
            else dragController.finishDrag()
        }
        onTranslationChanged: {
            if (active) dragController.updateDrag(nodeDrag)
        }
    }

    Item {
        visible: dragController.nodeType === "frame"
        x: 0
        y: 0
        width: parent.width
        height: dragController.edgeThickness

        HoverHandler { cursorShape: Qt.SizeAllCursor }
        DragHandler {
            id: topDrag
            target: null
            acceptedButtons: Qt.LeftButton
            dragThreshold: 1
            grabPermissions: PointerHandler.CanTakeOverFromAnything
            enabled: dragController.canDrag
            onActiveChanged: {
                if (active) dragController.beginDrag()
                else dragController.finishDrag()
            }
            onTranslationChanged: {
                if (active) dragController.updateDrag(topDrag)
            }
        }
    }

    Item {
        visible: dragController.nodeType === "frame"
        x: 0
        y: Math.max(0, parent.height - height)
        width: Math.max(0, parent.width - 24)
        height: dragController.edgeThickness

        HoverHandler { cursorShape: Qt.SizeAllCursor }
        DragHandler {
            id: bottomDrag
            target: null
            acceptedButtons: Qt.LeftButton
            dragThreshold: 1
            grabPermissions: PointerHandler.CanTakeOverFromAnything
            enabled: dragController.canDrag
            onActiveChanged: {
                if (active) dragController.beginDrag()
                else dragController.finishDrag()
            }
            onTranslationChanged: {
                if (active) dragController.updateDrag(bottomDrag)
            }
        }
    }

    Item {
        visible: dragController.nodeType === "frame"
        x: 0
        y: dragController.edgeThickness
        width: dragController.edgeThickness
        height: Math.max(0, parent.height - dragController.edgeThickness)

        HoverHandler { cursorShape: Qt.SizeAllCursor }
        DragHandler {
            id: leftDrag
            target: null
            acceptedButtons: Qt.LeftButton
            dragThreshold: 1
            grabPermissions: PointerHandler.CanTakeOverFromAnything
            enabled: dragController.canDrag
            onActiveChanged: {
                if (active) dragController.beginDrag()
                else dragController.finishDrag()
            }
            onTranslationChanged: {
                if (active) dragController.updateDrag(leftDrag)
            }
        }
    }

    Item {
        visible: dragController.nodeType === "frame"
        x: Math.max(0, parent.width - width)
        y: dragController.edgeThickness
        width: dragController.edgeThickness
        height: Math.max(
            0,
            parent.height - dragController.edgeThickness - 24
        )

        HoverHandler { cursorShape: Qt.SizeAllCursor }
        DragHandler {
            id: rightDrag
            target: null
            acceptedButtons: Qt.LeftButton
            dragThreshold: 1
            grabPermissions: PointerHandler.CanTakeOverFromAnything
            enabled: dragController.canDrag
            onActiveChanged: {
                if (active) dragController.beginDrag()
                else dragController.finishDrag()
            }
            onTranslationChanged: {
                if (active) dragController.updateDrag(rightDrag)
            }
        }
    }
}
