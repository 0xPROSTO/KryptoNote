import QtQuick


Item {
    id: delegateRoot
    x: model.nodeX
    y: model.nodeY
    width: model.nodeWidth
    height: model.nodeHeight
    z: model.nodeIsSelected ? 10 : 1
    visible: isInViewport || model.nodeIsDeleting

    property bool _isResizing: false
    property bool _resizeHovered: nodeLoader.item && nodeLoader.item.isResizeHovered !== undefined
                                  ? nodeLoader.item.isResizeHovered : false
    property real _viewportMargin: 320 / Math.max(root.contentScale, 0.12)
    property real _visibleLeft: (-root._contentLayerX / root.contentScale) - _viewportMargin
    property real _visibleTop: (-root._contentLayerY / root.contentScale) - _viewportMargin
    property real _visibleRight: ((root.width - root._contentLayerX) / root.contentScale) + _viewportMargin
    property real _visibleBottom: ((root.height - root._contentLayerY) / root.contentScale) + _viewportMargin
    property bool isInViewport: (x + width >= _visibleLeft
                                 && x <= _visibleRight
                                 && y + height >= _visibleTop
                                 && y <= _visibleBottom)

    Loader {
        id: nodeLoader
        anchors.fill: parent
        active: delegateRoot.isInViewport || model.nodeIsDeleting
        sourceComponent: model.nodeType === "text" ? textNodeComponent : mediaNodeComponent
    }

    Component {
        id: textNodeComponent
        TextNode {
            nodeId: model.nodeId
            nodeTitle: model.nodeTitle
            nodeContent: model.nodeContent
            isSelected: model.nodeIsSelected
            isHovered: model.nodeIsHovered
            titleSize: model.nodeTitleSize
            textSize: model.nodeTextSize
            nodeWidth: model.nodeWidth
            nodeHeight: model.nodeHeight
            canvasScale: root.contentScale
        }
    }

    Component {
        id: mediaNodeComponent
        MediaNode {
            nodeId: model.nodeId
            nodeTitle: model.nodeTitle
            mediaType: model.nodeMediaType
            metaSummary: model.nodeMetaSummary
            isSelected: model.nodeIsSelected
            isHovered: model.nodeIsHovered
            nodeWidth: model.nodeWidth
            nodeHeight: model.nodeHeight
        }
    }

    NodeDragController {
        anchors.fill: parent
        delegateItem: delegateRoot
        nodeId: model.nodeId
        nodeIsSelected: model.nodeIsSelected
        resizeHovered: delegateRoot._resizeHovered
        resizing: delegateRoot._isResizing
    }

    NodeSelectionMouseArea {
        anchors.fill: parent
        nodeId: model.nodeId
        nodeType: model.nodeType
        contextMenu: contextMenu
    }

    NodeContextMenu {
        id: contextMenu
    }

    NodeDeleteAnimation {
        anchors.fill: nodeLoader
        targetItem: delegateRoot
        nodeId: model.nodeId
        deleting: model.nodeIsDeleting || false
    }
}
