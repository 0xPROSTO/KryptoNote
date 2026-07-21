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
    readonly property real referenceFrameTime: 1.0 / 60.0
    readonly property real inertiaDecayPerReferenceFrame: 0.82
    property bool keyboardPanLeft: false
    property bool keyboardPanRight: false
    property bool keyboardPanUp: false
    property bool keyboardPanDown: false

    property bool _inertiaRunning: false
    property bool _keyboardPanRunning: false
    property bool _zoomRunning: false
    property bool _panRunning: false
    property bool _initialized: false
    property real _lastViewportWidth: 0.0
    property real _lastViewportHeight: 0.0
    readonly property bool frameClockNeeded: _inertiaRunning
            || _keyboardPanRunning || _zoomRunning || _panRunning

    property real _zoomAnchorX: 0
    property real _zoomAnchorY: 0
    property real _zoomMouseX: 0
    property real _zoomMouseY: 0
    property real _zoomFrom: 1.0
    property real _zoomTo: 1.0
    property real _zoomElapsed: 0.0
    readonly property real zoomDuration: 0.12

    property real _panFromX: 0.0
    property real _panFromY: 0.0
    property real _panToX: 0.0
    property real _panToY: 0.0
    property real _panElapsed: 0.0
    readonly property real panDuration: 0.20

    signal zoomChanged(real scale)
    signal viewportCenterShifted(real deltaX, real deltaY)

    function initialize() {
        if (!contentLayer) return
        if (!_initialized) {
            contentLayer.x = width / 2
            contentLayer.y = height / 2
            _initialized = true
        }
        _lastViewportWidth = width
        _lastViewportHeight = height
    }

    function ensureInitialized() {
        if (!_initialized) initialize()
    }

    function preserveCenterOnResize() {
        if (!_initialized || !contentLayer) {
            _lastViewportWidth = width
            _lastViewportHeight = height
            return
        }

        var deltaX = (width - _lastViewportWidth) / 2
        var deltaY = (height - _lastViewportHeight) / 2
        _lastViewportWidth = width
        _lastViewportHeight = height
        if (Math.abs(deltaX) + Math.abs(deltaY) <= 0.0001) return

        contentLayer.x += deltaX
        contentLayer.y += deltaY

        // Keep in-flight camera motion in the resized viewport's coordinate
        // system, otherwise the next animation frame would undo this shift.
        if (_panRunning) {
            _panFromX += deltaX
            _panFromY += deltaY
            _panToX += deltaX
            _panToY += deltaY
        }
        if (_zoomRunning) {
            _zoomMouseX += deltaX
            _zoomMouseY += deltaY
        }
        viewportCenterShifted(deltaX, deltaY)
    }

    function stopMotion() {
        _inertiaRunning = false
        _keyboardPanRunning = false
        _zoomRunning = false
        _panRunning = false
        keyboardPanLeft = false
        keyboardPanRight = false
        keyboardPanUp = false
        keyboardPanDown = false
        velocityX = 0
        velocityY = 0
        keyboardVelocityX = 0
        keyboardVelocityY = 0
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
            _inertiaRunning = true
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
        _zoomFrom = contentScale
        _zoomTo = newScale
        _zoomElapsed = 0.0
        _zoomRunning = Math.abs(_zoomTo - _zoomFrom) > 0.0001
    }

    function smoothCenterOn(targetX, targetY) {
        smoothCenterOnScreen(targetX, targetY, width / 2, height / 2)
    }

    function smoothCenterOnScreen(targetX, targetY, screenCenterX, screenCenterY) {
        stopMotion()
        _startPan(
            screenCenterX - targetX * contentScale,
            screenCenterY - targetY * contentScale
        )
    }

    function smoothMoveTo(layerX, layerY) {
        stopMotion()
        _startPan(layerX, layerY)
    }

    function _startPan(layerX, layerY) {
        if (!contentLayer) return
        _panFromX = contentLayer.x
        _panFromY = contentLayer.y
        _panToX = layerX
        _panToY = layerY
        _panElapsed = 0.0
        _panRunning = Math.abs(_panToX - _panFromX)
                + Math.abs(_panToY - _panFromY) > 0.01
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
            _inertiaRunning = false
            _panRunning = false
            _keyboardPanRunning = true
        } else if (!_hasKeyboardPanInput()
                   && Math.abs(keyboardVelocityX) + Math.abs(keyboardVelocityY) < 0.5) {
            _keyboardPanRunning = false
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

    function advanceFrame(frameTime) {
        var dt = Math.min(Math.max(Number(frameTime), 0.0), 0.05)
        if (!isFinite(dt) || dt <= 0) return
        if (_inertiaRunning) _advanceInertia(dt)
        if (_keyboardPanRunning) _advanceKeyboardPan(dt)
        if (_zoomRunning) _advanceZoom(dt)
        if (_panRunning) _advancePan(dt)
    }

    function _advanceInertia(dt) {
        if (!contentLayer) {
            _inertiaRunning = false
            return
        }
        // Preserve the old 60 Hz inertia curve while subdividing it into
        // as many updates as the display can render.
        var frameRatio = dt / referenceFrameTime
        var decay = Math.pow(inertiaDecayPerReferenceFrame, frameRatio)
        var distanceScale = inertiaDecayPerReferenceFrame
                * (1.0 - decay) / (1.0 - inertiaDecayPerReferenceFrame)
        var previousVelocityX = velocityX
        var previousVelocityY = velocityY
        velocityX *= decay
        velocityY *= decay
        if (Math.abs(velocityX) + Math.abs(velocityY) < 1.0) {
            _inertiaRunning = false
            return
        }
        contentLayer.x += previousVelocityX * distanceScale
        contentLayer.y += previousVelocityY * distanceScale
    }

    function _advanceKeyboardPan(dt) {
        if (!contentLayer) {
            _keyboardPanRunning = false
            return
        }
        var axisX = _keyboardAxis(keyboardPanRight, keyboardPanLeft)
        var axisY = _keyboardAxis(keyboardPanDown, keyboardPanUp)
        var length = Math.sqrt(axisX * axisX + axisY * axisY)
        if (length > 0) {
            axisX /= length
            axisY /= length
        }

        var targetX = axisX * keyboardMaxSpeed
        var targetY = axisY * keyboardMaxSpeed
        var hasInput = length > 0
        keyboardVelocityX = _approach(
            keyboardVelocityX,
            targetX,
            _keyboardDelta(keyboardVelocityX, targetX, hasInput, dt)
        )
        keyboardVelocityY = _approach(
            keyboardVelocityY,
            targetY,
            _keyboardDelta(keyboardVelocityY, targetY, hasInput, dt)
        )

        if (length === 0
                && Math.abs(keyboardVelocityX) + Math.abs(keyboardVelocityY) < 0.5) {
            keyboardVelocityX = 0
            keyboardVelocityY = 0
            _keyboardPanRunning = false
            return
        }
        contentLayer.x += keyboardVelocityX * dt
        contentLayer.y += keyboardVelocityY * dt
    }

    function _advanceZoom(dt) {
        _zoomElapsed = Math.min(zoomDuration, _zoomElapsed + dt)
        var progress = zoomDuration > 0 ? _zoomElapsed / zoomDuration : 1.0
        var eased = 1.0 - Math.pow(1.0 - progress, 2)
        contentScale = _zoomFrom + (_zoomTo - _zoomFrom) * eased
        if (progress >= 1.0) {
            contentScale = _zoomTo
            _zoomRunning = false
        }
    }

    function _advancePan(dt) {
        if (!contentLayer) {
            _panRunning = false
            return
        }
        _panElapsed = Math.min(panDuration, _panElapsed + dt)
        var progress = panDuration > 0 ? _panElapsed / panDuration : 1.0
        var eased = 1.0 - Math.pow(1.0 - progress, 3)
        contentLayer.x = _panFromX + (_panToX - _panFromX) * eased
        contentLayer.y = _panFromY + (_panToY - _panFromY) * eased
        if (progress >= 1.0) {
            contentLayer.x = _panToX
            contentLayer.y = _panToY
            _panRunning = false
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

    onWidthChanged: preserveCenterOnResize()
    onHeightChanged: preserveCenterOnResize()

    onContentScaleChanged: {
        if (!contentLayer) return
        contentLayer.x = _zoomMouseX - _zoomAnchorX * contentScale
        contentLayer.y = _zoomMouseY - _zoomAnchorY * contentScale
        zoomChanged(contentScale)
    }

}
