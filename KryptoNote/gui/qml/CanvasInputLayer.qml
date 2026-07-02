import QtQuick

Item {
    id: input
    property Item contentLayer
    property var viewport
    property var rubberBand
    property real contentScale: 1.0
    property real gridSize: 100.0
    property bool snapToGrid: false
    property bool isLinkMode: false
    property bool isEraserMode: false
    property bool isCtrlHeld: false
    property bool isShiftHeld: false
    property bool isPanning: false
    property bool suppressingNextPress: false
    property bool suppressingMouseSequence: false

    MouseArea {
        id: canvasMouseArea
        anchors.fill: parent
        acceptedButtons: Qt.LeftButton | Qt.RightButton | Qt.MiddleButton
        hoverEnabled: true
        z: -10
        propagateComposedEvents: true

        property point lastPos: Qt.point(0, 0)
        property point pressPos: Qt.point(0, 0)
        property bool dragging: false

        onPressed: function(mouse) {
            if (input.suppressingNextPress) {
                input.suppressingNextPress = false
                input.cancelPointerGesture()
                input.suppressingMouseSequence = true
                mouse.accepted = true
                return
            }

            viewport.stopMotion()
            lastPos = Qt.point(mouse.x, mouse.y)
            pressPos = Qt.point(mouse.x, mouse.y)

            if (mouse.button === Qt.RightButton && input.isShiftHeld) {
                input.isEraserMode = true
                cursorShape = Qt.ForbiddenCursor
                mouse.accepted = true
                return
            }

            if (mouse.button === Qt.LeftButton && input.isCtrlHeld) {
                rubberBand.begin(mouse.x, mouse.y)
                mouse.accepted = true
                return
            }

            if (mouse.button === Qt.LeftButton || mouse.button === Qt.MiddleButton) {
                input.isPanning = true
                dragging = true
                cursorShape = Qt.ClosedHandCursor
                mouse.accepted = true
            }
        }

        onPositionChanged: function(mouse) {
            if (input.suppressingMouseSequence) {
                mouse.accepted = true
                return
            }

            var contentPos = mapToItem(contentLayer, mouse.x, mouse.y)
            mouse.accepted = false

            if (input.isEraserMode) {
                var segments = connectionModel.get_connection_hit_segments()
                for (var i = 0; i < segments.length; i++) {
                    var s = segments[i]
                    var minX = Math.min(s.x1, s.x2) - 24
                    var maxX = Math.max(s.x1, s.x2) + 24
                    var minY = Math.min(s.y1, s.y2) - 24
                    var maxY = Math.max(s.y1, s.y2) + 24
                    if (contentPos.x < minX || contentPos.x > maxX
                            || contentPos.y < minY || contentPos.y > maxY) {
                        continue
                    }
                    if (_checkBezierHit(contentPos.x, contentPos.y, s.x1, s.y1, s.x2, s.y2)) {
                        canvasController.delete_connection(s.id)
                    }
                }
                return
            }

            if (rubberBand.visible) {
                rubberBand.updateBand(mouse.x, mouse.y)
                return
            }

            if (dragging) {
                viewport.panBy(mouse.x - lastPos.x, mouse.y - lastPos.y)
                lastPos = Qt.point(mouse.x, mouse.y)
            }
        }

        onReleased: function(mouse) {
            if (input.suppressingMouseSequence) {
                input.suppressingMouseSequence = false
                input.cancelPointerGesture()
                mouse.accepted = true
                return
            }

            if (input.isEraserMode) {
                input.isEraserMode = false
                cursorShape = Qt.ArrowCursor
                return
            }

            if (rubberBand.visible) {
                rubberBand.finishSelection(contentLayer, contentScale)
                return
            }

            if (dragging) {
                dragging = false
                input.isPanning = false
                cursorShape = Qt.ArrowCursor
                viewport.startInertiaIfNeeded()
            }

            if (Math.abs(mouse.x - pressPos.x) < 3 && Math.abs(mouse.y - pressPos.y) < 3) {
                if (mouse.button === Qt.LeftButton && !input.isShiftHeld) {
                    nodeModel.clear_selection()
                    nodeModel.clear_hovered()
                }
            }
        }
    }

    Keys.onPressed: function(event) {
        handleKeyPressed(event)
    }

    Keys.onReleased: function(event) {
        handleKeyReleased(event)
    }

    function suppressNextMousePress() {
        cancelPointerGesture()
        suppressingNextPress = true
    }

    function cancelPointerGesture() {
        suppressingNextPress = false
        suppressingMouseSequence = false
        canvasMouseArea.dragging = false
        isPanning = false
        isEraserMode = false
        if (rubberBand && rubberBand.visible) {
            rubberBand.visible = false
        }
        canvasMouseArea.cursorShape = Qt.ArrowCursor
        if (viewport) {
            viewport.stopMotion()
        }
    }

    function handleKeyPressed(event) {
        if (event.key === Qt.Key_Control) {
            input.isCtrlHeld = true
        } else if (event.key === Qt.Key_Shift) {
            input.isShiftHeld = true
            input.isLinkMode = true
        }
    }

    function handleKeyReleased(event) {
        if (event.key === Qt.Key_Control) {
            input.isCtrlHeld = false
        } else if (event.key === Qt.Key_Shift) {
            input.isShiftHeld = false
            input.isLinkMode = false
            canvasController.toggle_link_mode_off()
        }
    }

    function resetModifiers() {
        isCtrlHeld = false
        isShiftHeld = false
        isLinkMode = false
        canvasController.toggle_link_mode_off()
    }

    function syncModifiers(ctrlHeld, shiftHeld) {
        isCtrlHeld = ctrlHeld
        isShiftHeld = shiftHeld
        isLinkMode = shiftHeld
        if (!shiftHeld) {
            canvasController.toggle_link_mode_off()
        }
    }

    function _checkBezierHit(px, py, p0x, p0y, p3x, p3y) {
        var dx = p3x - p0x
        var p1x = p0x + dx * 0.4
        var p1y = p0y
        var p2x = p3x - dx * 0.4
        var p2y = p3y
        var minDSq = 1000000
        var prevX = p0x
        var prevY = p0y
        var steps = 80
        for (var i = 1; i <= steps; i++) {
            var t = i / steps
            var mt = 1.0 - t
            var b0 = mt * mt * mt
            var b1 = 3 * mt * mt * t
            var b2 = 3 * mt * t * t
            var b3 = t * t * t
            var x = b0*p0x + b1*p1x + b2*p2x + b3*p3x
            var y = b0*p0y + b1*p1y + b2*p2y + b3*p3y
            var dsq = _distanceToSegmentSquared(px, py, prevX, prevY, x, y)
            if (dsq < minDSq) minDSq = dsq
            prevX = x
            prevY = y
        }
        return minDSq < 100
    }

    function _distanceToSegmentSquared(px, py, x1, y1, x2, y2) {
        var sx = x2 - x1
        var sy = y2 - y1
        var lengthSq = sx * sx + sy * sy
        if (lengthSq <= 0.0001) {
            return (px - x1) * (px - x1) + (py - y1) * (py - y1)
        }
        var t = ((px - x1) * sx + (py - y1) * sy) / lengthSq
        t = Math.max(0.0, Math.min(1.0, t))
        var cx = x1 + t * sx
        var cy = y1 + t * sy
        return (px - cx) * (px - cx) + (py - cy) * (py - cy)
    }
}
