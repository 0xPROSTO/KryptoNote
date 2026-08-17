pragma ComponentBehavior: Bound

import QtQuick


Item {
    id: delegateRoot
    required property var model
    required property var canvasRoot
    required property var nodeModel
    required property var canvasController
    required property var viewerController
    required property Item contentLayer
    required property var appTheme
    required property bool renderFrames
    signal contextMenuRequested(int nodeId, string nodeType, var sourceItem, real localX, real localY)
    x: delegateRoot.model.nodeX
    y: delegateRoot.model.nodeY
    width: delegateRoot.model.nodeWidth
    height: delegateRoot.model.nodeHeight
    z: delegateRoot.visuallySelected ? 10 : 1
    visible: matchesLayer
             && (isInViewport || delegateRoot.model.nodeIsDeleting)

    property bool _isResizing: false
    property bool _resizeHovered: nodeLoader.itemResizeHovered
    readonly property bool visuallySelected:
            delegateRoot.canvasRoot.propertiesFocusNodeId > 0
            ? delegateRoot.model.nodeId
                === delegateRoot.canvasRoot.propertiesFocusNodeId
            : delegateRoot.model.nodeIsSelected
    property bool matchesLayer: delegateRoot.renderFrames
                                ? delegateRoot.model.nodeType === "frame"
                                : delegateRoot.model.nodeType !== "frame"
    property real _viewportMargin: 320 / Math.max(delegateRoot.canvasRoot.contentScale, 0.12)
    property var _visibleRect: delegateRoot.canvasRoot.visibleCanvasRect(_viewportMargin)
    property real _visibleLeft: _visibleRect.x
    property real _visibleTop: _visibleRect.y
    property real _visibleRight: _visibleRect.x + _visibleRect.width
    property real _visibleBottom: _visibleRect.y + _visibleRect.height
    property bool isInViewport: (x + width >= _visibleLeft
                                 && x <= _visibleRight
                                 && y + height >= _visibleTop
                                 && y <= _visibleBottom)

    Loader {
        id: nodeLoader
        z: delegateRoot.model.nodeType === "frame"
           ? 2 : (delegateRoot.model.nodeType === "audio" ? 4 : 0)
        property bool itemResizeHovered: false
        onItemChanged: itemResizeHovered = false
        x: 0
        y: delegateRoot.model.nodeType === "frame" ? -15 : 0
        width: parent.width
        height: parent.height
                + (delegateRoot.model.nodeType === "frame" ? 15 : 0)
        active: delegateRoot.matchesLayer
                && (delegateRoot.isInViewport
                    || delegateRoot.model.nodeIsDeleting)
        sourceComponent: delegateRoot.model.nodeType === "frame"
                         ? frameNodeComponent
                         : (delegateRoot.model.nodeType === "text"
                            ? textNodeComponent
                            : (delegateRoot.model.nodeType === "audio"
                               ? audioNodeComponent : mediaNodeComponent))
    }

    Component {
        id: frameNodeComponent
        FrameNode {
            canvasRoot: delegateRoot.canvasRoot
            nodeModel: delegateRoot.nodeModel
            canvasController: delegateRoot.canvasController
            dragController: nodeDragController
            contentLayer: delegateRoot.contentLayer
            appTheme: delegateRoot.appTheme
            delegateItem: delegateRoot
            nodeId: delegateRoot.model.nodeId
            frameTitle: delegateRoot.model.nodeTitle
            frameLocked: delegateRoot.model.nodeFrameLocked
            frameColor: delegateRoot.model.nodeFrameColor
            frameOpacity: delegateRoot.model.nodeFrameOpacity
            tags: delegateRoot.model.nodeTags
            isSelected: delegateRoot.visuallySelected
            isHovered: delegateRoot.model.nodeIsHovered
            resizing: delegateRoot._isResizing
            onIsResizeHoveredChanged: nodeLoader.itemResizeHovered = isResizeHovered
            onContextMenuRequested: function(
                nodeId, nodeType, sourceItem, localX, localY
            ) {
                delegateRoot.contextMenuRequested(
                    nodeId, nodeType, sourceItem, localX, localY
                )
            }
        }
    }

    Component {
        id: textNodeComponent
        TextNode {
            canvasRoot: delegateRoot.canvasRoot
            nodeModel: delegateRoot.nodeModel
            contentLayer: delegateRoot.contentLayer
            appTheme: delegateRoot.appTheme
            delegateItem: delegateRoot
            nodeId: delegateRoot.model.nodeId
            nodeTitle: delegateRoot.model.nodeTitle
            nodeContent: delegateRoot.model.nodeContent
            isSelected: delegateRoot.visuallySelected
            isHovered: delegateRoot.model.nodeIsHovered
            titleSize: delegateRoot.model.nodeTitleSize
            textSize: delegateRoot.model.nodeTextSize
            nodeWidth: delegateRoot.model.nodeWidth
            nodeHeight: delegateRoot.model.nodeHeight
            canvasScale: delegateRoot.canvasRoot.contentScale
            tags: delegateRoot.model.nodeTags
            onIsResizeHoveredChanged: nodeLoader.itemResizeHovered = isResizeHovered
        }
    }

    Component {
        id: audioNodeComponent
        AudioNode {
            canvasRoot: delegateRoot.canvasRoot
            nodeModel: delegateRoot.nodeModel
            contentLayer: delegateRoot.contentLayer
            appTheme: delegateRoot.appTheme
            delegateItem: delegateRoot
            viewerController: delegateRoot.viewerController
            nodeId: delegateRoot.model.nodeId
            nodeTitle: delegateRoot.model.nodeTitle
            nodeContent: delegateRoot.model.nodeContent
            textSize: delegateRoot.model.nodeTextSize
            mediaType: delegateRoot.model.nodeMediaType
            metaSummary: delegateRoot.model.nodeMetaSummary
            audioWaveform: delegateRoot.model.audioWaveform
            mediaDuration: delegateRoot.model.nodeMediaDuration
            isSelected: delegateRoot.visuallySelected
            isHovered: delegateRoot.model.nodeIsHovered
            nodeWidth: delegateRoot.model.nodeWidth
            nodeHeight: delegateRoot.model.nodeHeight
            tags: delegateRoot.model.nodeTags
            onIsResizeHoveredChanged: nodeLoader.itemResizeHovered = isResizeHovered
        }
    }

    Component {
        id: mediaNodeComponent
        MediaNode {
            canvasRoot: delegateRoot.canvasRoot
            nodeModel: delegateRoot.nodeModel
            contentLayer: delegateRoot.contentLayer
            appTheme: delegateRoot.appTheme
            delegateItem: delegateRoot
            nodeId: delegateRoot.model.nodeId
            nodeTitle: delegateRoot.model.nodeTitle
            nodeContent: delegateRoot.model.nodeContent
            textSize: delegateRoot.model.nodeTextSize
            mediaType: delegateRoot.model.nodeMediaType
            metaSummary: delegateRoot.model.nodeMetaSummary
            isSelected: delegateRoot.visuallySelected
            isHovered: delegateRoot.model.nodeIsHovered
            nodeWidth: delegateRoot.model.nodeWidth
            nodeHeight: delegateRoot.model.nodeHeight
            tags: delegateRoot.model.nodeTags
            onIsResizeHoveredChanged: nodeLoader.itemResizeHovered = isResizeHovered
        }
    }

    NodeDragController {
        id: nodeDragController
        z: 1
        canvasRoot: delegateRoot.canvasRoot
        nodeModel: delegateRoot.nodeModel
        contentLayer: delegateRoot.contentLayer
        anchors.fill: parent
        delegateItem: delegateRoot
        nodeId: delegateRoot.model.nodeId
        nodeType: delegateRoot.model.nodeType
        nodeIsSelected: delegateRoot.model.nodeIsSelected
        resizeHovered: delegateRoot._resizeHovered
        resizing: delegateRoot._isResizing
    }

    NodeSelectionMouseArea {
        id: nodeSelection
        z: 2
        visible: delegateRoot.model.nodeType !== "frame"
        enabled: nodeSelection.visible
        canvasRoot: delegateRoot.canvasRoot
        nodeModel: delegateRoot.nodeModel
        canvasController: delegateRoot.canvasController
        anchors.fill: parent
        nodeId: delegateRoot.model.nodeId
        nodeType: delegateRoot.model.nodeType
        bottomRightExclusion: 24
        onContextMenuRequested: function(nodeId, nodeType, sourceItem, localX, localY) {
            delegateRoot.contextMenuRequested(nodeId, nodeType, sourceItem, localX, localY)
        }
    }

    FrameSelectionLayer {
        id: frameSelectionLayer
        z: 0
        visible: delegateRoot.model.nodeType === "frame"
        enabled: frameSelectionLayer.visible
        anchors.fill: parent
        canvasRoot: delegateRoot.canvasRoot
        nodeModel: delegateRoot.nodeModel
        canvasController: delegateRoot.canvasController
        nodeId: delegateRoot.model.nodeId
        onContextMenuRequested: function(nodeId, nodeType, sourceItem, localX, localY) {
            delegateRoot.contextMenuRequested(nodeId, nodeType, sourceItem, localX, localY)
        }
    }

    NodeDeleteAnimation {
        // Audio controls sit above the generic selection layer.  Keep the
        // delete transition above every node surface as well.
        z: 5
        canvasController: delegateRoot.canvasController
        anchors.fill: nodeLoader
        targetItem: delegateRoot
        nodeId: delegateRoot.model.nodeId
        deleting: delegateRoot.model.nodeIsDeleting || false
    }
}
