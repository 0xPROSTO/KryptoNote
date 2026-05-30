import QtQuick

Rectangle {
    id: root
    color: AppTheme ? AppTheme.bgCanvas : "#1a1a2e"
    clip: true
    focus: true

    property alias contentScale: viewport.contentScale
    property real gridSize: 100.0
    property real gridMain: 500.0
    property bool snapToGrid: canvasController ? canvasController.snap_to_grid : false

    property alias isLinkMode: inputLayer.isLinkMode
    property alias isEraserMode: inputLayer.isEraserMode
    property alias isCtrlHeld: inputLayer.isCtrlHeld
    property alias isShiftHeld: inputLayer.isShiftHeld
    property alias isPanning: inputLayer.isPanning
    property alias isEditorResizing: textEditorPanel.resizing
    property alias isSearchResizing: searchPanel.resizing
    property bool isTextEditorOpen: textEditorPanel.open
    property bool isSearchPanelOpen: searchPanel.open
    property int hoveredConnectionId: 0

    signal textEditorOpenChanged(bool open)

    property alias _contentLayerX: contentLayer.x
    property alias _contentLayerY: contentLayer.y
    property real _editorReturnX: 0
    property real _editorReturnY: 0
    property bool _hasEditorReturn: false
    property bool _searchCameraOffsetActive: false

    Component.onCompleted: viewport.initialize()
    onWidthChanged: viewport.ensureInitialized()
    onHeightChanged: viewport.ensureInitialized()
    onIsTextEditorOpenChanged: textEditorOpenChanged(isTextEditorOpen)

    GridLayer {
        anchors.fill: parent
        contentLayer: contentLayer
        contentScale: root.contentScale
        gridSize: root.gridSize
        gridMain: root.gridMain
    }

    Item {
        id: contentLayer
        z: 1
        x: 0
        y: 0
        transformOrigin: Item.TopLeft
        scale: root.contentScale

        ConnectionLayer {
            anchors.fill: parent
        }

        NodeLayer {
            anchors.fill: parent
        }
    }

    RubberBandSelection {
        id: rubberBand
        z: 2
    }

    CanvasViewport {
        id: viewport
        anchors.fill: parent
        contentLayer: contentLayer
        onZoomChanged: function(scale) {
            if (canvasController) {
                canvasController.report_zoom(scale)
            }
        }
    }

    CanvasInputLayer {
        id: inputLayer
        anchors.fill: parent
        focus: true
        contentLayer: contentLayer
        viewport: viewport
        rubberBand: rubberBand
        contentScale: root.contentScale
        gridSize: root.gridSize
        snapToGrid: root.snapToGrid
    }

    SearchPanel {
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
            canvasController.set_status_message(message, message === "Ready" ? "normal" : "accent")
        }
    }

    TextEditorPanel {
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
    }

    Connections {
        target: canvasController
        function onOpenTextEditorRequested(nodeId) {
            root.openEditorForNode(nodeId)
        }
    }

    HoverHandler {
        id: globalHover
        onHoveredChanged: {
            if (!hovered) {
                root.hoveredConnectionId = 0
            }
        }
        onPointChanged: {
            if (!point) return
            var contentPos = root.mapToItem(contentLayer, point.position.x, point.position.y)
            root.hoveredConnectionId = connectionModel.hit_test_connection(
                contentPos.x,
                contentPos.y,
                10 / Math.max(root.contentScale, 0.12)
            )
            if (!coordThrottleTimer.running) {
                canvasController.report_mouse_position(contentPos.x, contentPos.y)
                coordThrottleTimer.start()
            }
        }
    }

    Timer {
        id: coordThrottleTimer
        interval: 32
        repeat: false
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

    function openEditorForNode(nodeId) {
        if (!_hasEditorReturn) {
            _editorReturnX = contentLayer.x
            _editorReturnY = contentLayer.y
            _hasEditorReturn = true
        }
        textEditorPanel.openForNode(nodeId)
    }

    function centerOnNodeForEditor(nodeId) {
        var bounds = nodeModel.get_node_bounds(nodeId)
        if (!bounds || bounds.length < 4) {
            return
        }

        var targetX = bounds[0] + bounds[2] / 2
        var targetY = bounds[1] + bounds[3] / 2
        viewport.smoothCenterOnScreen(targetX, targetY, _availableScreenCenterX(), root.height / 2)
    }

    function returnFromEditor() {
        if (!_hasEditorReturn) {
            return
        }
        viewport.smoothMoveTo(_editorReturnX, _editorReturnY)
        _hasEditorReturn = false
    }

    function centerOnNodeFromSearch(nodeId) {
        var bounds = nodeModel.get_node_bounds(nodeId)
        if (!bounds || bounds.length < 4) {
            return
        }

        nodeModel.clear_selection()
        nodeModel.set_selected(nodeId, true)

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
        var rightInset = textEditorPanel.open ? textEditorPanel.width : 0
        var usableWidth = Math.max(160, root.width - leftInset - rightInset)
        return leftInset + usableWidth / 2
    }

    // Drag & Drop

    DropArea {
        anchors.fill: parent
        keys: ["text/uri-list"]

        onDropped: function(drop) {
            if (drop.hasUrls) {
                var canvasX = (drop.x - contentLayer.x) / viewport.contentScale
                var canvasY = (drop.y - contentLayer.y) / viewport.contentScale
                canvasController.handle_dropped_files(drop.urls, canvasX, canvasY)
                drop.accept()
            }
        }
    }
}
