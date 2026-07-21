pragma ComponentBehavior: Bound

import QtQuick


Item {
    id: delegateRoot
    required property var model
    required property var canvasRoot
    required property var nodeModel
    required property var canvasController
    required property Item contentLayer
    required property var appTheme
    signal contextMenuRequested(int nodeId, string nodeType, var sourceItem, real localX, real localY)
    x: delegateRoot.model.nodeX
    y: delegateRoot.model.nodeY
    width: delegateRoot.model.nodeWidth
    height: delegateRoot.model.nodeHeight
    z: delegateRoot.model.nodeIsSelected ? 10 : 1
    visible: isInViewport || delegateRoot.model.nodeIsDeleting

    property bool _isResizing: false
    property bool _resizeHovered: nodeLoader.itemResizeHovered
    property real _viewportMargin: 320 / Math.max(delegateRoot.canvasRoot.contentScale, 0.12)
    property real _visibleLeft: (-delegateRoot.canvasRoot._contentLayerX / delegateRoot.canvasRoot.contentScale) - _viewportMargin
    property real _visibleTop: (-delegateRoot.canvasRoot._contentLayerY / delegateRoot.canvasRoot.contentScale) - _viewportMargin
    property real _visibleRight: ((delegateRoot.canvasRoot.width - delegateRoot.canvasRoot._contentLayerX) / delegateRoot.canvasRoot.contentScale) + _viewportMargin
    property real _visibleBottom: ((delegateRoot.canvasRoot.height - delegateRoot.canvasRoot._contentLayerY) / delegateRoot.canvasRoot.contentScale) + _viewportMargin
    property bool isInViewport: (x + width >= _visibleLeft
                                 && x <= _visibleRight
                                 && y + height >= _visibleTop
                                 && y <= _visibleBottom)

    Loader {
        id: nodeLoader
        property bool itemResizeHovered: false
        onItemChanged: itemResizeHovered = false
        anchors.fill: parent
        active: delegateRoot.isInViewport || delegateRoot.model.nodeIsDeleting
        sourceComponent: delegateRoot.model.nodeType === "text" ? textNodeComponent : mediaNodeComponent
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
            isSelected: delegateRoot.model.nodeIsSelected
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
        id: mediaNodeComponent
        MediaNode {
            canvasRoot: delegateRoot.canvasRoot
            nodeModel: delegateRoot.nodeModel
            contentLayer: delegateRoot.contentLayer
            appTheme: delegateRoot.appTheme
            delegateItem: delegateRoot
            nodeId: delegateRoot.model.nodeId
            nodeTitle: delegateRoot.model.nodeTitle
            mediaType: delegateRoot.model.nodeMediaType
            metaSummary: delegateRoot.model.nodeMetaSummary
            isSelected: delegateRoot.model.nodeIsSelected
            isHovered: delegateRoot.model.nodeIsHovered
            nodeWidth: delegateRoot.model.nodeWidth
            nodeHeight: delegateRoot.model.nodeHeight
            tags: delegateRoot.model.nodeTags
            onIsResizeHoveredChanged: nodeLoader.itemResizeHovered = isResizeHovered
        }
    }

    NodeDragController {
        canvasRoot: delegateRoot.canvasRoot
        nodeModel: delegateRoot.nodeModel
        contentLayer: delegateRoot.contentLayer
        anchors.fill: parent
        delegateItem: delegateRoot
        nodeId: delegateRoot.model.nodeId
        nodeIsSelected: delegateRoot.model.nodeIsSelected
        resizeHovered: delegateRoot._resizeHovered
        resizing: delegateRoot._isResizing
    }

    NodeSelectionMouseArea {
        canvasRoot: delegateRoot.canvasRoot
        nodeModel: delegateRoot.nodeModel
        canvasController: delegateRoot.canvasController
        anchors.fill: parent
        nodeId: delegateRoot.model.nodeId
        nodeType: delegateRoot.model.nodeType
        onContextMenuRequested: function(nodeId, nodeType, sourceItem, localX, localY) {
            delegateRoot.contextMenuRequested(nodeId, nodeType, sourceItem, localX, localY)
        }
    }

    NodeDeleteAnimation {
        canvasController: delegateRoot.canvasController
        anchors.fill: nodeLoader
        targetItem: delegateRoot
        nodeId: delegateRoot.model.nodeId
        deleting: delegateRoot.model.nodeIsDeleting || false
    }
}
