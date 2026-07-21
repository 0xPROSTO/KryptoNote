import QtQuick


Item {
    id: handle
    required property var canvasRoot
    required property var nodeModel
    required property Item contentLayer
    required property var appTheme
    width: 24
    height: 24

    required property int nodeId
    required property Item delegateItem
    property bool _isHovered: false

    Canvas {
        id: gripCanvas
        width: 14
        height: 14
        anchors.right: parent.right
        anchors.bottom: parent.bottom
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
            ctx.fillStyle = handle._isHovered ? handle.appTheme.accentMain : handle.appTheme.resizeHandle;
            ctx.fill();
        }
    }

    HoverHandler {
        onHoveredChanged: {
            handle._isHovered = hovered;
            gripCanvas.requestPaint();
        }
        cursorShape: Qt.SizeFDiagCursor
    }

    DragHandler {
        id: resizeDrag
        target: null
        dragThreshold: 0
        property real _startWidth: 0
        property real _startHeight: 0
        property point _startContentPos: Qt.point(0, 0)

        onActiveChanged: {
            var delegateRoot = handle.delegateItem;
            if (delegateRoot) delegateRoot._isResizing = active;

            if (active) {
                _startWidth = delegateRoot ? delegateRoot.width : 0;
                _startHeight = delegateRoot ? delegateRoot.height : 0;
                _startContentPos = handle.mapToItem(
                    handle.contentLayer,
                    centroid.position.x,
                    centroid.position.y
                );
            } else {
                // Commit only on release; live resize uses preview_size.
                if (delegateRoot) {
                    var finalW = delegateRoot.width;
                    var finalH = delegateRoot.height;
                    if (handle.canvasRoot.snapToGrid) {
                        finalW = Math.round(finalW / handle.canvasRoot.gridSize) * handle.canvasRoot.gridSize;
                        finalH = Math.round(finalH / handle.canvasRoot.gridSize) * handle.canvasRoot.gridSize;
                    }
                    handle.nodeModel.update_size(handle.nodeId, finalW, finalH);
                }
            }
        }

        onTranslationChanged: {
            var delegateRoot = handle.delegateItem;
            if (!delegateRoot) return;

            var currentContentPos = handle.mapToItem(
                handle.contentLayer,
                centroid.position.x,
                centroid.position.y
            );
            var newW = Math.max(100, _startWidth + currentContentPos.x - _startContentPos.x);
            var newH = Math.max(50, _startHeight + currentContentPos.y - _startContentPos.y);

            if (handle.canvasRoot.snapToGrid) {
                newW = Math.round(newW / handle.canvasRoot.gridSize) * handle.canvasRoot.gridSize;
                newH = Math.round(newH / handle.canvasRoot.gridSize) * handle.canvasRoot.gridSize;
            }

            if (delegateRoot.width !== newW || delegateRoot.height !== newH) {
                handle.nodeModel.preview_size(handle.nodeId, newW, newH);
            }
        }
    }
}
