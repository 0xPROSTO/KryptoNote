import QtQuick
import QtQuick.Shapes
import QtQuick.Controls

Item {
    id: connectionItem
    z: showHighlight ? 1 : 0

    property real minX: Math.min(model.connStartEdgeX, model.connEndEdgeX)
    property real minY: Math.min(model.connStartEdgeY, model.connEndEdgeY)
    property real maxX: Math.max(model.connStartEdgeX, model.connEndEdgeX)
    property real maxY: Math.max(model.connStartEdgeY, model.connEndEdgeY)

    property bool isHighlighted: model.connIsHighlighted
    property bool isDeleting: model.connIsDeleting || false
    property bool curveHovered: root.hoveredConnectionId === model.connId
    property bool showHighlight: isHighlighted || curveHovered
    property bool _isDeleting: false
    property bool _deleteFinalizes: true
    property real _viewportMargin: 360 / Math.max(root.contentScale, 0.12)
    property real _visibleLeft: (-root._contentLayerX / root.contentScale) - _viewportMargin
    property real _visibleTop: (-root._contentLayerY / root.contentScale) - _viewportMargin
    property real _visibleRight: ((root.width - root._contentLayerX) / root.contentScale) + _viewportMargin
    property real _visibleBottom: ((root.height - root._contentLayerY) / root.contentScale) + _viewportMargin
    property bool isInViewport: (maxX >= _visibleLeft
                                 && minX <= _visibleRight
                                 && maxY >= _visibleTop
                                 && minY <= _visibleBottom)
    property real lodLineAmount: Math.max(0.0, Math.min(1.0, (0.45 - root.contentScale) / 0.25))
    property real screenStrokeWidth: showHighlight ? 2.1 : (1.5 - lodLineAmount * 0.2)
    property real effectiveStrokeWidth: screenStrokeWidth / Math.max(root.contentScale, 0.12)
    property real hitRadius: Math.max(10.0 / Math.max(root.contentScale, 0.12), effectiveStrokeWidth * 2.0)
    property real hitPadding: hitRadius + 8.0
    visible: isInViewport || _isDeleting

    x: minX - hitPadding
    y: minY - hitPadding
    width: maxX - minX + hitPadding * 2
    height: Math.max(1, maxY - minY + hitPadding * 2)

    onIsDeletingChanged: {
        if (isDeleting) {
            animateDeletion(model.connDeleteFinalizes)
        }
    }

    Shape {
        anchors.fill: parent
        vendorExtensionsEnabled: true
        antialiasing: true

        ShapePath {
            id: shapePath
            strokeColor: connectionItem._isDeleting ? "#8c8c8c" :
                         (connectionItem.showHighlight ? AppTheme.accentMain : AppTheme.borderDefault)
            strokeWidth: connectionItem.effectiveStrokeWidth
            fillColor: "transparent"
            capStyle: ShapePath.RoundCap

            Behavior on strokeColor { ColorAnimation { duration: 120 } }
            Behavior on strokeWidth { NumberAnimation { duration: 120 } }

            startX: model.connStartEdgeX - connectionItem.x
            startY: model.connStartEdgeY - connectionItem.y

            PathCubic {
                id: bezierPath
                x: model.connEndEdgeX - connectionItem.x
                y: model.connEndEdgeY - connectionItem.y

                property real dx: x - shapePath.startX
                property real dy: y - shapePath.startY

                control1X: shapePath.startX + dx * 0.4
                control1Y: shapePath.startY
                control2X: x - dx * 0.4
                control2Y: y
            }
        }
    }

    MouseArea {
        id: connectionHover
        anchors.fill: parent
        hoverEnabled: false
        acceptedButtons: Qt.RightButton
        enabled: connectionItem.visible

        onPressed: function(mouse) {
            if (!checkDistance(mouse.x, mouse.y)) {
                mouse.accepted = false;
                return;
            }
        }

        onClicked: function(mouse) {
            if (!checkDistance(mouse.x, mouse.y)) {
                mouse.accepted = false;
                return;
            }
            if (mouse.button === Qt.RightButton) {
                connectionContextMenu.connId = model.connId;
                connectionContextMenu.x = mouse.x;
                connectionContextMenu.y = mouse.y;
                connectionContextMenu.popup();
            }
        }
    }

    function checkDistance(px, py) {
        var p0x = shapePath.startX;
        var p0y = shapePath.startY;
        var p1x = bezierPath.control1X;
        var p1y = bezierPath.control1Y;
        var p2x = bezierPath.control2X;
        var p2y = bezierPath.control2Y;
        var p3x = bezierPath.x;
        var p3y = bezierPath.y;

        var minDSq = 1000000;
        var steps = 80;
        var prevX = p0x;
        var prevY = p0y;
        for (var i = 1; i <= steps; i++) {
            var t = i / steps;
            var mt = 1.0 - t;
            var b0 = mt * mt * mt;
            var b1 = 3 * mt * mt * t;
            var b2 = 3 * mt * t * t;
            var b3 = t * t * t;

            var x = b0*p0x + b1*p1x + b2*p2x + b3*p3x;
            var y = b0*p0y + b1*p1y + b2*p2y + b3*p3y;

            var dsq = distanceToSegmentSquared(px, py, prevX, prevY, x, y);
            if (dsq < minDSq) minDSq = dsq;
            prevX = x;
            prevY = y;
        }
        return minDSq <= connectionItem.hitRadius * connectionItem.hitRadius;
    }

    function distanceToSegmentSquared(px, py, x1, y1, x2, y2) {
        var dx = x2 - x1;
        var dy = y2 - y1;
        var lengthSq = dx * dx + dy * dy;
        if (lengthSq <= 0.0001) {
            return (px - x1) * (px - x1) + (py - y1) * (py - y1);
        }
        var t = ((px - x1) * dx + (py - y1) * dy) / lengthSq;
        t = Math.max(0.0, Math.min(1.0, t));
        var cx = x1 + t * dx;
        var cy = y1 + t * dy;
        return (px - cx) * (px - cx) + (py - cy) * (py - cy);
    }

    function requestDeletion() {
        if (_isDeleting) return;
        canvasController.delete_connection(model.connId);
    }

    function animateDeletion(finalizeAfterAnimation) {
        if (_isDeleting) return;
        _deleteFinalizes = finalizeAfterAnimation;
        _isDeleting = true;
        deleteAnim.start();
    }

    SequentialAnimation {
        id: deleteAnim
        NumberAnimation {
            target: connectionItem
            property: "opacity"
            from: 1.0; to: 0.0
            duration: 240
        }
        ScriptAction {
            script: {
                if (connectionItem._deleteFinalizes) {
                    canvasController.perform_delete_connection(model.connId)
                }
            }
        }
    }

    Popup {
        id: connectionContextMenu
        width: 140
        padding: 4
        modal: true
        closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside
        opacity: 0.0
        property int connId: 0
        enter: Transition {
            NumberAnimation { property: "opacity"; from: 0.0; to: 1.0; duration: 140; easing.type: Easing.OutQuad }
        }
        exit: Transition {
            NumberAnimation { property: "opacity"; from: 1.0; to: 0.0; duration: 120; easing.type: Easing.OutQuad }
        }
        Overlay.modal: Rectangle {
            color: "#1a000000"
            opacity: connectionContextMenu.opened ? 1.0 : 0.0
            Behavior on opacity { NumberAnimation { duration: 140; easing.type: Easing.OutQuad } }
        }
        background: Rectangle {
            color: "#333333"
            radius: 4
            border.color: "#444444"
            border.width: 1
        }
        contentItem: Rectangle {
            width: 132
            height: 28
            color: removeMouseArea.containsMouse ? "#444444" : "transparent"
            radius: 3
            Text {
                anchors.verticalCenter: parent.verticalCenter
                x: 10
                text: "Remove Link"
                color: "#ffffff"
                font.family: "Segoe UI"
                font.pointSize: 9
            }
            MouseArea {
                id: removeMouseArea
                anchors.fill: parent
                hoverEnabled: true
                onClicked: {
                    connectionItem.requestDeletion();
                    connectionContextMenu.close();
                }
            }
        }
    }
}
