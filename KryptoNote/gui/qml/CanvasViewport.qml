import QtQuick

Item {
    id: viewport
    property Item contentLayer
    // Qt documents pixelDelta as the native high-resolution path, but warns
    // that X11 pixel deltas are driver-specific.  The runtime can force the
    // stable angle path on platforms where those deltas are unreliable.
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
    property bool _continuousZoomPending: false
    property bool _continuousZoomGestureActive: false
    property bool _panRunning: false
    property bool _initialized: false
    property real _lastViewportWidth: 0.0
    property real _lastViewportHeight: 0.0
    readonly property bool zoomActive: _zoomRunning
            || _continuousZoomPending || _continuousZoomGestureActive
    readonly property bool frameClockNeeded: _inertiaRunning
            || _keyboardPanRunning || zoomActive || _panRunning

    property real _zoomAnchorX: 0
    property real _zoomAnchorY: 0
    property real _zoomMouseX: 0
    property real _zoomMouseY: 0
    property real _zoomFrom: 1.0
    property real _zoomTo: 1.0
    property real _zoomElapsed: 0.0
    property real _zoomStartVelocity: 0.0
    property real _zoomVelocity: 0.0
    property bool _zoomAnchorValid: false
    property real _pendingZoomLog: 0.0
    property real _pendingZoomMouseX: 0.0
    property real _pendingZoomMouseY: 0.0
    property real _continuousZoomIdleElapsed: 0.0
    readonly property real zoomDuration: 0.12
    readonly property real continuousZoomIdleDuration: 0.08

    property real _panFromX: 0.0
    property real _panFromY: 0.0
    property real _panToX: 0.0
    property real _panToY: 0.0
    property real _panElapsed: 0.0
    property var _panFinishedCallback: null
    readonly property real panDuration: 0.20

    signal zoomChanged(real scale)
    signal zoomFinished(real scale)
    signal viewportCenterShifted(real deltaX, real deltaY)

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
        if (_continuousZoomPending) {
            _pendingZoomMouseX += deltaX
            _pendingZoomMouseY += deltaY
        }
        viewportCenterShifted(deltaX, deltaY)
    }

    function stopMotion() {
        _inertiaRunning = false
        _keyboardPanRunning = false
        _zoomRunning = false
        _continuousZoomPending = false
        _continuousZoomGestureActive = false
        _zoomAnchorValid = false
        _panRunning = false
        _panFinishedCallback = null
        keyboardPanLeft = false
        keyboardPanRight = false
        keyboardPanUp = false
        keyboardPanDown = false
        velocityX = 0
        velocityY = 0
        keyboardVelocityX = 0
        keyboardVelocityY = 0
        _pendingZoomLog = 0.0
        _continuousZoomIdleElapsed = 0.0
        _zoomFrom = contentScale
        _zoomTo = contentScale
        _zoomElapsed = 0.0
        _zoomStartVelocity = 0.0
        _zoomVelocity = 0.0
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

        // A wheel burst arrives faster than the tween can advance.  Accumulate
        // each notch from the previous target so no discrete step is lost.
        var previousVelocity = _zoomRunning ? _zoomVelocity : 0.0
        var pendingFactor = Math.exp(_pendingZoomLog)
        var baseScale = _zoomRunning
                ? _zoomTo
                : contentScale * pendingFactor
        var newScale = Math.max(minScale, Math.min(maxScale, baseScale * factor))
        _zoomAnchorX = (Number(mouseX) - contentLayer.x) / safeScale
        _zoomAnchorY = (Number(mouseY) - contentLayer.y) / safeScale
        _zoomMouseX = Number(mouseX)
        _zoomMouseY = Number(mouseY)
        _zoomFrom = contentScale
        _zoomTo = newScale
        _zoomElapsed = 0.0
        _zoomStartVelocity = previousVelocity
        _zoomVelocity = previousVelocity
        _zoomAnchorValid = Math.abs(_zoomTo - _zoomFrom) > 0.0001
        _zoomRunning = _zoomAnchorValid
        if (!_zoomRunning) {
            _zoomStartVelocity = 0.0
            _zoomVelocity = 0.0
        }

        // Switch input modes without producing an intermediate terminal
        // state.  Any pending continuous delta was folded into baseScale.
        _continuousZoomPending = false
        _continuousZoomGestureActive = false
        _continuousZoomIdleElapsed = 0.0
        _pendingZoomLog = 0.0
    }

    function setZoomScale(mouseX, mouseY, requestedScale, animated) {
        if (!contentLayer) return
        var targetScale = Math.max(
            minScale,
            Math.min(maxScale, Number(requestedScale))
        )
        if (!isFinite(targetScale)) return

        if (animated) {
            var pendingFactor = Math.exp(_pendingZoomLog)
            var baseScale = _zoomRunning
                    ? _zoomTo : contentScale * pendingFactor
            if (Math.abs(baseScale - targetScale) <= 0.0001) return
            zoomByFactor(
                Number(mouseX),
                Number(mouseY),
                targetScale / Math.max(baseScale, 0.0001)
            )
            return
        }

        var anchor = screenToCanvas(mouseX, mouseY)
        stopMotion()
        contentScale = targetScale
        contentLayer.x = Number(mouseX) - anchor.x * contentScale
        contentLayer.y = Number(mouseY) - anchor.y * contentScale
        zoomFinished(contentScale)
    }

    function queueContinuousZoom(mouseX, mouseY, steps) {
        steps = Number(steps)
        if (!isFinite(steps) || Math.abs(steps) <= 0.0001) {
            return false
        }

        // Mark the continuous gesture first so canceling an in-flight mouse
        // tween cannot briefly emit zoomFinished between input modes.
        _continuousZoomGestureActive = true
        if (_zoomRunning) {
            _zoomRunning = false
            _zoomAnchorValid = false
            _zoomFrom = contentScale
            _zoomTo = contentScale
            _zoomElapsed = 0.0
            _zoomStartVelocity = 0.0
            _zoomVelocity = 0.0
        }

        var maximumPendingLog = Math.log(maxScale / minScale)
        _pendingZoomLog = Math.max(
            -maximumPendingLog,
            Math.min(
                maximumPendingLog,
                _pendingZoomLog + steps * Math.log(zoomFactor)
            )
        )
        _pendingZoomMouseX = Number(mouseX)
        _pendingZoomMouseY = Number(mouseY)
        _continuousZoomIdleElapsed = 0.0
        _continuousZoomPending = true
        return true
    }

    function smoothCenterOn(targetX, targetY, onFinished) {
        smoothCenterOnScreen(
            targetX,
            targetY,
            width / 2,
            height / 2,
            onFinished
        )
    }

    function smoothCenterOnScreen(targetX, targetY, screenCenterX, screenCenterY,
                                  onFinished) {
        stopMotion()
        _startPan(
            screenCenterX - targetX * contentScale,
            screenCenterY - targetY * contentScale,
            onFinished
        )
    }

    function smoothMoveTo(layerX, layerY, onFinished) {
        stopMotion()
        _startPan(layerX, layerY, onFinished)
    }

    function _startPan(layerX, layerY, onFinished) {
        if (!contentLayer) return
        _panFromX = contentLayer.x
        _panFromY = contentLayer.y
        _panToX = layerX
        _panToY = layerY
        _panElapsed = 0.0
        _panFinishedCallback = typeof onFinished === "function"
                ? onFinished : null
        _panRunning = Math.abs(_panToX - _panFromX)
                + Math.abs(_panToY - _panFromY) > 0.01
        if (!_panRunning) {
            contentLayer.x = _panToX
            contentLayer.y = _panToY
            _finishPan()
        }
    }

    function _finishPan() {
        var callback = _panFinishedCallback
        _panFinishedCallback = null
        if (typeof callback === "function") callback()
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
            _panFinishedCallback = null
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
        var continuousZoomApplied = false
        if (_continuousZoomPending) {
            continuousZoomApplied = _applyPendingContinuousZoom()
        }
        if (_zoomRunning) _advanceZoom(dt)
        if (_continuousZoomGestureActive) {
            _advanceContinuousZoomGesture(dt, continuousZoomApplied)
        }
        if (_panRunning) _advancePan(dt)
    }

    function _applyPendingContinuousZoom() {
        var step = _pendingZoomLog
        _pendingZoomLog = 0.0
        _continuousZoomPending = false
        if (Math.abs(step) <= 0.0001 || !contentLayer) return false

        _zoomAnchorX = (_pendingZoomMouseX - contentLayer.x) / safeScale
        _zoomAnchorY = (_pendingZoomMouseY - contentLayer.y) / safeScale
        _zoomMouseX = _pendingZoomMouseX
        _zoomMouseY = _pendingZoomMouseY
        var newScale = Math.max(
            minScale,
            Math.min(maxScale, contentScale * Math.exp(step))
        )
        _zoomAnchorValid = Math.abs(newScale - contentScale) > 0.0001
        if (_zoomAnchorValid) contentScale = newScale
        _zoomAnchorValid = false
        _zoomFrom = contentScale
        _zoomTo = contentScale
        _zoomStartVelocity = 0.0
        _zoomVelocity = 0.0
        return true
    }

    function _advanceContinuousZoomGesture(dt, inputApplied) {
        if (inputApplied) {
            _continuousZoomIdleElapsed = 0.0
            return
        }
        _continuousZoomIdleElapsed += dt
        if (_continuousZoomIdleElapsed >= continuousZoomIdleDuration) {
            _continuousZoomIdleElapsed = 0.0
            _continuousZoomGestureActive = false
        }
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
        var progress2 = progress * progress
        var progress3 = progress2 * progress
        var fromLog = Math.log(Math.max(_zoomFrom, 0.0001))
        var toLog = Math.log(Math.max(_zoomTo, 0.0001))
        var distance = toLog - fromLog
        var tangent = _zoomStartVelocity * zoomDuration

        // Match SmoothedAnimation's useful property without falling back to
        // QQuickWidget's 60 Hz animation driver: splice a new target onto the
        // current logarithmic velocity. Limiting the tangent keeps reversals
        // and scale-limit retargets monotonic enough to avoid overshoot spikes.
        if (Math.abs(distance) > 0.0000001) {
            var normalizedTangent = tangent / distance
            normalizedTangent = Math.max(-1.0, Math.min(3.0, normalizedTangent))
            tangent = normalizedTangent * distance
        } else {
            tangent = 0.0
        }

        var h00 = 2.0 * progress3 - 3.0 * progress2 + 1.0
        var h10 = progress3 - 2.0 * progress2 + progress
        var h01 = -2.0 * progress3 + 3.0 * progress2
        var nextLog = h00 * fromLog + h10 * tangent + h01 * toLog
        var derivative = ((6.0 * progress2 - 6.0 * progress) * fromLog
                          + (3.0 * progress2 - 4.0 * progress + 1.0) * tangent
                          + (-6.0 * progress2 + 6.0 * progress) * toLog)
        _zoomVelocity = zoomDuration > 0 ? derivative / zoomDuration : 0.0
        contentScale = Math.exp(nextLog)
        if (progress >= 1.0) {
            contentScale = _zoomTo
            _zoomStartVelocity = 0.0
            _zoomVelocity = 0.0
            _zoomAnchorValid = false
            _zoomRunning = false
        }
    }

    function _advancePan(dt) {
        if (!contentLayer) {
            _panRunning = false
            _panFinishedCallback = null
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
            _finishPan()
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
        var angleX = _wheelHorizontalComponent(event, "angleDelta")
        var angleY = _wheelComponent(event, "angleDelta")
        var usePixels = _usesPixelWheel(event)
        if (!usePixels && (Math.abs(angleX) > 0.001 || Math.abs(angleY) > 0.001)) {
            // A normal mouse wheel remains one discrete angle step.
            return Qt.point(angleX / 120.0 * 48.0, angleY / 120.0 * 48.0)
        }
        return hasPixels ? Qt.point(pixelX, pixelY) : Qt.point(0, 0)
    }

    function _usesPixelWheel(event) {
        if (preferAngleDelta || !event || !event.device) return false
        var deviceType = event.device.type
        return (deviceType & PointerDevice.TouchPad) !== 0
    }

    function _dominantWheelComponent(event, propertyName) {
        var horizontal = _wheelHorizontalComponent(event, propertyName)
        var vertical = _wheelComponent(event, propertyName)
        return Math.abs(vertical) > 0.001 ? vertical : horizontal
    }

    function _usesContinuousZoomInput(event) {
        var angle = _dominantWheelComponent(event, "angleDelta")
        if (event && event.device
                && (event.device.type & PointerDevice.TouchPad) !== 0) {
            return true
        }
        if (Math.abs(angle) > 0.001 && Math.abs(angle) < 120.0) {
            return true
        }
        var pixel = _dominantWheelComponent(event, "pixelDelta")
        return !preferAngleDelta
                && Math.abs(angle) <= 0.001
                && Math.abs(pixel) > 0.001
    }

    function _continuousZoomSteps(event) {
        var angle = _dominantWheelComponent(event, "angleDelta")
        if (Math.abs(angle) > 0.001) return angle / 120.0
        if (preferAngleDelta) return 0.0
        return _dominantWheelComponent(event, "pixelDelta") / 120.0
    }

    function handleWheel(event, zoom) {
        var mouseX = event && event.x !== undefined ? event.x : viewport.width / 2
        var mouseY = event && event.y !== undefined ? event.y : viewport.height / 2
        if (zoom) {
            var angleX = _wheelHorizontalComponent(event, "angleDelta")
            var angleY = _wheelComponent(event, "angleDelta")
            if (_usesContinuousZoomInput(event)) {
                return viewport.queueContinuousZoom(
                    mouseX,
                    mouseY,
                    _continuousZoomSteps(event)
                )
            }
            if (Math.abs(angleX) > 0.001 || Math.abs(angleY) > 0.001) {
                var angle = Math.abs(angleY) > 0.001 ? angleY : angleX
                viewport.zoomAt(mouseX, mouseY, angle > 0)
                return true
            }
            return false
        }
        var delta = _wheelDelta(event)
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
        if (_zoomAnchorValid) {
            contentLayer.x = _zoomMouseX - _zoomAnchorX * contentScale
            contentLayer.y = _zoomMouseY - _zoomAnchorY * contentScale
        }
        zoomChanged(contentScale)
    }

    onZoomActiveChanged: {
        if (!zoomActive) zoomFinished(contentScale)
    }

}
