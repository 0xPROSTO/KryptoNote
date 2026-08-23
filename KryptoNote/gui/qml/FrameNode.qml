import QtQuick
import QtQuick.Controls


Item {
    id: frame
    required property var canvasRoot
    required property var nodeModel
    required property var canvasController
    required property var dragController
    required property Item contentLayer
    required property var appTheme
    required property Item delegateItem

    property int nodeId: 0
    property string frameTitle: ""
    property bool frameLocked: false
    property string frameColor: ""
    property real frameOpacity: 0.21
    property var tags: []
    property bool isSelected: false
    property bool isHovered: false
    property bool resizing: false
    property bool topOverlayHoverActive: false
    property point topOverlayHoverPosition: Qt.point(-1, -1)
    signal contextMenuRequested(
        int nodeId,
        string nodeType,
        var sourceItem,
        real localX,
        real localY
    )

    readonly property color outlineColor: frame.isSelected
            ? frame.appTheme.accentMain
            : (frame.isHovered || titleHover.hovered || frame.lockHovered
               ? frame.appTheme.borderHover
               : frame.appTheme.borderDefault)
    readonly property bool lockHovered:
            lockButton.hovered
            || (frame.topOverlayHoverActive
                && frame.topOverlayHoverPosition.x
                   >= titleBlob.x + lockButton.x
                && frame.topOverlayHoverPosition.x
                   <= titleBlob.x + lockButton.x + lockButton.width
                && frame.topOverlayHoverPosition.y
                   >= titleBlob.y + lockButton.y
                && frame.topOverlayHoverPosition.y
                   <= titleBlob.y + lockButton.y + lockButton.height)
    readonly property real surfaceTopInset: 15
    readonly property real topResizeExclusionWidth:
            titleBlob.width
            + 8 / Math.max(frame.canvasRoot.visualDetailScale, 0.25)
    readonly property real topResizeExclusionHeight: Math.max(
        0,
        titleBlob.y + titleBlob.height - frame.surfaceTopInset
    )

    Item {
        id: frameSurface
        x: 0
        y: frame.surfaceTopInset
        width: parent.width
        height: Math.max(0, parent.height - frame.surfaceTopInset)
    }

    Rectangle {
        anchors.fill: frameSurface
        radius: 8
        color: frame.frameColor.length > 0
               ? frame.frameColor
               : frame.appTheme.bgPanel
        opacity: Math.max(0, Math.min(1, frame.frameOpacity))

        Behavior on opacity {
            NumberAnimation { duration: 120; easing.type: Easing.OutCubic }
        }
    }

    Rectangle {
        anchors.fill: frameSurface
        radius: 8
        color: "transparent"
        border.width: frame.isSelected ? 1.8 : 1.15
        border.color: frame.outlineColor

        Behavior on border.color { ColorAnimation { duration: 120 } }
    }

    Rectangle {
        id: titleBlob
        z: 4
        anchors.horizontalCenter: frameSurface.horizontalCenter
        y: frameSurface.y - height / 2 + 1
        width: Math.max(
            88,
            Math.min(frame.width - 24, titleLabel.implicitWidth + 72)
        )
        height: 30
        radius: height / 2
        color: frame.appTheme.bgNode
        border.width: frame.isSelected ? 1.5 : 1
        border.color: frame.outlineColor

        Behavior on border.color { ColorAnimation { duration: 120 } }

        NodeSelectionMouseArea {
            anchors.fill: parent
            canvasRoot: frame.canvasRoot
            nodeModel: frame.nodeModel
            canvasController: frame.canvasController
            nodeId: frame.nodeId
            nodeType: "frame"
            onContextMenuRequested: function(
                nodeId, nodeType, sourceItem, localX, localY
            ) {
                frame.contextMenuRequested(
                    nodeId, nodeType, sourceItem, localX, localY
                )
            }
        }

        HoverHandler {
            id: titleHover
            cursorShape: Qt.SizeAllCursor
        }

        DragHandler {
            id: titleDrag
            target: null
            acceptedButtons: Qt.LeftButton
            dragThreshold: 1
            grabPermissions: PointerHandler.CanTakeOverFromAnything
            enabled: frame.dragController
                     && frame.dragController.canDrag
            onActiveChanged: {
                if (active) frame.dragController.beginDrag()
                else frame.dragController.handleDragActiveChanged(titleDrag)
            }
            onCanceled: frame.dragController.cancelDrag()
            onTranslationChanged: {
                if (active) frame.dragController.updateDrag(titleDrag)
            }
        }

        ToolButton {
            id: lockButton
            z: 2
            anchors.left: parent.left
            anchors.leftMargin: (parent.height - height) / 2
            anchors.verticalCenter: parent.verticalCenter
            width: 24
            height: 24
            hoverEnabled: true
            focusPolicy: Qt.NoFocus
            display: AbstractButton.IconOnly
            icon.source: frame.frameLocked
                         ? "../assets/icons/lock.svg"
                         : "../assets/icons/unlock.svg"
            icon.width: 14
            icon.height: 14
            icon.color: frame.frameLocked
                        ? frame.appTheme.textMain
                        : frame.appTheme.textMuted
            scale: down ? 0.97 : 1.0
            Behavior on scale {
                NumberAnimation {
                    duration: frame.appTheme.motionEnabled ? 80 : 0
                    easing.type: Easing.OutCubic
                }
            }
            background: Rectangle {
                radius: 12
                color: frame.lockHovered
                       ? frame.appTheme.bgControlHover
                       : "transparent"
            }
            onClicked: frame.canvasController.toggle_frame_locked(frame.nodeId)

            Accessible.role: Accessible.Button
            Accessible.name: frame.frameLocked ? "Unlock frame" : "Lock frame"
            ThemedToolTip {
                appTheme: frame.appTheme
                visible: frame.lockHovered
                delay: 450
                text: frame.frameLocked
                      ? "Locked · moves contained nodes"
                      : "Unlocked · moves independently"
            }
        }

        Text {
            id: titleLabel
            z: 1
            anchors.left: parent.left
            anchors.leftMargin: 34
            anchors.right: parent.right
            anchors.rightMargin: 34
            anchors.verticalCenter: parent.verticalCenter
            horizontalAlignment: Text.AlignHCenter
            text: frame.frameTitle.trim().length > 0
                  ? frame.frameTitle
                  : "Untitled Frame"
            color: frame.appTheme.textMain
            font.family: "Segoe UI"
            font.pointSize: 10
            font.weight: Font.DemiBold
            elide: Text.ElideRight
        }
    }

    TagDots {
        id: frameTagSummary
        z: 3
        appTheme: frame.appTheme
        tags: frame.tags
        width: Math.min(280, Math.max(0, frameSurface.width - 56))
        anchors.left: frameSurface.left
        anchors.leftMargin: 28
        anchors.bottom: frameSurface.bottom
        anchors.bottomMargin: -height / 2 + 1
    }

}
