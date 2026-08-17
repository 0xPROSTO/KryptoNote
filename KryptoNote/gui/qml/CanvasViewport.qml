import QtQuick

Item {
    id: viewport
    property Item contentLayer
    // Qt documents pixelDelta as the native high-resolution path, but warns
    // that X11 pixel deltas are driver-specific.  The Python runtime sets
    // this only for xcb; Wayland retains pixel-first behavior.
    property bool preferAngleDelta: false
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
    property bool _zoomAnchorValid: false
    readonly property real zoomDuration: 0.12

    property real _panFromX: 0.0
    property real _panFromY: 0.0
    property real _panToX: 0.0
    property real _panToY: 0.0
    property real _panElapsed: 0.0
    readonly property real panDuration: 0.20

    signal zoomChanged(real scale)
    signal viewportCenterShifted(real deltaX, real deltaY)
    signal cameraChanged()

    // The camera contract is deliberately kept in one place.  All canvas
    // coordinates are logical scene units, while callers pass viewport pixel
    // (QML logical) coordinates.  Keeping these helpers here prevents small
    // differences in scale/offset arithmetic between hit testing, delegates,
    // drag-and-drop, and the viewport proxy.
    readonly property real safeScale: Math.max(contentScale, 0.0001)
    readonly property real cameraOffsetX: contentLayer ? contentLayer.x : 0.0
    readonly property real cameraOffsetY: contentLayer ? contentLayer.y : 0.0

    function screenToCanvas(screenX, screenY) {
        return Qt.point(
            (Number(screenX) - cameraOffsetX) / safeScale,
            (Number(screenY) - cameraOffsetY) / safeScale
        )
    }

    function canvasToScreen(canvasX, canvasY) {
        return Qt.point(
            cameraOffsetX + Number(canvasX) * safeScale,
            cameraOffsetY + Number(canvasY) * safeScale
        )
    }

    function visibleCanvasRect(margin) {
        var extra = Number(margin)
        if (!isFinite(extra)) extra = 0.0
        return Qt.rect(
            -cameraOffsetX / safeScale - extra,
            -cameraOffsetY / safeScale - extra,
            width / safeScale + extra * 2.0,
            height / safeScale + extra * 2.0
        )
    }

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
        _zoomAnchorValid = false
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

    function panBy(dx, dy, updateVelocity) {
        if (!contentLayer) return
        if (updateVelocity === undefined) updateVelocity = true
        contentLayer.x += dx
        contentLayer.y += dy
        if (updateVelocity) {
            velocityX = velocityX * 0.4 + dx * 1.85
            velocityY = velocityY * 0.4 + dy * 1.85
        }
    }

    function startInertiaIfNeeded() {
        if (Math.abs(velocityX) + Math.abs(velocityY) > 2) {
            _inertiaRunning = true
        }
    }

    function zoomAt(mouseX, mouseY, zoomIn) {
        zoomByFactor(mouseX, mouseY, zoomIn ? zoomFactor : (1.0 / zoomFactor))
    }

    function zoomByFactor(mouseX, mouseY, factor) {
        if (!contentLayer) return
        factor = Number(factor)
        if (!isFinite(factor) || factor <= 0.0) return
        var newScale = Math.max(minScale, Math.min(maxScale, contentScale * factor))
        _zoomAnchorX = (Number(mouseX) - contentLayer.x) / safeScale
        _zoomAnchorY = (Number(mouseY) - contentLayer.y) / safeScale
        _zoomMouseX = mouseX
        _zoomMouseY = mouseY
        _zoomFrom = contentScale
        _zoomTo = newScale
        _zoomElapsed = 0.0
        _zoomAnchorValid = Math.abs(_zoomTo - _zoomFrom) > 0.0001
        _zoomRunning = _zoomAnchorValid
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
            _zoomAnchorValid = false
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

    function _wheelComponent(event, propertyName) {
        if (!event || event[propertyName] === undefined || event[propertyName] === null) {
            return 0.0
        }
        var value = Number(event[propertyName].y)
        return isFinite(value) ? value : 0.0
    }

    function _wheelHorizontalComponent(event, propertyName) {
        if (!event || event[propertyName] === undefined || event[propertyName] === null) {
            return 0.0
        }
        var value = Number(event[propertyName].x)
        return isFinite(value) ? value : 0.0
    }

    function _wheelDelta(event) {
        var pixelX = _wheelHorizontalComponent(event, "pixelDelta")
        var pixelY = _wheelComponent(event, "pixelDelta")
        var hasPixels = Math.abs(pixelX) > 0.001 || Math.abs(pixelY) > 0.001
        if (hasPixels && !viewport.preferAngleDelta) {
            return Qt.point(pixelX, pixelY)
        }
        var angleX = _wheelHorizontalComponent(event, "angleDelta")
        var angleY = _wheelComponent(event, "angleDelta")
        if (Math.abs(angleX) <= 0.001 && Math.abs(angleY) <= 0.001 && hasPixels) {
            return Qt.point(pixelX, pixelY)
        }
        // One wheel step is conventionally 120 eighths of a degree.  Keep a
        // useful screen-space fallback for traditional mouse wheels.
        return Qt.point(angleX / 120.0 * 48.0, angleY / 120.0 * 48.0)
    }

    function handleWheel(event, zoom) {
        var mouseX = event && event.x !== undefined ? event.x : viewport.width / 2
        var mouseY = event && event.y !== undefined ? event.y : viewport.height / 2
        var delta = _wheelDelta(event)
        if (zoom) {
            var magnitude = Math.abs(delta.y) > 0.001
                    ? delta.y / 240.0
                    : delta.x / 240.0
            if (Math.abs(magnitude) <= 0.0001) return false
            viewport.zoomByFactor(
                mouseX,
                mouseY,
                Math.exp(magnitude * Math.log(viewport.zoomFactor))
            )
            return true
        }
        if (Math.abs(delta.x) > 0.001 || Math.abs(delta.y) > 0.001) {
            // Wheel/touchpad momentum is delivered by Qt.  Do not feed it
            // into the canvas drag inertia accumulator a second time.
            viewport.panBy(delta.x, delta.y, false)
            return true
        }
        return false
    }

    WheelHandler {
        id: zoomWheel
        acceptedModifiers: Qt.ControlModifier
        acceptedDevices: PointerDevice.Mouse | PointerDevice.TouchPad
        onWheel: function(event) {
            event.accepted = viewport.handleWheel(event, true)
        }
    }

    WheelHandler {
        id: panWheel
        acceptedModifiers: Qt.NoModifier
        acceptedDevices: PointerDevice.Mouse | PointerDevice.TouchPad
        onWheel: function(event) {
            event.accepted = viewport.handleWheel(event, false)
        }
    }

    onWidthChanged: preserveCenterOnResize()
    onHeightChanged: preserveCenterOnResize()

    onContentScaleChanged: {
        if (!contentLayer) return
        if (_zoomRunning || _zoomAnchorValid) {
            contentLayer.x = _zoomMouseX - _zoomAnchorX * contentScale
            contentLayer.y = _zoomMouseY - _zoomAnchorY * contentScale
        }
        cameraChanged()
        zoomChanged(contentScale)
    }

}
