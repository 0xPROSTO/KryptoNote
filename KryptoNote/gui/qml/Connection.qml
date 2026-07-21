import QtQuick
import QtQuick.Shapes

Item {
    id: connectionItem
    required property var model
    required property var canvasRoot
    required property var canvasController
    required property var appTheme
    signal contextMenuRequested(int connId, var sourceItem, real localX, real localY)
    z: showHighlight ? 1 : 0

    property real minX: Math.min(connectionItem.model.connStartEdgeX, connectionItem.model.connEndEdgeX)
    property real minY: Math.min(connectionItem.model.connStartEdgeY, connectionItem.model.connEndEdgeY)
    property real maxX: Math.max(connectionItem.model.connStartEdgeX, connectionItem.model.connEndEdgeX)
    property real maxY: Math.max(connectionItem.model.connStartEdgeY, connectionItem.model.connEndEdgeY)

    property bool isHighlighted: connectionItem.model.connIsHighlighted
    property bool isDeleting: connectionItem.model.connIsDeleting || false
    property bool curveHovered: connectionItem.canvasRoot.hoveredConnectionId === connectionItem.model.connId
    property bool showHighlight: isHighlighted || curveHovered
    property bool _isDeleting: false
    property bool _deleteFinalizes: true
    property real _viewportMargin: 360 / Math.max(connectionItem.canvasRoot.contentScale, 0.12)
    property real _visibleLeft: (-connectionItem.canvasRoot._contentLayerX / connectionItem.canvasRoot.contentScale) - _viewportMargin
    property real _visibleTop: (-connectionItem.canvasRoot._contentLayerY / connectionItem.canvasRoot.contentScale) - _viewportMargin
    property real _visibleRight: ((connectionItem.canvasRoot.width - connectionItem.canvasRoot._contentLayerX) / connectionItem.canvasRoot.contentScale) + _viewportMargin
    property real _visibleBottom: ((connectionItem.canvasRoot.height - connectionItem.canvasRoot._contentLayerY) / connectionItem.canvasRoot.contentScale) + _viewportMargin
    property bool isInViewport: (maxX >= _visibleLeft
                                 && minX <= _visibleRight
                                 && maxY >= _visibleTop
                                 && minY <= _visibleBottom)
    property real lodLineAmount: Math.max(0.0, Math.min(1.0, (0.45 - connectionItem.canvasRoot.contentScale) / 0.25))
    property real screenStrokeWidth: showHighlight
            ? connectionItem.appTheme.connectionHighlightWidth
            : (connectionItem.appTheme.connectionStrokeWidth - lodLineAmount * 0.2)
    property real effectiveStrokeWidth: screenStrokeWidth / Math.max(connectionItem.canvasRoot.contentScale, 0.12)
    property real hitRadius: Math.max(10.0 / Math.max(connectionItem.canvasRoot.contentScale, 0.12), effectiveStrokeWidth * 2.0)
    property real hitPadding: hitRadius + 8.0
    visible: isInViewport || _isDeleting

    x: minX - hitPadding
    y: minY - hitPadding
    width: maxX - minX + hitPadding * 2
    height: Math.max(1, maxY - minY + hitPadding * 2)

    onIsDeletingChanged: {
        if (isDeleting) {
            animateDeletion(connectionItem.model.connDeleteFinalizes)
        } else {
            deleteAnim.stop()
            _isDeleting = false
            opacity = 1.0
        }
    }

    Shape {
        anchors.fill: parent
        vendorExtensionsEnabled: true
        antialiasing: true

        ShapePath {
            id: shapePath
            strokeColor: connectionItem._isDeleting ? connectionItem.appTheme.textMuted :
                         (connectionItem.showHighlight ? connectionItem.appTheme.accentMain : connectionItem.appTheme.borderDefault)
            strokeWidth: connectionItem.effectiveStrokeWidth
            fillColor: "transparent"
            capStyle: ShapePath.RoundCap

            Behavior on strokeColor { ColorAnimation { duration: 120 } }
            Behavior on strokeWidth { NumberAnimation { duration: 120 } }

            startX: connectionItem.model.connStartEdgeX - connectionItem.x
            startY: connectionItem.model.connStartEdgeY - connectionItem.y

            PathCubic {
                id: bezierPath
                x: connectionItem.model.connEndEdgeX - connectionItem.x
                y: connectionItem.model.connEndEdgeY - connectionItem.y

                property real dx: x - shapePath.startX
                property real dy: y - shapePath.startY

                control1X: connectionItem.appTheme.connectionCurved
                        ? shapePath.startX + dx * 0.4
                        : shapePath.startX + dx / 3.0
                control1Y: connectionItem.appTheme.connectionCurved
                        ? shapePath.startY
                        : shapePath.startY + dy / 3.0
                control2X: connectionItem.appTheme.connectionCurved
                        ? x - dx * 0.4
                        : shapePath.startX + dx * 2.0 / 3.0
                control2Y: connectionItem.appTheme.connectionCurved
                        ? y
                        : shapePath.startY + dy * 2.0 / 3.0
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
            if (!connectionItem.checkDistance(mouse.x, mouse.y)) {
                mouse.accepted = false;
                return;
            }
        }

        onClicked: function(mouse) {
            if (!connectionItem.checkDistance(mouse.x, mouse.y)) {
                mouse.accepted = false;
                return;
            }
            if (mouse.button === Qt.RightButton) {
                connectionItem.contextMenuRequested(connectionItem.model.connId, connectionHover, mouse.x, mouse.y)
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


    function animateDeletion(finalizeAfterAnimation) {
        if (_isDeleting) return;
        _deleteFinalizes = finalizeAfterAnimation;
        opacity = 1.0;
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
                    connectionItem.canvasController.perform_delete_connection(connectionItem.model.connId)
                }
            }
        }
    }

}
