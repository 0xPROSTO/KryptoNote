import QtQuick

Item {
    id: viewport
    property Item contentLayer
    property real contentScale: 1.0
    property real minScale: 0.1
    property real maxScale: 5.0
    property real zoomFactor: 1.20
    property real velocityX: 0
    property real velocityY: 0
    property real keyboardVelocityX: 0
    property real keyboardVelocityY: 0
    property real keyboardMaxSpeed: 2400
    property real keyboardAcceleration: 16000
    property real keyboardBrake: 24000
    property real keyboardTurnAcceleration: 36000
    property bool keyboardPanLeft: false
    property bool keyboardPanRight: false
    property bool keyboardPanUp: false
    property bool keyboardPanDown: false

    property real _zoomAnchorX: 0
    property real _zoomAnchorY: 0
    property real _zoomMouseX: 0
    property real _zoomMouseY: 0

    signal zoomChanged(real scale)

    function initialize() {
        if (!contentLayer) return
        contentLayer.x = width / 2
        contentLayer.y = height / 2
    }

    function ensureInitialized() {
        if (!contentLayer) return
        if (contentLayer.x === 0) contentLayer.x = width / 2
        if (contentLayer.y === 0) contentLayer.y = height / 2
    }

    function stopMotion() {
        inertiaTimer.stop()
        keyboardPanTimer.stop()
        keyboardPanLeft = false
        keyboardPanRight = false
        keyboardPanUp = false
        keyboardPanDown = false
        velocityX = 0
        velocityY = 0
        keyboardVelocityX = 0
        keyboardVelocityY = 0
        panXAnimation.stop()
        panYAnimation.stop()
    }

    function panBy(dx, dy) {
        if (!contentLayer) return
        contentLayer.x += dx
        contentLayer.y += dy
        velocityX = velocityX * 0.4 + dx * 1.85
        velocityY = velocityY * 0.4 + dy * 1.85
    }

    function startInertiaIfNeeded() {
        if (Math.abs(velocityX) + Math.abs(velocityY) > 2) {
            inertiaTimer.start()
        }
    }

    function zoomAt(mouseX, mouseY, zoomIn) {
        if (!contentLayer) return
        var factor = zoomIn ? zoomFactor : (1.0 / zoomFactor)
        var newScale = Math.max(minScale, Math.min(maxScale, contentScale * factor))
        _zoomAnchorX = (mouseX - contentLayer.x) / contentScale
        _zoomAnchorY = (mouseY - contentLayer.y) / contentScale
        _zoomMouseX = mouseX
        _zoomMouseY = mouseY
        zoomAnimation.stop()
        zoomAnimation.from = contentScale
        zoomAnimation.to = newScale
        zoomAnimation.start()
    }

    function smoothCenterOn(targetX, targetY) {
        smoothCenterOnScreen(targetX, targetY, width / 2, height / 2)
    }

    function smoothCenterOnScreen(targetX, targetY, screenCenterX, screenCenterY) {
        stopMotion()
        panXAnimation.from = contentLayer.x
        panYAnimation.from = contentLayer.y
        panXAnimation.to = screenCenterX - targetX * contentScale
        panYAnimation.to = screenCenterY - targetY * contentScale
        panXAnimation.start()
        panYAnimation.start()
    }

    function smoothMoveTo(layerX, layerY) {
        stopMotion()
        panXAnimation.from = contentLayer.x
        panYAnimation.from = contentLayer.y
        panXAnimation.to = layerX
        panYAnimation.to = layerY
        panXAnimation.start()
        panYAnimation.start()
    }

    function setKeyboardPanKey(keyName, pressed) {
        if (keyName === "left") {
            keyboardPanLeft = pressed
        } else if (keyName === "right") {
            keyboardPanRight = pressed
        } else if (keyName === "up") {
            keyboardPanUp = pressed
        } else if (keyName === "down") {
            keyboardPanDown = pressed
        }

        if (pressed) {
            inertiaTimer.stop()
            panXAnimation.stop()
            panYAnimation.stop()
            if (!keyboardPanTimer.running) {
                keyboardPanTimer.start()
            }
        } else if (!_hasKeyboardPanInput()
                   && Math.abs(keyboardVelocityX) + Math.abs(keyboardVelocityY) < 0.5) {
            keyboardPanTimer.stop()
        }
    }

    function stopKeyboardPan() {
        keyboardPanLeft = false
        keyboardPanRight = false
        keyboardPanUp = false
        keyboardPanDown = false
    }

    function _hasKeyboardPanInput() {
        return keyboardPanLeft || keyboardPanRight || keyboardPanUp || keyboardPanDown
    }

    function _approach(current, target, delta) {
        if (current < target) {
            return Math.min(target, current + delta)
        }
        if (current > target) {
            return Math.max(target, current - delta)
        }
        return target
    }

    function _keyboardDelta(current, target, hasInput, dt) {
        if (!hasInput) {
            return keyboardBrake * dt
        }
        if ((current > 0 && target < 0) || (current < 0 && target > 0)) {
            return keyboardTurnAcceleration * dt
        }
        return keyboardAcceleration * dt
    }

    function _keyboardAxis(negativePressed, positivePressed) {
        return (positivePressed ? 1 : 0) - (negativePressed ? 1 : 0)
    }

    Timer {
        id: inertiaTimer
        interval: 16
        repeat: true
        onTriggered: {
            viewport.velocityX *= 0.82
            viewport.velocityY *= 0.82
            if (Math.abs(viewport.velocityX) + Math.abs(viewport.velocityY) < 1.0) {
                inertiaTimer.stop()
                return
            }
            viewport.contentLayer.x += viewport.velocityX
            viewport.contentLayer.y += viewport.velocityY
        }
    }

    Timer {
        id: keyboardPanTimer
        interval: 16
        repeat: true
        onTriggered: {
            if (!viewport.contentLayer) return

            var dt = interval / 1000.0
            var axisX = viewport._keyboardAxis(
                viewport.keyboardPanRight,
                viewport.keyboardPanLeft
            )
            var axisY = viewport._keyboardAxis(
                viewport.keyboardPanDown,
                viewport.keyboardPanUp
            )
            var length = Math.sqrt(axisX * axisX + axisY * axisY)
            if (length > 0) {
                axisX /= length
                axisY /= length
            }

            var targetX = axisX * viewport.keyboardMaxSpeed
            var targetY = axisY * viewport.keyboardMaxSpeed
            var hasInput = length > 0
            viewport.keyboardVelocityX = viewport._approach(
                viewport.keyboardVelocityX,
                targetX,
                viewport._keyboardDelta(viewport.keyboardVelocityX, targetX, hasInput, dt)
            )
            viewport.keyboardVelocityY = viewport._approach(
                viewport.keyboardVelocityY,
                targetY,
                viewport._keyboardDelta(viewport.keyboardVelocityY, targetY, hasInput, dt)
            )

            if (length === 0
                    && Math.abs(viewport.keyboardVelocityX) + Math.abs(viewport.keyboardVelocityY) < 0.5) {
                viewport.keyboardVelocityX = 0
                viewport.keyboardVelocityY = 0
                keyboardPanTimer.stop()
                return
            }

            viewport.contentLayer.x += viewport.keyboardVelocityX * dt
            viewport.contentLayer.y += viewport.keyboardVelocityY * dt
        }
    }

    WheelHandler {
        acceptedModifiers: Qt.ControlModifier
        onWheel: function(event) {
            var mouseX = event.x !== undefined ? event.x : viewport.width / 2
            var mouseY = event.y !== undefined ? event.y : viewport.height / 2
            viewport.zoomAt(mouseX, mouseY, event.angleDelta.y > 0)
        }
    }

    NumberAnimation {
        id: zoomAnimation
        target: viewport
        property: "contentScale"
        duration: 120
        easing.type: Easing.OutQuad
    }

    onContentScaleChanged: {
        if (!contentLayer) return
        contentLayer.x = _zoomMouseX - _zoomAnchorX * contentScale
        contentLayer.y = _zoomMouseY - _zoomAnchorY * contentScale
        zoomChanged(contentScale)
    }

    NumberAnimation {
        id: panXAnimation
        target: viewport.contentLayer
        property: "x"
        duration: 200
        easing.type: Easing.OutCubic
    }

    NumberAnimation {
        id: panYAnimation
        target: viewport.contentLayer
        property: "y"
        duration: 200
        easing.type: Easing.OutCubic
    }
}
