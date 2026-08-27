import QtQuick
import QtQuick.Shapes

Item {
    id: connectionItem
    required property var model
    required property var canvasRoot
    required property var canvasController
    required property var appTheme
    z: showHighlight || _revealActive ? 1 : 0

    property bool revealRequested: false
    property bool _revealHandled: false
    property bool _componentReady: false
    property bool _revealActive: false
    signal revealAccepted(int connectionId)

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
    property real lodLineAmount: Math.max(
        0.0,
        Math.min(
            1.0,
            (0.45 - connectionItem.canvasRoot.visualDetailScale) / 0.25
        )
    )
    property real screenStrokeWidth: showHighlight || _revealActive
            ? connectionItem.appTheme.connectionHighlightWidth
            : (connectionItem.appTheme.connectionStrokeWidth - lodLineAmount * 0.2)
    property real effectiveStrokeWidth: screenStrokeWidth / Math.max(
        connectionItem.canvasRoot.visualDetailScale,
        0.12
    )
    property real endpointDistance: Math.sqrt(
        Math.pow(connectionItem.model.connEndEdgeX - connectionItem.model.connStartEdgeX, 2)
        + Math.pow(connectionItem.model.connEndEdgeY - connectionItem.model.connStartEdgeY, 2)
    )
    property real curveOverflow: connectionItem.appTheme.connectionStyle !== "curved"
            ? 0
            : (connectionItem.appTheme.connectionCurveFormula === "arc"
               ? Math.min(80, endpointDistance * 0.22)
               : (connectionItem.appTheme.connectionCurveFormula === "s_curve"
                  ? Math.min(64, endpointDistance * 0.18) : 0))
    property real maximumStrokeWidth: Math.max(
        connectionItem.appTheme.connectionStrokeWidth,
        connectionItem.appTheme.connectionHighlightWidth
    )
    property real renderPadding: curveOverflow
            + (maximumStrokeWidth / 2.0 + 2.0)
              / Math.max(connectionItem.canvasRoot.minimumScale, 0.01)
    // The viewport proxy already limits delegates. A scale-bound visibility
    // check here would dirty every remaining connection on every zoom frame.
    property var pathGeometry: buildPathGeometry()

    x: minX - renderPadding
    y: minY - renderPadding
    width: maxX - minX + renderPadding * 2
    height: Math.max(1, maxY - minY + renderPadding * 2)

    onIsDeletingChanged: {
        if (isDeleting) {
            revealAnimation.stop()
            _revealActive = false
            animateDeletion(connectionItem.model.connDeleteFinalizes)
        } else {
            deleteAnim.stop()
            _isDeleting = false
            opacity = 1.0
        }
    }

    onRevealRequestedChanged: {
        if (!revealRequested) return
        if (_componentReady) {
            startReveal()
        } else if (connectionItem.appTheme.colorMotionEnabled) {
            opacity = 0.0
        }
    }
    Component.onCompleted: {
        _componentReady = true
        if (revealRequested) startReveal()
    }

    Shape {
        anchors.fill: parent
        vendorExtensionsEnabled: true
        antialiasing: true
        // Use native hardware curve antialiasing without forcing global MSAA.
        preferredRendererType: Shape.CurveRenderer

        ShapePath {
            id: shapePath
            strokeColor: connectionItem._isDeleting
                         ? connectionItem.appTheme.dangerHover
                         : connectionItem._revealActive
                           ? connectionItem.appTheme.accentHigh
                           : connectionItem.isHighlighted
                             ? connectionItem.appTheme.accentMain
                             : connectionItem.curveHovered
                               ? connectionItem.appTheme.borderHover
                               : connectionItem.appTheme.borderDefault
            strokeWidth: connectionItem.effectiveStrokeWidth
            fillColor: "transparent"
            capStyle: ShapePath.RoundCap
            joinStyle: ShapePath.RoundJoin
            strokeStyle: connectionItem.appTheme.connectionPattern === "solid"
                         ? ShapePath.SolidLine : ShapePath.DashLine
            dashPattern: connectionItem.appTheme.connectionPattern === "dotted"
                         ? [1, 2.4] : [5, 3]

            Behavior on strokeColor {
                ColorAnimation { duration: connectionItem.appTheme.durationState }
            }

            PathSvg {
                path: connectionItem.pathGeometry.path
            }
        }
    }

    function buildPathGeometry() {
        var start = [
            connectionItem.model.connStartEdgeX - connectionItem.x,
            connectionItem.model.connStartEdgeY - connectionItem.y
        ];
        var end = [
            connectionItem.model.connEndEdgeX - connectionItem.x,
            connectionItem.model.connEndEdgeY - connectionItem.y
        ];
        var style = connectionItem.appTheme.connectionStyle;
        if (style === "straight") {
            return lineGeometry(start, end);
        }
        if (style === "orthogonal" || style === "angled") {
            return roundedPolylineGeometry(
                routePoints(style, start, end),
                cornerRadiusForStyle(
                    connectionItem.appTheme.connectionCornerStyle
                )
            );
        }
        return curvedGeometry(
            start,
            end,
            connectionItem.appTheme.connectionCurveFormula
        );
    }

    function lineGeometry(start, end) {
        return {
            path: "M " + start[0] + " " + start[1]
                  + " L " + end[0] + " " + end[1]
        };
    }

    function curvedGeometry(start, end, formula) {
        var dx = end[0] - start[0];
        var dy = end[1] - start[1];
        var length = pointDistance(start, end);
        if (formula === "arc") {
            if (length <= 0.001) return lineGeometry(start, end);
            var arcNormal = stableNormal(dx, dy, length);
            var arcBow = Math.min(80, length * 0.22);
            return quadraticGeometry(
                start,
                [
                    (start[0] + end[0]) / 2.0 + arcNormal[0] * arcBow,
                    (start[1] + end[1]) / 2.0 + arcNormal[1] * arcBow
                ],
                end
            );
        }

        var control1;
        var control2;
        if (formula === "s_curve" && length > 0.001) {
            var normal = stableNormal(dx, dy, length);
            var bow = Math.min(64, length * 0.18);
            control1 = [
                start[0] + dx / 3.0 + normal[0] * bow,
                start[1] + dy / 3.0 + normal[1] * bow
            ];
            control2 = [
                start[0] + dx * 2.0 / 3.0 - normal[0] * bow,
                start[1] + dy * 2.0 / 3.0 - normal[1] * bow
            ];
        } else if (formula === "adaptive" && Math.abs(dy) > Math.abs(dx)) {
            control1 = [start[0], start[1] + dy * 0.4];
            control2 = [end[0], end[1] - dy * 0.4];
        } else {
            control1 = [start[0] + dx * 0.4, start[1]];
            control2 = [end[0] - dx * 0.4, end[1]];
        }
        return {
            path: "M " + start[0] + " " + start[1]
                  + " C " + control1[0] + " " + control1[1]
                  + ", " + control2[0] + " " + control2[1]
                  + ", " + end[0] + " " + end[1]
        };
    }

    function quadraticGeometry(start, control, end) {
        return {
            path: "M " + start[0] + " " + start[1]
                  + " Q " + control[0] + " " + control[1]
                  + " " + end[0] + " " + end[1]
        };
    }

    function routePoints(style, start, end) {
        var dx = end[0] - start[0];
        var dy = end[1] - start[1];
        var horizontal = Math.abs(dx) >= Math.abs(dy);
        if (style === "orthogonal") {
            if (horizontal) {
                var middleX = (start[0] + end[0]) / 2.0;
                return compactPoints([
                    start, [middleX, start[1]], [middleX, end[1]], end
                ]);
            }
            var middleY = (start[1] + end[1]) / 2.0;
            return compactPoints([
                start, [start[0], middleY], [end[0], middleY], end
            ]);
        }

        if (horizontal) {
            var directionX = dx >= 0 ? 1 : -1;
            var leadX = Math.min(
                Math.abs(dx) / 3.0, 48
            );
            return compactPoints([
                start,
                [start[0] + directionX * leadX, start[1]],
                [end[0] - directionX * leadX, end[1]],
                end
            ]);
        }
        var directionY = dy >= 0 ? 1 : -1;
        var leadY = Math.min(
            Math.abs(dy) / 3.0, 48
        );
        return compactPoints([
            start,
            [start[0], start[1] + directionY * leadY],
            [end[0], end[1] - directionY * leadY],
            end
        ]);
    }

    function roundedPolylineGeometry(points, requestedRadius) {
        if (points.length < 2) {
            return { path: "" };
        }
        var radius = Math.max(0, Math.min(64, requestedRadius));
        var path = "M " + points[0][0] + " " + points[0][1];
        for (var index = 1; index < points.length - 1; index++) {
            var previous = points[index - 1];
            var corner = points[index];
            var following = points[index + 1];
            var localRadius = Math.min(
                radius,
                pointDistance(previous, corner) / 2.0,
                pointDistance(corner, following) / 2.0
            );
            if (localRadius <= 0.001) {
                path += " L " + corner[0] + " " + corner[1];
                continue;
            }
            var entry = pointToward(corner, previous, localRadius);
            var exitPoint = pointToward(corner, following, localRadius);
            path += " L " + entry[0] + " " + entry[1];

            path += " Q " + corner[0] + " " + corner[1]
                    + " " + exitPoint[0] + " " + exitPoint[1];
        }
        var end = points[points.length - 1];
        path += " L " + end[0] + " " + end[1];
        return { path: path };
    }

    function compactPoints(points) {
        var compact = [];
        for (var index = 0; index < points.length; index++) {
            if (!compact.length
                    || pointDistance(compact[compact.length - 1], points[index])
                       > 0.001) {
                compact.push(points[index]);
            }
        }
        return compact;
    }

    function pointToward(origin, target, distance) {
        var length = pointDistance(origin, target);
        if (length <= 0.001) return origin;
        var amount = distance / length;
        return [
            origin[0] + (target[0] - origin[0]) * amount,
            origin[1] + (target[1] - origin[1]) * amount
        ];
    }

    function pointDistance(first, second) {
        var dx = second[0] - first[0];
        var dy = second[1] - first[1];
        return Math.sqrt(dx * dx + dy * dy);
    }

    function stableNormal(dx, dy, length) {
        var normalX = -dy / length;
        var normalY = dx / length;
        if (normalY < -0.001
                || (Math.abs(normalY) <= 0.001 && normalX < 0)) {
            normalX = -normalX;
            normalY = -normalY;
        }
        return [normalX, normalY];
    }

    function cornerRadiusForStyle(style) {
        if (style === "sharp") return 0;
        if (style === "tight") return 8;
        return 24;
    }

    function animateDeletion(finalizeAfterAnimation) {
        if (_isDeleting) return;
        _deleteFinalizes = finalizeAfterAnimation;
        _isDeleting = true;
        deleteAnim.start();
    }

    function startReveal() {
        if (!revealRequested || _revealHandled || _isDeleting) return;
        _revealHandled = true;
        revealAccepted(connectionItem.model.connId);
        revealAnimation.stop();
        if (!connectionItem.appTheme.colorMotionEnabled) {
            opacity = 1.0;
            _revealActive = false;
            return;
        }
        _revealActive = true;
        opacity = 0.0;
        revealAnimation.start();
    }

    NumberAnimation {
        id: revealAnimation
        target: connectionItem
        property: "opacity"
        from: 0.0
        to: 1.0
        duration: connectionItem.appTheme.durationPanel
        easing.type: Easing.OutQuad
        onFinished: connectionItem._revealActive = false
    }

    SequentialAnimation {
        id: deleteAnim
        NumberAnimation {
            target: connectionItem
            property: "opacity"
            to: 0.0
            duration: connectionItem.appTheme.durationPanel
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
