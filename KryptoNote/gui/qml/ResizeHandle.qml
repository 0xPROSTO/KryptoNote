import QtQuick


Item {
    id: handle

    required property var canvasRoot
    required property var nodeModel
    required property var appTheme
    required property int nodeId
    required property Item delegateItem
    required property double nodeWorldX
    required property double nodeWorldY
    required property bool geometryInteractive

    property bool nodeHovered: false
    property bool nodeSelected: false
    property bool passiveSurfaceHovered: false
    property real minimumNodeWidth: 100
    property real minimumNodeHeight: 50
    property real topEdgeExclusionWidth: 0
    property real topEdgeExclusionHeight: 0

    readonly property real _inverseCanvasScale:
            1 / Math.max(handle.canvasRoot.visualDetailScale, 0.25)
    readonly property real _edgeHitSize: Math.min(
        Math.min(width, height) / 3,
        8 * _inverseCanvasScale
    )
    readonly property real _cornerHitSize: Math.min(
        Math.min(width, height) / 2,
        14 * _inverseCanvasScale
    )
    readonly property real _primaryCornerHitSize: Math.min(
        Math.min(width, height) / 2,
        24 * _inverseCanvasScale
    )
    readonly property real _iconSize: Math.min(
        _primaryCornerHitSize,
        20 * _inverseCanvasScale
    )
    readonly property real _iconGeometryScale: Math.min(
        _inverseCanvasScale,
        _iconSize / 20
    )
    readonly property real _topEdgeStart: _cornerHitSize
    readonly property real _topEdgeEnd: Math.max(
        _topEdgeStart,
        width - _cornerHitSize
    )
    readonly property real _topEdgeExclusionSize: Math.min(
        Math.max(0, topEdgeExclusionWidth),
        Math.max(0, _topEdgeEnd - _topEdgeStart)
    )
    readonly property real _topEdgeExclusionStart: Math.max(
        _topEdgeStart,
        (width - _topEdgeExclusionSize) / 2
    )
    readonly property real _topEdgeExclusionEnd: Math.min(
        _topEdgeEnd,
        (width + _topEdgeExclusionSize) / 2
    )
    readonly property real _topEdgeContentExclusionSize: Math.min(
        width,
        Math.max(0, topEdgeExclusionWidth)
    )
    readonly property real _topEdgeContentExclusionStart:
            (width - _topEdgeContentExclusionSize) / 2
    readonly property real _topEdgeContentExclusionEnd:
            (width + _topEdgeContentExclusionSize) / 2
    readonly property bool topEdgeExclusionHovered:
            topEdgeExclusionHeight > 0
            && nodeHover.hovered
            && nodeHover.point.position.x >= _topEdgeContentExclusionStart
            && nodeHover.point.position.x <= _topEdgeContentExclusionEnd
            && nodeHover.point.position.y >= 0
            && nodeHover.point.position.y <= Math.min(
                height,
                topEdgeExclusionHeight
            )
    readonly property point hoverPosition: nodeHover.point.position
    readonly property bool _isHovered:
            topLeft.hovered || topEdgeLeft.hovered
            || topEdgeRight.hovered || topRight.hovered
            || leftEdge.hovered || rightEdge.hovered
            || bottomLeft.hovered || bottomEdge.hovered
            || bottomRight.hovered
    readonly property bool _pointerHovered:
            nodeHover.hovered || _isHovered
    readonly property bool _isActive: _resizing
    readonly property bool _showIcon:
            nodeSelected || nodeHovered || passiveSurfaceHovered
            || _pointerHovered || _isActive
    readonly property bool _canResize:
        handle._resizing
            || (handle.geometryInteractive
            && !handle.canvasRoot.canvasInputBlocked
            && !handle.canvasRoot.isNodeDragging
            && !handle.canvasRoot.isLinkMode
            && !handle.canvasRoot.isPanning
            && !handle.canvasRoot.isEditorResizing)

    property bool _resizing: false
    property var _activeRegion: null
    property real _startX: 0
    property real _startY: 0
    property real _startWidth: 0
    property real _startHeight: 0
    property real _pendingX: 0
    property real _pendingY: 0
    property real _pendingWidth: 0
    property real _pendingHeight: 0
    property bool _transformNodesRetained: false

    function _snappedSize(value, minimum) {
        var size = Math.max(minimum, value)
        if (!handle.canvasRoot.snapToGrid) return size
        return Math.max(
            minimum,
            Math.round(size / handle.canvasRoot.gridSize)
                * handle.canvasRoot.gridSize
        )
    }

    function _axisGeometry(startPosition, startSize, delta, direction, minimum) {
        if (direction === 0) return [startPosition, startSize]

        var size = direction < 0 ? startSize - delta : startSize + delta
        size = handle._snappedSize(size, minimum)
        var position = direction < 0
                ? startPosition + startSize - size
                : startPosition
        return [position, size]
    }

    function _clampLeadingAxis(geometry, startPosition, startSize,
                               direction, limit) {
        if (direction >= 0) return geometry
        var position = Math.max(-limit, Math.min(limit, geometry[0]))
        if (position === geometry[0]) return geometry
        return [position, startPosition + startSize - position]
    }

    function beginResize(region) {
        if (handle._resizing || !handle._canResize
                || !handle.geometryInteractive) return

        handle._activeRegion = region
        handle._resizing = true
        handle._startX = handle.nodeWorldX
        handle._startY = handle.nodeWorldY
        handle._startWidth = handle.delegateItem.width
        handle._startHeight = handle.delegateItem.height
        handle._pendingX = handle._startX
        handle._pendingY = handle._startY
        handle._pendingWidth = handle._startWidth
        handle._pendingHeight = handle._startHeight
        if (handle.canvasRoot
                && typeof handle.canvasRoot.retainTransformNodes
                   === "function") {
            handle.canvasRoot.retainTransformNodes([handle.nodeId])
            handle._transformNodesRetained = true
        }
        handle.delegateItem._isResizing = true
        handle.canvasRoot.activeNodeResizeController = handle
    }

    function updateResize(region, dragHandler) {
        if (!handle._resizing || handle._activeRegion !== region) return

        var scale = Math.max(Number(handle.canvasRoot.contentScale), 0.0001)
        var deltaX = (
            Number(dragHandler.centroid.scenePosition.x)
            - Number(dragHandler.centroid.scenePressPosition.x)
        ) / scale
        var deltaY = (
            Number(dragHandler.centroid.scenePosition.y)
            - Number(dragHandler.centroid.scenePressPosition.y)
        ) / scale
        var horizontal = handle._axisGeometry(
            handle._startX,
            handle._startWidth,
            deltaX,
            region.horizontalDirection,
            handle.minimumNodeWidth
        )
        var vertical = handle._axisGeometry(
            handle._startY,
            handle._startHeight,
            deltaY,
            region.verticalDirection,
            handle.minimumNodeHeight
        )

        var limit = Number(handle.canvasRoot.interactiveCoordinateLimit)
        horizontal = handle._clampLeadingAxis(
            horizontal,
            handle._startX,
            handle._startWidth,
            region.horizontalDirection,
            limit
        )
        vertical = handle._clampLeadingAxis(
            vertical,
            handle._startY,
            handle._startHeight,
            region.verticalDirection,
            limit
        )

        if (handle._pendingX !== horizontal[0]
                || handle._pendingY !== vertical[0]
                || handle._pendingWidth !== horizontal[1]
                || handle._pendingHeight !== vertical[1]) {
            handle._pendingX = horizontal[0]
            handle._pendingY = vertical[0]
            handle._pendingWidth = horizontal[1]
            handle._pendingHeight = vertical[1]
            handle._applyResizePreview()
        }
    }

    function _applyResizePreview() {
        if (!handle._resizing) return
        if (handle._activeRegion
                && (handle._activeRegion.horizontalDirection < 0
                    || handle._activeRegion.verticalDirection < 0)) {
            handle.nodeModel.preview_position(
                handle.nodeId,
                handle._pendingX,
                handle._pendingY
            )
        }
        handle.nodeModel.preview_size(
            handle.nodeId,
            handle._pendingWidth,
            handle._pendingHeight
        )
    }

    function scheduleFinishResize(region) {
        Qt.callLater(function() {
            if (handle._resizing && handle._activeRegion === region) {
                handle.finishResize()
            }
        })
    }

    function finishResize() {
        if (!handle._resizing) return

        var region = handle._activeRegion
        try {
            if (region && (region.horizontalDirection < 0
                           || region.verticalDirection < 0)) {
                handle.nodeModel.update_position(
                    handle.nodeId,
                    handle._pendingX,
                    handle._pendingY
                )
            }
            handle.nodeModel.update_size(
                handle.nodeId,
                handle._pendingWidth,
                handle._pendingHeight
            )
        } finally {
            handle._endResizeSession()
        }
    }

    function cancelResize(region) {
        if (!handle._resizing
                || (region && handle._activeRegion !== region)) return

        try {
            handle.nodeModel.preview_position(
                handle.nodeId,
                handle._startX,
                handle._startY
            )
            handle.nodeModel.preview_size(
                handle.nodeId,
                handle._startWidth,
                handle._startHeight
            )
        } finally {
            handle._endResizeSession()
        }
    }

    function _endResizeSession() {
        // Mark the controller finished before clearing the delegate flag.
        // That flag owns the ResizeHandle Loader; clearing it first can
        // synchronously destroy this object and turn a normal release into
        // Component.onDestruction -> cancelResize() -> visual rollback.
        handle._activeRegion = null
        handle._resizing = false
        if (handle.canvasRoot
                && handle.canvasRoot.activeNodeResizeController === handle) {
            handle.canvasRoot.activeNodeResizeController = null
        }
        if (handle._transformNodesRetained) {
            handle._transformNodesRetained = false
            if (handle.canvasRoot
                    && typeof handle.canvasRoot.releaseTransformNodes
                       === "function") {
                handle.canvasRoot.releaseTransformNodes()
            }
        }
        // Keep this last: it is allowed to unload and destroy `handle`.
        if (handle.delegateItem) handle.delegateItem._isResizing = false
    }

    Component.onDestruction: {
        if (handle._resizing) handle.cancelResize(null)
        else if (handle.canvasRoot
                 && handle.canvasRoot.activeNodeResizeController === handle) {
            handle.canvasRoot.activeNodeResizeController = null
        }
        if (handle._transformNodesRetained && handle.canvasRoot
                && typeof handle.canvasRoot.releaseTransformNodes
                   === "function") {
            handle.canvasRoot.releaseTransformNodes()
        }
    }

    HoverHandler {
        id: nodeHover

        onHoveredChanged: {
            if (!hovered) {
                handle.nodeModel.set_hovered(handle.nodeId, false)
                return
            }

            Qt.callLater(function() {
                if (nodeHover.hovered) {
                    handle.nodeModel.set_hovered(handle.nodeId, true)
                }
            })
        }
    }

    Item {
        id: gripIcon
        z: 3
        width: handle._iconSize
        height: handle._iconSize
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        opacity: handle._showIcon ? 0.95 : 0
        Accessible.ignored: true

        readonly property color barColor:
                handle._isHovered || handle._isActive
                ? handle.appTheme.accentMain
                : handle.appTheme.resizeHandle
        readonly property real barThickness:
                2 * handle._iconGeometryScale

        Rectangle {
            width: 16 * handle._iconGeometryScale
            height: gripIcon.barThickness
            x: 11 * handle._iconGeometryScale - width / 2
            y: 11 * handle._iconGeometryScale - height / 2
            radius: height / 2
            rotation: -45
            transformOrigin: Item.Center
            antialiasing: true
            color: gripIcon.barColor
        }

        Rectangle {
            width: 8 * handle._iconGeometryScale
            height: gripIcon.barThickness
            x: 14 * handle._iconGeometryScale - width / 2
            y: 14 * handle._iconGeometryScale - height / 2
            radius: height / 2
            rotation: -45
            transformOrigin: Item.Center
            antialiasing: true
            color: gripIcon.barColor
        }

        Behavior on opacity {
            NumberAnimation {
                duration: handle.appTheme.durationState
                easing.type: Easing.OutCubic
            }
        }
    }

    component ResizeRegion: Item {
        id: region
        required property var resizeController
        required property int horizontalDirection
        required property int verticalDirection
        required property int resizeCursor
        readonly property bool hovered: regionHover.hovered

        enabled: region.resizeController._canResize

        HoverHandler {
            id: regionHover
            cursorShape: region.resizeCursor
        }

        DragHandler {
            id: regionDrag
            target: null
            acceptedButtons: Qt.LeftButton
            dragThreshold: 0
            grabPermissions: PointerHandler.CanTakeOverFromItems

            onActiveChanged: {
                if (active) region.resizeController.beginResize(region)
                else region.resizeController.scheduleFinishResize(region)
            }
            onCanceled: region.resizeController.cancelResize(region)
            onTranslationChanged: {
                if (active) {
                    region.resizeController.updateResize(region, regionDrag)
                }
            }
        }
    }

    ResizeRegion {
        id: topLeft
        z: 2
        resizeController: handle
        horizontalDirection: -1
        verticalDirection: -1
        resizeCursor: Qt.SizeFDiagCursor
        x: 0
        y: 0
        width: handle._cornerHitSize
        height: handle._cornerHitSize
    }

    ResizeRegion {
        id: topEdgeLeft
        z: 1
        resizeController: handle
        horizontalDirection: 0
        verticalDirection: -1
        resizeCursor: Qt.SizeVerCursor
        x: handle._topEdgeStart
        y: 0
        width: Math.max(0, handle._topEdgeExclusionStart - x)
        height: handle._edgeHitSize
    }

    ResizeRegion {
        id: topEdgeRight
        z: 1
        resizeController: handle
        horizontalDirection: 0
        verticalDirection: -1
        resizeCursor: Qt.SizeVerCursor
        x: handle._topEdgeExclusionEnd
        y: 0
        width: Math.max(0, handle._topEdgeEnd - x)
        height: handle._edgeHitSize
    }

    ResizeRegion {
        id: topRight
        z: 2
        resizeController: handle
        horizontalDirection: 1
        verticalDirection: -1
        resizeCursor: Qt.SizeBDiagCursor
        x: Math.max(0, parent.width - width)
        y: 0
        width: handle._cornerHitSize
        height: handle._cornerHitSize
    }

    ResizeRegion {
        id: leftEdge
        z: 1
        resizeController: handle
        horizontalDirection: -1
        verticalDirection: 0
        resizeCursor: Qt.SizeHorCursor
        x: 0
        y: handle._cornerHitSize
        width: handle._edgeHitSize
        height: Math.max(0, parent.height - 2 * handle._cornerHitSize)
    }

    ResizeRegion {
        id: rightEdge
        z: 1
        resizeController: handle
        horizontalDirection: 1
        verticalDirection: 0
        resizeCursor: Qt.SizeHorCursor
        x: Math.max(0, parent.width - width)
        y: handle._cornerHitSize
        width: handle._edgeHitSize
        height: Math.max(
            0,
            parent.height - handle._cornerHitSize
                - handle._primaryCornerHitSize
        )
    }

    ResizeRegion {
        id: bottomLeft
        z: 2
        resizeController: handle
        horizontalDirection: -1
        verticalDirection: 1
        resizeCursor: Qt.SizeBDiagCursor
        x: 0
        y: Math.max(0, parent.height - height)
        width: handle._cornerHitSize
        height: handle._cornerHitSize
    }

    ResizeRegion {
        id: bottomEdge
        z: 1
        resizeController: handle
        horizontalDirection: 0
        verticalDirection: 1
        resizeCursor: Qt.SizeVerCursor
        x: handle._cornerHitSize
        y: Math.max(0, parent.height - height)
        width: Math.max(
            0,
            parent.width - handle._cornerHitSize
                - handle._primaryCornerHitSize
        )
        height: handle._edgeHitSize
    }

    ResizeRegion {
        id: bottomRight
        z: 2
        resizeController: handle
        horizontalDirection: 1
        verticalDirection: 1
        resizeCursor: Qt.SizeFDiagCursor
        x: Math.max(0, parent.width - width)
        y: Math.max(0, parent.height - height)
        width: handle._primaryCornerHitSize
        height: handle._primaryCornerHitSize
    }
}
