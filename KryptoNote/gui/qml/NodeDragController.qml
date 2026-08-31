import QtQuick


Item {
    id: dragController
    required property var canvasRoot
    required property var nodeModel
    required property Item contentLayer
    property Item delegateItem
    required property double nodeWorldX
    required property double nodeWorldY
    required property bool geometryInteractive
    property int nodeId: 0
    property string nodeType: ""
    property bool nodeIsSelected: false
    property bool resizeHovered: false
    property bool resizing: false
    property real lastDx: 0
    property real lastDy: 0
    property var dragNodes: []
    property bool dragging: false
    property var _lastPreviewUpdates: []
    property bool _transformNodesRetained: false

    readonly property real edgeThickness: 8
    readonly property bool canDrag:
        dragController.dragging
        || (dragController.geometryInteractive
        && !dragController.canvasRoot.canvasInputBlocked
        && !dragController.canvasRoot.isLinkMode
        && !dragController.canvasRoot.isPanning
        && !dragController.canvasRoot.isEditorResizing
        && !dragController.resizeHovered
        && !dragController.resizing)

    function beginDrag() {
        if (dragController.dragging || !dragController.geometryInteractive) return
        dragController.nodeModel.clear_hovered()
        dragController.lastDx = 0
        dragController.lastDy = 0
        dragController._lastPreviewUpdates = []
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
                "x": dragController.nodeWorldX,
                "y": dragController.nodeWorldY
            }]
        }
        for (var geometryIndex = 0;
             geometryIndex < dragController.dragNodes.length;
             geometryIndex++) {
            var geometryNode = dragController.dragNodes[geometryIndex]
            var nodeInteractive = Math.abs(Number(geometryNode.x))
                    <= dragController.canvasRoot.interactiveCoordinateLimit
                    && Math.abs(Number(geometryNode.y))
                    <= dragController.canvasRoot.interactiveCoordinateLimit
            if (typeof dragController.nodeModel.is_geometry_interactive
                    === "function") {
                nodeInteractive = dragController.nodeModel
                        .is_geometry_interactive(geometryNode.id)
            }
            if (!nodeInteractive) {
                dragController.dragNodes = []
                return
            }
        }
        var retainedIds = []
        for (var i = 0; i < dragController.dragNodes.length; i++)
            retainedIds.push(dragController.dragNodes[i].id)
        if (dragController.canvasRoot
                && typeof dragController.canvasRoot.retainTransformNodes
                   === "function") {
            dragController.canvasRoot.retainTransformNodes(retainedIds)
            dragController._transformNodesRetained = true
        }
        dragController.dragging = true
        dragController.canvasRoot.activeNodeDragController = dragController
    }

    function releaseTransformNodes() {
        if (!dragController._transformNodesRetained) return
        dragController._transformNodesRetained = false
        if (dragController.canvasRoot
                && typeof dragController.canvasRoot.releaseTransformNodes
                   === "function") {
            dragController.canvasRoot.releaseTransformNodes()
        }
    }

    function appliedDragDelta() {
        var origin = dragController.primaryStartPosition()
        var current = dragController.currentNodePosition()
        return Qt.point(current.x - origin.x, current.y - origin.y)
    }

    function primaryStartPosition() {
        for (var i = 0; i < dragController.dragNodes.length; i++) {
            var node = dragController.dragNodes[i]
            if (node.id === dragController.nodeId)
                return Qt.point(node.x, node.y)
        }
        return Qt.point(
            dragController.nodeWorldX,
            dragController.nodeWorldY
        )
    }

    function currentNodePosition() {
        var updates = dragController.currentPositionUpdates()
        for (var i = 0; i < updates.length; i++) {
            if (updates[i].id === dragController.nodeId)
                return Qt.point(updates[i].x, updates[i].y)
        }
        return dragController.primaryStartPosition()
    }

    function _updatesEqual(first, second) {
        if (!first || !second || first.length !== second.length) return false
        for (var i = 0; i < first.length; i++) {
            if (first[i].id !== second[i].id
                    || first[i].x !== second[i].x
                    || first[i].y !== second[i].y) return false
        }
        return true
    }

    function previewCurrentPosition() {
        var updates = dragController.currentPositionUpdates()
        if (dragController._updatesEqual(
                updates, dragController._lastPreviewUpdates)) return
        dragController._lastPreviewUpdates = updates
        dragController.nodeModel.preview_positions(updates)
    }

    function updateDrag(handler) {
        if (!dragController.dragging) return
        var scale = Math.max(
            Number(dragController.canvasRoot.contentScale),
            0.0001
        )
        dragController.lastDx = (
            Number(handler.centroid.scenePosition.x)
            - Number(handler.centroid.scenePressPosition.x)
        ) / scale
        dragController.lastDy = (
            Number(handler.centroid.scenePosition.y)
            - Number(handler.centroid.scenePressPosition.y)
        ) / scale
        dragController.previewCurrentPosition()
    }

    function _snapWorld(value, origin) {
        if (typeof dragController.canvasRoot.snapWorldCoordinate === "function") {
            return dragController.canvasRoot.snapWorldCoordinate(
                value,
                origin,
                dragController.canvasRoot.gridSize
            )
        }
        var spacing = Number(dragController.canvasRoot.gridSize)
        var phase = ((Number(origin) % spacing) + spacing) % spacing
        var local = Number(value) - Number(origin)
        return Number(origin)
                + Math.round((local + phase) / spacing) * spacing - phase
    }

    function currentPositionUpdates() {
        var updates = []

        var appliedX = dragController.lastDx
        var appliedY = dragController.lastDy
        var snapAsGroup = dragController.canvasRoot.snapToGrid
                          && dragController.nodeType === "frame"

        if (snapAsGroup) {
            var origin = dragController.primaryStartPosition()
            appliedX = dragController._snapWorld(
                origin.x + appliedX,
                dragController.canvasRoot.renderOriginX
            ) - origin.x
            appliedY = dragController._snapWorld(
                origin.y + appliedY,
                dragController.canvasRoot.renderOriginY
            ) - origin.y
        }

        for (var i = 0; i < dragController.dragNodes.length; i++) {
            var node = dragController.dragNodes[i]
            var newX = node.x + appliedX
            var newY = node.y + appliedY
            if (dragController.canvasRoot.snapToGrid && !snapAsGroup) {
                newX = dragController._snapWorld(
                    newX,
                    dragController.canvasRoot.renderOriginX
                )
                newY = dragController._snapWorld(
                    newY,
                    dragController.canvasRoot.renderOriginY
                )
            }
            updates.push({"id": node.id, "x": newX, "y": newY})
        }
        if (updates.length > 0) {
            var minimumX = updates[0].x
            var maximumX = updates[0].x
            var minimumY = updates[0].y
            var maximumY = updates[0].y
            for (var updateIndex = 1;
                 updateIndex < updates.length;
                 updateIndex++) {
                minimumX = Math.min(minimumX, updates[updateIndex].x)
                maximumX = Math.max(maximumX, updates[updateIndex].x)
                minimumY = Math.min(minimumY, updates[updateIndex].y)
                maximumY = Math.max(maximumY, updates[updateIndex].y)
            }
            var limit = Number(
                dragController.canvasRoot.interactiveCoordinateLimit
            )
            var correctionX = minimumX < -limit
                    ? -limit - minimumX
                    : (maximumX > limit ? limit - maximumX : 0.0)
            var correctionY = minimumY < -limit
                    ? -limit - minimumY
                    : (maximumY > limit ? limit - maximumY : 0.0)
            if (correctionX !== 0.0 || correctionY !== 0.0) {
                for (var correctionIndex = 0;
                     correctionIndex < updates.length;
                     correctionIndex++) {
                    updates[correctionIndex].x += correctionX
                    updates[correctionIndex].y += correctionY
                }
            }
        }
        return updates
    }

    function finishDrag() {
        if (!dragController.dragging) return

        var updates = dragController.currentPositionUpdates()
        try {
            if (updates.length > 0) {
                dragController.nodeModel.update_positions(updates)
            }
        } finally {
            dragController.dragNodes = []
            dragController._lastPreviewUpdates = []
            dragController.dragging = false
            if (dragController.canvasRoot
                    && dragController.canvasRoot.activeNodeDragController
                    === dragController) {
                dragController.canvasRoot.activeNodeDragController = null
            }
            dragController.releaseTransformNodes()
        }
    }

    function cancelDrag() {
        if (!dragController.dragging) return
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
        dragController._lastPreviewUpdates = []
        dragController.lastDx = 0
        dragController.lastDy = 0
        dragController.dragging = false
        if (dragController.canvasRoot
                && dragController.canvasRoot.activeNodeDragController
                === dragController) {
            dragController.canvasRoot.activeNodeDragController = null
        }
        dragController.releaseTransformNodes()
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
        dragController.releaseTransformNodes()
    }

    DragHandler {
        id: nodeDrag
        target: null
        acceptedButtons: Qt.LeftButton
        dragThreshold: 1
        grabPermissions: PointerHandler.CanTakeOverFromItems
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

        HoverHandler {
            enabled: dragController.canDrag
            cursorShape: Qt.SizeAllCursor
        }
        DragHandler {
            id: topDrag
            target: null
            acceptedButtons: Qt.LeftButton
            dragThreshold: 1
            grabPermissions: PointerHandler.CanTakeOverFromItems
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

        HoverHandler {
            enabled: dragController.canDrag
            cursorShape: Qt.SizeAllCursor
        }
        DragHandler {
            id: bottomDrag
            target: null
            acceptedButtons: Qt.LeftButton
            dragThreshold: 1
            grabPermissions: PointerHandler.CanTakeOverFromItems
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

        HoverHandler {
            enabled: dragController.canDrag
            cursorShape: Qt.SizeAllCursor
        }
        DragHandler {
            id: leftDrag
            target: null
            acceptedButtons: Qt.LeftButton
            dragThreshold: 1
            grabPermissions: PointerHandler.CanTakeOverFromItems
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

        HoverHandler {
            enabled: dragController.canDrag
            cursorShape: Qt.SizeAllCursor
        }
        DragHandler {
            id: rightDrag
            target: null
            acceptedButtons: Qt.LeftButton
            dragThreshold: 1
            grabPermissions: PointerHandler.CanTakeOverFromItems
            enabled: dragController.canDrag
            onActiveChanged: dragController.handleDragActiveChanged(rightDrag)
            onCanceled: dragController.cancelDrag()
            onTranslationChanged: {
                if (active) dragController.updateDrag(rightDrag)
            }
        }
    }
}
