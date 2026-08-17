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
    property bool dragging: false
    property bool previewPending: false

    readonly property real edgeThickness: 8
    readonly property bool canDrag:
        !dragController.canvasRoot.isLinkMode
        && !dragController.canvasRoot.isPanning
        && !dragController.canvasRoot.isEditorResizing
        && !dragController.resizeHovered
        && !dragController.resizing

    function beginDrag() {
        if (dragController.dragging) return
        dragController.nodeModel.clear_hovered()
        dragController.lastDx = 0
        dragController.lastDy = 0
        dragController.previewPending = false
        if (!dragController.canvasRoot.isCtrlHeld) {
            if (!dragController.nodeIsSelected) {
                dragController.nodeModel.set_selection([dragController.nodeId])
            }
        } else if (!dragController.nodeIsSelected) {
            dragController.nodeModel.add_selection([dragController.nodeId])
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
        dragController.dragging = true
        dragController.canvasRoot.activeNodeDragController = dragController
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
        if (!dragController.dragging) return
        var current = dragController.canvasRoot.screenToCanvas(
            handler.centroid.scenePosition.x,
            handler.centroid.scenePosition.y
        )
        var pressed = dragController.canvasRoot.screenToCanvas(
            handler.centroid.scenePressPosition.x,
            handler.centroid.scenePressPosition.y
        )
        dragController.lastDx = current.x - pressed.x
        dragController.lastDy = current.y - pressed.y

        dragController.previewPending = true
    }

    function currentPositionUpdates() {
        var updates = []

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
            updates.push({"id": node.id, "x": newX, "y": newY})
        }
        return updates
    }

    function advanceDragFrame() {
        if (!dragController.dragging || !dragController.previewPending) return
        dragController.previewPending = false
        dragController.nodeModel.preview_positions(
            dragController.currentPositionUpdates()
        )
    }

    function finishDrag() {
        if (!dragController.dragging) return

        var updates = dragController.currentPositionUpdates()
        dragController.previewPending = false
        try {
            if (updates.length > 0) {
                dragController.nodeModel.update_positions(updates)
            }
        } finally {
            dragController.dragNodes = []
            dragController.dragging = false
            if (dragController.canvasRoot
                    && dragController.canvasRoot.activeNodeDragController
                    === dragController) {
                dragController.canvasRoot.activeNodeDragController = null
            }
        }
    }

    function cancelDrag() {
        if (!dragController.dragging) return
        dragController.previewPending = false
        // Preview positions are intentionally reverted instead of persisted
        // when Qt reports a canceled pointer grab (focus loss, Wayland seat
        // transfer, or another PointerHandler taking ownership).
        var revert = []
        for (var i = 0; i < dragController.dragNodes.length; i++) {
            var node = dragController.dragNodes[i]
            revert.push({"id": node.id, "x": node.x, "y": node.y})
        }
        if (revert.length > 0) {
            dragController.nodeModel.preview_positions(revert)
        }
        dragController.dragNodes = []
        dragController.lastDx = 0
        dragController.lastDy = 0
        dragController.dragging = false
        if (dragController.canvasRoot
                && dragController.canvasRoot.activeNodeDragController
                === dragController) {
            dragController.canvasRoot.activeNodeDragController = null
        }
    }

    function handleDragActiveChanged(handler) {
        if (handler.active) {
            dragController.beginDrag()
            return
        }
        // Let a possible canceled() signal run first.  On a normal release
        // the session is still active and gets committed exactly once.
        Qt.callLater(function() {
            if (dragController.dragging) {
                dragController.finishDrag()
            }
        })
    }

    Component.onDestruction: {
        if (dragController.canvasRoot
                && dragController.canvasRoot.activeNodeDragController
                === dragController) {
            dragController.canvasRoot.activeNodeDragController = null
        }
    }

    DragHandler {
        id: nodeDrag
        target: null
        acceptedButtons: Qt.LeftButton
        dragThreshold: 1
        grabPermissions: PointerHandler.CanTakeOverFromAnything
        enabled: dragController.nodeType !== "frame"
                 && dragController.canDrag
        onActiveChanged: dragController.handleDragActiveChanged(nodeDrag)
        onCanceled: dragController.cancelDrag()
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
            onActiveChanged: dragController.handleDragActiveChanged(topDrag)
            onCanceled: dragController.cancelDrag()
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
            onActiveChanged: dragController.handleDragActiveChanged(bottomDrag)
            onCanceled: dragController.cancelDrag()
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
            onActiveChanged: dragController.handleDragActiveChanged(leftDrag)
            onCanceled: dragController.cancelDrag()
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
            onActiveChanged: dragController.handleDragActiveChanged(rightDrag)
            onCanceled: dragController.cancelDrag()
            onTranslationChanged: {
                if (active) dragController.updateDrag(rightDrag)
            }
        }
    }
}
