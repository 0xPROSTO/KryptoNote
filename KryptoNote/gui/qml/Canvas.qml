import QtQuick

Rectangle {
    id: root
    // The Python side exposes one stable CanvasRuntime object through the
    // engine root context before this component is loaded.  Keeping the
    // individual dependencies as bindings prevents PySide QVariant-map
    // conversion from producing null QObject references on Linux.
    // qmllint disable unqualified
    property var canvasRuntime: canvasRuntimeContext
    // qmllint enable unqualified
    readonly property var appTheme: canvasRuntime ? canvasRuntime.appTheme : null
    readonly property var nodeModel: canvasRuntime ? canvasRuntime.nodeModel : null
    readonly property var connectionModel: canvasRuntime ? canvasRuntime.connectionModel : null
    readonly property var nodeViewportModel: canvasRuntime ? canvasRuntime.nodeViewportModel : null
    readonly property var connectionViewportModel: canvasRuntime ? canvasRuntime.connectionViewportModel : null
    readonly property var canvasController: canvasRuntime ? canvasRuntime.canvasController : null
    readonly property var viewerController: canvasRuntime ? canvasRuntime.viewerController : null
    readonly property var frameClock: canvasRuntime ? canvasRuntime.frameClock : null
    readonly property bool wheelPreferAngleDelta: canvasRuntime
            ? canvasRuntime.preferAngleDelta : false
    color: root.appTheme ? root.appTheme.bgCanvas : "#121212"
    palette.toolTipBase: root.appTheme
                         ? root.appTheme.bgPopover : "#232425"
    palette.toolTipText: root.appTheme
                         ? root.appTheme.textMain : "#efefef"
    clip: true
    focus: true

    property alias contentScale: viewport.contentScale
    readonly property real minimumScale: viewport.minScale
    property real _visualDetailScale: 1.0
    readonly property real visualDetailScale: _visualDetailScale
    readonly property real cameraOffsetX: viewport.cameraOffsetX
    readonly property real cameraOffsetY: viewport.cameraOffsetY
    property real gridSize: 100.0
    property real gridMain: 500.0
    property bool snapToGrid: root.canvasController ? root.canvasController.snap_to_grid : false

    property alias isLinkMode: inputLayer.isLinkMode
    property alias isEraserMode: inputLayer.isEraserMode
    property alias isCtrlHeld: inputLayer.isCtrlHeld
    property alias isShiftHeld: inputLayer.isShiftHeld
    property alias isPanning: inputLayer.isPanning
    property alias gestureState: inputLayer.gestureState
    property bool isEditorResizing: textEditorPanel.resizing || mediaViewerPanel.resizing
    property alias isSearchResizing: searchPanel.resizing
    property bool isTextEditorOpen: textEditorPanel.open
    property bool isFrameEditorOpen: frameEditor.visible
    property bool isNodePropertiesOpen: nodeProperties.visible
    readonly property int propertiesFocusNodeId:
            nodeProperties.visible ? nodeProperties.nodeId : 0
    property bool isTagPickerOpen: globalTagPicker.visible || mediaViewerPanel.tagPickerOpen
    property bool isSearchPanelOpen: searchPanel.open
    property bool isMediaViewerOpen: viewerController.active && !viewerController.detached
    readonly property bool arrayListSuppressed:
            textEditorPanel.open
            || frameEditor.visible
            || nodeProperties.visible
            || (viewerController.active && !viewerController.detached)
            || root._arrayListHandoffActive
            || root._pendingMediaEditorNodeId > 0
    property bool isMediaViewerExpanded: mediaViewerPanel.expanded
    property bool isMediaRenameEditing: mediaViewerPanel.renameEditing
    readonly property bool hasUnsavedEditorChanges:
            (textEditorPanel.open && textEditorPanel.dirty)
            || (frameEditor.visible && frameEditor.dirty)
    property int hoveredConnectionId: 0
    property var activeNodeDragController: null
    property var activeNodeResizeController: null
    readonly property bool isNodeDragging:
            root.activeNodeDragController !== null
    readonly property bool isNodeResizing:
            root.activeNodeResizeController !== null
    readonly property bool isNodeTransforming:
            root.isNodeDragging || root.isNodeResizing
    property point _pendingConnectionHit: Qt.point(0, 0)
    property real _pendingConnectionRadius: 0
    property bool _connectionHitPending: false
    property bool _viewportUpdatePending: false
    readonly property bool frameClockNeeded: _connectionHitPending
            || isNodeTransforming
            || viewport.frameClockNeeded
    property int _lastReportedZoomPercent: -1

    property alias _contentLayerX: contentLayer.x
    property alias _contentLayerY: contentLayer.y
    property real _editorReturnX: 0
    property real _editorReturnY: 0
    property bool _hasEditorReturn: false
    property real _mediaReturnX: 0
    property real _mediaReturnY: 0
    property bool _hasMediaReturn: false
    property bool _suppressEditorCameraReturn: false
    property bool _suppressMediaCameraReturn: false
    property bool _searchCameraOffsetActive: false
    property string _pendingMediaEditorAction: ""
    property int _pendingMediaEditorNodeId: 0
    // Keep the native ArrayList outside the canvas while one surface hands
    // focus to another. QML can otherwise expose a one-frame gap between the
    // closing and opening panels.
    property bool _arrayListHandoffActive: false

    signal applicationCloseRequested()
    signal arrayListSuppressionChanged(bool suppressed)

    Component.onCompleted: {
        viewport.initialize()
        root._visualDetailScale = root.contentScale
        root.updateViewportModels()
        root._lastReportedZoomPercent = Math.round(root.contentScale * 100)
        if (root.frameClock) root.frameClock.setActive(root.frameClockNeeded)
    }
    Component.onDestruction: {
        if (root.frameClock) root.frameClock.setActive(false)
    }
    onFrameClockNeededChanged: {
        if (root.frameClock) root.frameClock.setActive(root.frameClockNeeded)
    }
    onIsNodeTransformingChanged: {
        if (isNodeTransforming) {
            root._connectionHitPending = false
            root.hoveredConnectionId = 0
        }
    }
    onWidthChanged: {
        viewport.ensureInitialized()
        root.scheduleViewportUpdate()
    }
    onHeightChanged: {
        viewport.ensureInitialized()
        root.scheduleViewportUpdate()
    }
    onIsTextEditorOpenChanged: {
        if (!isTextEditorOpen && globalTagPicker.visible) {
            globalTagPicker.close()
        }
    }
    onArrayListSuppressedChanged:
        root.arrayListSuppressionChanged(root.arrayListSuppressed)

    GridLayer {
        appTheme: root.appTheme
        anchors.fill: parent
        offset: Qt.vector2d(viewport.cameraOffsetX, viewport.cameraOffsetY)
        viewScale: viewport.contentScale
        viewportSize: Qt.vector2d(root.width, root.height)
        gridSize: root.gridSize
        gridMain: root.gridMain
    }

    Item {
        id: contentLayer
        z: 1
        enabled: !root.isNodePropertiesOpen
        x: 0
        y: 0
        transformOrigin: Item.TopLeft
        scale: root.contentScale

        NodeLayer {
            z: 0
            viewportModel: root.nodeViewportModel
            canvasRoot: root
            nodeModel: root.nodeModel
            canvasController: root.canvasController
            viewerController: root.viewerController
            contentLayer: contentLayer
            appTheme: root.appTheme
            framesOnly: true
            anchors.fill: parent
            onContextMenuRequested: function(nodeId, nodeType, sourceItem, localX, localY) {
                canvasContextMenu.openForNode(nodeId, nodeType, sourceItem, localX, localY)
            }
        }

        ConnectionLayer {
            z: 1
            viewportModel: root.connectionViewportModel
            canvasRoot: root
            canvasController: root.canvasController
            appTheme: root.appTheme
            anchors.fill: parent
        }

        NodeLayer {
            z: 2
            viewportModel: root.nodeViewportModel
            canvasRoot: root
            nodeModel: root.nodeModel
            canvasController: root.canvasController
            viewerController: root.viewerController
            contentLayer: contentLayer
            appTheme: root.appTheme
            framesOnly: false
            anchors.fill: parent
            onContextMenuRequested: function(nodeId, nodeType, sourceItem, localX, localY) {
                canvasContextMenu.openForNode(nodeId, nodeType, sourceItem, localX, localY)
            }
        }
    }

    NodeContextMenu {
        canvasController: root.canvasController
        appTheme: root.appTheme
        id: canvasContextMenu
        onRequestedTags: function(nodeId, anchorItem) {
            root.openTagPickerForNode(nodeId, anchorItem)
        }
        onRequestedSearch: root.openSearchPanel()
    }

    RubberBandSelection {
        nodeModel: root.nodeModel
        appTheme: root.appTheme
        viewport: viewport
        id: rubberBand
        z: 2
    }

    CanvasViewport {
        id: viewport
        anchors.fill: parent
        contentLayer: contentLayer
        preferAngleDelta: root.wheelPreferAngleDelta
        onZoomFinished: function(scale) {
            var percent = Math.round(scale * 100)
            if (percent !== root._lastReportedZoomPercent) {
                root._lastReportedZoomPercent = percent
                if (root.canvasController) {
                    root.canvasController.report_zoom(scale)
                }
            }
            root._visualDetailScale = scale
            root.scheduleViewportUpdate()
        }
        onZoomActiveChanged: {
            if (viewport.zoomActive) viewportUpdateTimer.stop()
        }
        onViewportCenterShifted: function(deltaX, deltaY) {
            if (root._hasEditorReturn) {
                root._editorReturnX += deltaX
                root._editorReturnY += deltaY
            }
            if (root._hasMediaReturn) {
                root._mediaReturnX += deltaX
                root._mediaReturnY += deltaY
            }
        }
    }

    CanvasInputLayer {
        nodeModel: root.nodeModel
        connectionModel: root.connectionModel
        canvasController: root.canvasController
        id: inputLayer
        enabled: !root.isNodePropertiesOpen
        anchors.fill: parent
        focus: true
        contentLayer: contentLayer
        viewport: viewport
        rubberBand: rubberBand
        contentScale: root.contentScale
        gridSize: root.gridSize
        snapToGrid: root.snapToGrid
        onContextMenuRequested: function(
            sourceItem, localX, localY, contentX, contentY
        ) {
            var connectionId = 0
            if (root.connectionModel) {
                connectionId = root.connectionModel.hit_test_connection(
                    contentX,
                    contentY,
                    10 / Math.max(root.contentScale, 0.12)
                )
            }
            if (connectionId > 0) {
                canvasContextMenu.openForConnection(
                    connectionId,
                    sourceItem,
                    localX,
                    localY
                )
                return
            }
            canvasContextMenu.openForCanvas(
                sourceItem,
                localX,
                localY,
                contentX,
                contentY
            )
        }
    }

    SearchPanel {
        nodeModel: root.nodeModel
        canvasController: root.canvasController
        appTheme: root.appTheme
        id: searchPanel
        z: 19
        height: parent.height

        onRequestedCenter: function(nodeId) {
            root.centerOnNodeFromSearch(nodeId)
        }

        onRequestedCloseCompensation: function(panelWidth) {
            root.compensateSearchClose(panelWidth)
        }

        onStatusChanged: function(message) {
            root.canvasController.set_status_message(message, message === "Ready" ? "normal" : "accent")
        }
    }

    TextEditorPanel {
        canvasController: root.canvasController
        appTheme: root.appTheme
        id: textEditorPanel
        z: 20
        height: parent.height
        x: parent.width - width + slideOffset

        Behavior on slideOffset { NumberAnimation { duration: 220; easing.type: Easing.OutCubic } }

        onRequestedCenter: function(nodeId) {
            root.centerOnNodeForEditor(nodeId)
        }

        onRequestedReturn: {
            root.returnFromEditor()
        }

        onRequestedTagPicker: function(nodeId, anchorItem) {
            root.openTagPickerForNode(nodeId, anchorItem)
        }
    }

    MediaViewerPanel {
        id: mediaViewerPanel
        z: 30
        appTheme: root.appTheme
        canvasController: root.canvasController
        viewerController: root.viewerController
        open: root.isMediaViewerOpen

        onRequestedClose: root.viewerController.close_viewer()
        onRequestedApplicationClose: root.applicationCloseRequested()
        onRequestedCenter: function(nodeId) {
            root.centerOnNodeForMedia(nodeId)
        }
        onExpandedChangedByUser: function(nextExpanded) {
            if (!nextExpanded && root.viewerController.active)
                root.centerOnNodeForMedia(root.viewerController.nodeId)
        }
    }

    NodePropertiesOverlay {
        id: nodeProperties
        appTheme: root.appTheme
        nodeModel: root.nodeModel
        contentLayer: contentLayer
        contentScale: root.contentScale

        onClosed: root.forceActiveFocus()
    }

    FrameEditorDialog {
        id: frameEditor
        canvasController: root.canvasController
        appTheme: root.appTheme

        onRequestedTagPicker: function(nodeId, anchorItem) {
            root.openTagPickerForNode(nodeId, anchorItem)
        }
        onRequestedClose: root.closeTagPicker()
    }

    TagPicker {
        canvasController: root.canvasController
        appTheme: root.appTheme
        id: globalTagPicker
        onTagsChanged: {
            if (textEditorPanel.open && textEditorPanel.nodeId === globalTagPicker.nodeId) {
                textEditorPanel.refreshTags()
            }
            if (frameEditor.visible
                    && frameEditor.nodeId === globalTagPicker.nodeId) {
                frameEditor.refreshTags()
            }
            if (root.viewerController.active
                    && root.viewerController.nodeId === globalTagPicker.nodeId) {
                root.viewerController.notify_tags_changed()
            }
            searchPanel.syncTagsAndRefresh()
        }
    }

    Connections {
        target: root.viewerController

        function onSessionOpened(nodeId) {
            if (!root.viewerController.detached) {
                root.beginMediaViewer(nodeId)
                root.finishArrayListHandoff()
            }
        }

        function onSessionClosed() {
            root.returnFromMediaViewer()
            var pendingAction = root._pendingMediaEditorAction
            var pendingNodeId = root._pendingMediaEditorNodeId
            if (pendingNodeId > 0) {
                Qt.callLater(function() {
                    if (pendingAction === "text")
                        root.openEditorForNode(pendingNodeId)
                    else if (pendingAction === "frame")
                        root.openFrameEditorForNode(pendingNodeId)
                    root._pendingMediaEditorAction = ""
                    root._pendingMediaEditorNodeId = 0
                })
            } else {
                root._pendingMediaEditorAction = ""
                root._pendingMediaEditorNodeId = 0
            }
        }

        function onDetachedChanged() {
            if (root.viewerController.detached) {
                root.returnFromMediaViewer()
            } else if (root.viewerController.active) {
                root.beginMediaViewer(root.viewerController.nodeId)
            }
        }

        function onTagsEdited(nodeId) {
            if (globalTagPicker.visible && globalTagPicker.nodeId === nodeId)
                globalTagPicker.refresh()
            searchPanel.syncTagsAndRefresh()
        }
    }

    Connections {
        target: mediaViewerPanel

        function onDescriptionGuardCanceled(action) {
            root._pendingMediaEditorAction = ""
            root._pendingMediaEditorNodeId = 0
            root.finishArrayListHandoff()
        }
    }

    Connections {
        target: root.canvasController
        function onOpenTextEditorRequested(nodeId) {
            root.openEditorForNode(nodeId)
        }
        function onOpenFrameEditorRequested(nodeId) {
            root.openFrameEditorForNode(nodeId)
        }
        function onOpenNodePropertiesRequested(nodeId) {
            nodeProperties.openForNode(nodeId)
        }
        function onNodePropertiesUpdated(nodeId) {
            nodeProperties.refreshForNode(nodeId)
        }
    }

    HoverHandler {
        id: globalHover
        onHoveredChanged: {
            if (!hovered) {
                root._connectionHitPending = false
                root.hoveredConnectionId = 0
            }
        }
        onPointChanged: {
            if (!point) return
            if (!root.canvasController || !root.connectionModel) return
            var contentPos = viewport.screenToCanvas(
                point.position.x,
                point.position.y
            )
            if (!root.isNodeTransforming) {
                root._pendingConnectionHit = Qt.point(contentPos.x, contentPos.y)
                root._pendingConnectionRadius = 10 / Math.max(root.contentScale, 0.12)
                root._connectionHitPending = true
            }
            if (!coordThrottleTimer.running) {
                root.canvasController.report_mouse_position(contentPos.x, contentPos.y)
                coordThrottleTimer.start()
            }
        }
    }

    Connections {
        target: root.frameClock
        function onTick(frameTime) {
            if (root.activeNodeDragController) {
                root.activeNodeDragController.advanceDragFrame()
            }
            if (root.activeNodeResizeController) {
                root.activeNodeResizeController.advanceResizeFrame()
            }
            viewport.advanceFrame(frameTime)
            if (root._connectionHitPending && !root.isNodeTransforming) {
                root._connectionHitPending = false
                if (globalHover.hovered) {
                    root.hoveredConnectionId = root.connectionModel.hit_test_connection(
                        root._pendingConnectionHit.x,
                        root._pendingConnectionHit.y,
                        root._pendingConnectionRadius
                    )
                }
            }
        }
    }

    Timer {
        id: coordThrottleTimer
        interval: 32
        repeat: false
    }

    Timer {
        id: viewportUpdateTimer
        interval: 16
        repeat: false
        onTriggered: {
            if (!root._viewportUpdatePending || viewport.zoomActive) return
            root._viewportUpdatePending = false
            root.updateViewportModels()
        }
    }

    Connections {
        target: contentLayer
        function onXChanged() { root.scheduleViewportUpdate() }
        function onYChanged() { root.scheduleViewportUpdate() }
    }

    Connections {
        target: viewport
        function onContentScaleChanged() { root.scheduleViewportUpdate() }
    }

    onActiveFocusChanged: {
        if (!activeFocus) {
            resetModifiers()
        }
    }

    Keys.onPressed: function(event) {
        inputLayer.handleKeyPressed(event)
    }

    Keys.onReleased: function(event) {
        inputLayer.handleKeyReleased(event)
    }

    function resetModifiers() {
        inputLayer.resetModifiers()
        viewport.stopKeyboardPan()
    }

    function updateViewportModels() {
        if (!root.nodeViewportModel || !root.connectionViewportModel) return
        var visible = viewport.visibleCanvasRect(480 / Math.max(root.contentScale, 0.12))
        root.nodeViewportModel.updateViewport(
            visible.x,
            visible.y,
            visible.x + visible.width,
            visible.y + visible.height
        )
        root.connectionViewportModel.updateViewport(
            visible.x,
            visible.y,
            visible.x + visible.width,
            visible.y + visible.height
        )
    }

    function scheduleViewportUpdate() {
        // Keep the zoom tween inside QML; crossing into the Python proxy on
        // every scale frame causes an O(N) filter rebuild. Pan remains
        // coalesced to 60 Hz, while zoom gets one terminal flush.
        root._viewportUpdatePending = true
        if (viewport.zoomActive) {
            viewportUpdateTimer.stop()
            return
        }
        if (!viewportUpdateTimer.running) viewportUpdateTimer.start()
    }

    function openTagPickerForNode(nodeId, anchorItem) {
        globalTagPicker.openForNodeAt(nodeId, anchorItem)
    }

    function closeTagPicker() {
        globalTagPicker.close()
        mediaViewerPanel.closeTagPicker()
    }

    function syncModifiers(ctrlHeld, shiftHeld) {
        inputLayer.syncModifiers(ctrlHeld, shiftHeld)
    }

    function smoothCenterOn(targetX, targetY) {
        viewport.smoothCenterOnScreen(targetX, targetY, _availableScreenCenterX(), root.height / 2)
    }

    function saveEditor() {
        textEditorPanel.saveAndClose()
    }

    function cancelEditor() {
        textEditorPanel.cancelOrDelete()
    }

    function saveFrameEditor() {
        frameEditor.saveAndClose()
    }

    function cancelFrameEditor() {
        frameEditor.close()
    }

    function closeNodeProperties() {
        nodeProperties.closeOverlay()
    }

    function cancelMediaRename() {
        mediaViewerPanel.cancelRename()
    }

    function commitPendingMediaEdits() {
        return mediaViewerPanel.commitPendingEdits()
    }

    function clearPendingMediaEditorOpen() {
        root._pendingMediaEditorAction = ""
        root._pendingMediaEditorNodeId = 0
    }

    function beginArrayListHandoff() {
        root._arrayListHandoffActive = true
    }

    function finishArrayListHandoff() {
        Qt.callLater(function() {
            root._arrayListHandoffActive = false
        })
    }

    function promptDescriptionGuard(action) {
        if (action === "application-close")
            root.clearPendingMediaEditorOpen()
        return mediaViewerPanel.promptDescriptionGuard(action)
    }

    function collapseOrCloseMediaViewer() {
        mediaViewerPanel.collapseOrClose()
    }

    function closeMediaViewer() {
        mediaViewerPanel.requestCloseGuarded()
    }

    function openSearchPanel() {
        root.forceActiveFocus()
        searchPanel.openPanel()
    }

    function closeSearchPanel() {
        searchPanel.closePanel()
    }

    function setKeyboardPanKey(keyName, pressed) {
        viewport.setKeyboardPanKey(keyName, pressed)
    }

    function stopKeyboardPan() {
        viewport.stopKeyboardPan()
    }

    function suppressNextMousePress() {
        inputLayer.suppressNextMousePress()
    }

    function cancelPointerGesture() {
        inputLayer.cancelPointerGesture()
    }

    function screenToCanvas(screenX, screenY) {
        return viewport.screenToCanvas(screenX, screenY)
    }

    function canvasToScreen(canvasX, canvasY) {
        return viewport.canvasToScreen(canvasX, canvasY)
    }

    function visibleCanvasRect(margin) {
        return viewport.visibleCanvasRect(margin)
    }

    function openEditorForNode(nodeId) {
        if (root.viewerController.active && !root.viewerController.detached) {
            if (!mediaViewerPanel.commitPendingEdits()) {
                if (root.viewerController.descriptionDirty) {
                    root.beginArrayListHandoff()
                    root._pendingMediaEditorAction = "text"
                    root._pendingMediaEditorNodeId = Number(nodeId)
                    mediaViewerPanel.promptDescriptionGuard("close")
                }
                return
            }
            root.beginArrayListHandoff()
            if (root._hasMediaReturn && !root._hasEditorReturn) {
                root._editorReturnX = root._mediaReturnX
                root._editorReturnY = root._mediaReturnY
                root._hasEditorReturn = true
            }
            root._suppressMediaCameraReturn = true
            root.viewerController.close_viewer()
            root._suppressMediaCameraReturn = false
        }
        if (!_hasEditorReturn) {
            _editorReturnX = contentLayer.x
            _editorReturnY = contentLayer.y
            _hasEditorReturn = true
        }
        textEditorPanel.openForNode(nodeId)
        root.finishArrayListHandoff()
    }

    function openFrameEditorForNode(nodeId) {
        if (root.viewerController.active && !root.viewerController.detached) {
            if (!mediaViewerPanel.commitPendingEdits()) {
                if (root.viewerController.descriptionDirty) {
                    root.beginArrayListHandoff()
                    root._pendingMediaEditorAction = "frame"
                    root._pendingMediaEditorNodeId = Number(nodeId)
                    mediaViewerPanel.promptDescriptionGuard("close")
                }
                return
            }
            root.beginArrayListHandoff()
            root.viewerController.close_viewer()
        }
        frameEditor.openForFrame(nodeId)
        root.finishArrayListHandoff()
    }

    function closeEditorsForMedia() {
        var closingSurface = textEditorPanel.open || frameEditor.visible
                             || nodeProperties.visible
        if (closingSurface)
            root.beginArrayListHandoff()
        if (textEditorPanel.open) {
            if (root._hasEditorReturn && !root._hasMediaReturn) {
                root._mediaReturnX = root._editorReturnX
                root._mediaReturnY = root._editorReturnY
                root._hasMediaReturn = true
            }
            root._suppressEditorCameraReturn = true
            textEditorPanel.cancelOrDelete()
            root._suppressEditorCameraReturn = false
        }
        if (frameEditor.visible)
            frameEditor.close()
        if (nodeProperties.visible)
            nodeProperties.closeOverlay()
    }

    function beginMediaViewer(nodeId) {
        var firstOpen = !root._hasMediaReturn
        if (firstOpen) {
            root._mediaReturnX = contentLayer.x
            root._mediaReturnY = contentLayer.y
            root._hasMediaReturn = true
            mediaViewerPanel.resetExpanded()
        }
        root.centerOnNodeForMedia(nodeId)
    }

    function centerOnNodeForEditor(nodeId) {
        var bounds = root.nodeModel.get_node_bounds(nodeId)
        if (!bounds || bounds.length < 4) {
            return
        }

        var targetX = bounds[0] + bounds[2] / 2
        var targetY = bounds[1] + bounds[3] / 2
        viewport.smoothCenterOnScreen(targetX, targetY, _availableScreenCenterX(), root.height / 2)
    }

    function centerOnNodeForMedia(nodeId) {
        if (mediaViewerPanel.expanded) return
        var bounds = root.nodeModel.get_node_bounds(nodeId)
        if (!bounds || bounds.length < 4) return
        var targetX = bounds[0] + bounds[2] / 2
        var targetY = bounds[1] + bounds[3] / 2
        viewport.smoothCenterOnScreen(
            targetX,
            targetY,
            _availableScreenCenterX(),
            root.height / 2
        )
    }

    function returnFromEditor() {
        if (!_hasEditorReturn) {
            return
        }
        if (root._suppressEditorCameraReturn) {
            root._hasEditorReturn = false
            return
        }
        viewport.smoothMoveTo(_editorReturnX, _editorReturnY)
        _hasEditorReturn = false
    }

    function returnFromMediaViewer() {
        if (!root._hasMediaReturn) return
        if (root._suppressMediaCameraReturn) {
            root._hasMediaReturn = false
            return
        }
        viewport.smoothMoveTo(root._mediaReturnX, root._mediaReturnY)
        root._hasMediaReturn = false
    }

    function centerOnNodeFromSearch(nodeId) {
        var bounds = root.nodeModel.get_node_bounds(nodeId)
        if (!bounds || bounds.length < 4) {
            return
        }

        root.nodeModel.set_selection([nodeId])

        var targetX = bounds[0] + bounds[2] / 2
        var targetY = bounds[1] + bounds[3] / 2
        _searchCameraOffsetActive = true
        viewport.smoothCenterOnScreen(targetX, targetY, _availableScreenCenterX(), root.height / 2)
    }

    function compensateSearchClose(panelWidth) {
        if (!_searchCameraOffsetActive || panelWidth <= 0) {
            return
        }
        _searchCameraOffsetActive = false
        viewport.smoothMoveTo(contentLayer.x - panelWidth / 2, contentLayer.y)
    }

    function _availableScreenCenterX() {
        var leftInset = searchPanel.open ? searchPanel.width : 0
        var rightInset = textEditorPanel.open
                         ? textEditorPanel.width
                         : root.isMediaViewerOpen && !mediaViewerPanel.expanded
                           ? mediaViewerPanel.width : 0
        var usableWidth = Math.max(160, root.width - leftInset - rightInset)
        return leftInset + usableWidth / 2
    }

    // Drag & Drop

    DropArea {
        anchors.fill: parent
        keys: ["text/uri-list"]

        onDropped: function(drop) {
            if (drop.hasUrls) {
                var canvasPoint = viewport.screenToCanvas(drop.x, drop.y)
                root.canvasController.handle_dropped_files(
                    drop.urls,
                    canvasPoint.x,
                    canvasPoint.y
                )
                drop.accept()
            }
        }
    }
}
