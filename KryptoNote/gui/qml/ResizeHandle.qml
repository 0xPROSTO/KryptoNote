import QtQuick


Item {
    id: handle
    width: 14
    height: 14

    property int nodeId: 0
    property bool _isHovered: false

    Canvas {
        anchors.fill: parent
        onPaint: {
            var ctx = getContext("2d");
            ctx.reset();
            ctx.beginPath();
            var w = width;
            var h = height;
            var pad = 2;
            ctx.moveTo(w - pad, pad);
            ctx.lineTo(w - pad, h - pad);
            ctx.lineTo(pad, h - pad);
            ctx.closePath();
            ctx.fillStyle = handle._isHovered ? AppTheme.accentMain : AppTheme.textMuted;
            ctx.fill();
        }
    }

    HoverHandler {
        onHoveredChanged: {
            handle._isHovered = hovered;
            handle.children[0].requestPaint();
        }
        cursorShape: Qt.SizeFDiagCursor
    }

    DragHandler {
        id: resizeDrag
        target: null
        property real _startWidth: 0
        property real _startHeight: 0
        property point _startContentPos: Qt.point(0, 0)

        onActiveChanged: {
            // handle -> TextNode/MediaNode -> nodeLoader -> delegateRoot
            var delegateRoot = handle.parent.parent.parent;
            if (delegateRoot) delegateRoot._isResizing = active;

            if (active) {
                _startWidth = delegateRoot ? delegateRoot.width : 0;
                _startHeight = delegateRoot ? delegateRoot.height : 0;
                _startContentPos = handle.mapToItem(
                    contentLayer,
                    centroid.position.x,
                    centroid.position.y
                );
            } else {
                // Commit only on release; live resize uses preview_size.
                var parentNode = handle.parent;
                if (parentNode) {
                    var finalW = parentNode.parent.width;
                    var finalH = parentNode.parent.height;
                    if (root.snapToGrid) {
                        finalW = Math.round(finalW / root.gridSize) * root.gridSize;
                        finalH = Math.round(finalH / root.gridSize) * root.gridSize;
                    }
                    nodeModel.update_size(handle.nodeId, finalW, finalH);
                }
            }
        }

        onTranslationChanged: {
            var delegateRoot = handle.parent.parent.parent;
            if (!delegateRoot) return;

            var currentContentPos = handle.mapToItem(
                contentLayer,
                centroid.position.x,
                centroid.position.y
            );
            var newW = Math.max(100, _startWidth + currentContentPos.x - _startContentPos.x);
            var newH = Math.max(50, _startHeight + currentContentPos.y - _startContentPos.y);

            if (root.snapToGrid) {
                newW = Math.round(newW / root.gridSize) * root.gridSize;
                newH = Math.round(newH / root.gridSize) * root.gridSize;
            }

            if (delegateRoot.width !== newW || delegateRoot.height !== newH) {
                nodeModel.preview_size(handle.nodeId, newW, newH);
            }
        }
    }

    Timer {
        id: resizeThrottle
        interval: 16
        repeat: false
    }
}
