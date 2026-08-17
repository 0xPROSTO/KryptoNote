import QtQuick
import QtQuick.Controls


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
    property bool revealOnHover: true
    property real revealMargin: 8
    property real minimumNodeWidth: 100
    property real minimumNodeHeight: 50
    readonly property bool _isActive: resizeDrag.active
    property bool _previewPending: false
    property real _pendingWidth: 0
    property real _pendingHeight: 0

    function advanceResizeFrame() {
        if (!resizeDrag.active || !handle._previewPending) return
        handle._previewPending = false
        handle.nodeModel.preview_size(
            handle.nodeId, handle._pendingWidth, handle._pendingHeight
        )
    }

    Component.onDestruction: {
        if (handle.canvasRoot
                && handle.canvasRoot.activeNodeResizeController === handle) {
            handle.canvasRoot.activeNodeResizeController = null
        }
    }

    ToolButton {
        id: gripIcon
        width: 20
        height: 20
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        anchors.rightMargin: -1
        anchors.bottomMargin: -1
        padding: 0
        hoverEnabled: false
        focusPolicy: Qt.NoFocus
        display: AbstractButton.IconOnly
        opacity: handle.revealOnHover
                 ? (handle._isHovered || handle._isActive ? 0.95 : 0)
                 : (handle._isHovered ? 0.95 : 0.68)
        icon.source: "../assets/icons/resize.svg"
        icon.width: 18
        icon.height: 18
        icon.color: handle._isHovered || handle._isActive
                    ? handle.appTheme.accentMain
                    : handle.appTheme.resizeHandle
        background: Item {}
        Accessible.ignored: true

        Behavior on opacity {
            NumberAnimation { duration: 120; easing.type: Easing.OutCubic }
        }
    }

    HoverHandler {
        onHoveredChanged: handle._isHovered = hovered
        cursorShape: Qt.SizeFDiagCursor
        margin: handle.revealOnHover ? handle.revealMargin : 0
    }

    DragHandler {
        id: resizeDrag
        target: null
        dragThreshold: 0
        margin: handle.revealOnHover ? handle.revealMargin : 0
        grabPermissions: PointerHandler.CanTakeOverFromAnything
        property real _startWidth: 0
        property real _startHeight: 0
        property point _startContentPos: Qt.point(0, 0)

        onActiveChanged: {
            var delegateRoot = handle.delegateItem;
            if (delegateRoot) delegateRoot._isResizing = active;

            if (active) {
                _startWidth = delegateRoot ? delegateRoot.width : 0;
                _startHeight = delegateRoot ? delegateRoot.height : 0;
                handle._pendingWidth = _startWidth;
                handle._pendingHeight = _startHeight;
                handle._previewPending = false;
                _startContentPos = handle.mapToItem(
                    handle.contentLayer,
                    centroid.position.x,
                    centroid.position.y
                );
                handle.canvasRoot.activeNodeResizeController = handle;
            } else {
                handle._previewPending = false;
                try {
                    if (delegateRoot) {
                        handle.nodeModel.update_size(
                            handle.nodeId,
                            handle._pendingWidth,
                            handle._pendingHeight
                        );
                    }
                } finally {
                    if (handle.canvasRoot.activeNodeResizeController
                            === handle) {
                        handle.canvasRoot.activeNodeResizeController = null;
                    }
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
            var newW = Math.max(
                handle.minimumNodeWidth,
                _startWidth + currentContentPos.x - _startContentPos.x
            );
            var newH = Math.max(
                handle.minimumNodeHeight,
                _startHeight + currentContentPos.y - _startContentPos.y
            );

            if (handle.canvasRoot.snapToGrid) {
                newW = Math.max(
                    handle.minimumNodeWidth,
                    Math.round(newW / handle.canvasRoot.gridSize)
                        * handle.canvasRoot.gridSize
                );
                newH = Math.max(
                    handle.minimumNodeHeight,
                    Math.round(newH / handle.canvasRoot.gridSize)
                        * handle.canvasRoot.gridSize
                );
            }

            if (handle._pendingWidth !== newW
                    || handle._pendingHeight !== newH) {
                handle._pendingWidth = newW;
                handle._pendingHeight = newH;
                handle._previewPending = true;
            }
        }
    }
}
