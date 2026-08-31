import QtQuick

Item {
    id: viewport
    property Item contentLayer
    // Qt documents pixelDelta as the native high-resolution path, but warns
    // that X11 pixel deltas are driver-specific.  The runtime can force the
    // stable angle path on platforms where those deltas are unreliable.
    property bool preferAngleDelta: false
    property real contentScale: 1.0
    property real minScale: 0.05
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
    // World coordinates remain doubles. Only the nearby render-local values
    // below are ever sent through Qt Quick item transforms.
    property double renderOriginX: 0.0
    property double renderOriginY: 0.0
    readonly property double renderOriginQuantum: 32768.0
    readonly property double renderRebaseThreshold: 65536.0
    readonly property real referenceFrameTime: 1.0 / 60.0
    readonly property real inertiaDecayPerReferenceFrame: 0.82
    readonly property real inertiaReleaseWindowMs: 50.0
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
    property double _lastPointerPanTime: 0.0
    property real _lastViewportWidth: 0.0
    property real _lastViewportHeight: 0.0
    readonly property bool zoomActive: _zoomRunning
            || _continuousZoomPending || _continuousZoomGestureActive
    readonly property bool frameClockNeeded: _inertiaRunning
            || _keyboardPanRunning || zoomActive || _panRunning

    property double _zoomAnchorOriginX: 0.0
    property double _zoomAnchorOriginY: 0.0
    property double _zoomAnchorRenderX: 0.0
    property double _zoomAnchorRenderY: 0.0
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

    property double _panFromOriginX: 0.0
    property double _panFromOriginY: 0.0
    property double _panFromRenderX: 0.0
    property double _panFromRenderY: 0.0
    property double _panToOriginX: 0.0
    property double _panToOriginY: 0.0
    property double _panToRenderX: 0.0
    property double _panToRenderY: 0.0
    property real _panScreenX: 0.0
    property real _panScreenY: 0.0
    property real _panElapsed: 0.0
    property var _panFinishedCallback: null
    readonly property real panDuration: 0.20

    signal zoomChanged(real scale)
    signal zoomFinished(real scale)
    signal viewportCenterShifted(real deltaX, real deltaY)
    signal renderOriginRebased(double deltaX, double deltaY)

    // The camera contract is deliberately kept in one place.  All canvas
    // coordinates are logical scene units, while callers pass viewport pixel
    // (QML logical) coordinates.  Keeping these helpers here prevents small
    // differences in scale/offset arithmetic between hit testing, delegates,
    // drag-and-drop, and the viewport proxy.
    readonly property real safeScale: Math.max(contentScale, 0.0001)
    readonly property real cameraOffsetX: contentLayer ? contentLayer.x : 0.0
    readonly property real cameraOffsetY: contentLayer ? contentLayer.y : 0.0
    readonly property double cameraCenterX: renderOriginX
            + (width / 2.0 - cameraOffsetX) / safeScale
    readonly property double cameraCenterY: renderOriginY
            + (height / 2.0 - cameraOffsetY) / safeScale

    function worldToRender(worldX, worldY) {
        return Qt.point(
            Number(worldX) - renderOriginX,
            Number(worldY) - renderOriginY
        )
    }

    function renderToWorld(renderX, renderY) {
        return Qt.point(
            renderOriginX + Number(renderX),
            renderOriginY + Number(renderY)
        )
    }

    function screenToRender(screenX, screenY) {
        return Qt.point(
            (Number(screenX) - cameraOffsetX) / safeScale,
            (Number(screenY) - cameraOffsetY) / safeScale
        )
    }

    function renderToScreen(renderX, renderY) {
        return Qt.point(
            cameraOffsetX + Number(renderX) * safeScale,
            cameraOffsetY + Number(renderY) * safeScale
        )
    }

    function screenToCanvas(screenX, screenY) {
        var local = screenToRender(screenX, screenY)
        return renderToWorld(local.x, local.y)
    }

    function canvasToScreen(canvasX, canvasY) {
        var local = worldToRender(canvasX, canvasY)
        return renderToScreen(local.x, local.y)
    }

    function captureCameraState(screenX, screenY) {
        screenX = screenX === undefined ? width / 2.0 : Number(screenX)
        screenY = screenY === undefined ? height / 2.0 : Number(screenY)
        if (!isFinite(screenX) || !isFinite(screenY)) return null
        var local = screenToRender(screenX, screenY)
        return {
            "originX": renderOriginX,
            "originY": renderOriginY,
            "renderX": local.x,
            "renderY": local.y,
            "screenOffsetX": screenX - width / 2.0,
            "screenOffsetY": screenY - height / 2.0
        }
    }

    function visibleRenderRect(margin) {
        var extra = Number(margin)
        if (!isFinite(extra)) extra = 0.0
        return Qt.rect(
            -cameraOffsetX / safeScale - extra,
            -cameraOffsetY / safeScale - extra,
            width / safeScale + extra * 2.0,
            height / safeScale + extra * 2.0
        )
    }

    function visibleCanvasRect(margin) {
        var localRect = visibleRenderRect(margin)
        return Qt.rect(
            renderOriginX + localRect.x,
            renderOriginY + localRect.y,
            localRect.width,
            localRect.height
        )
    }

    function _quantizedOrigin(value) {
        value = Number(value)
        if (!isFinite(value)) return 0.0
        var quantized = Math.round(value / renderOriginQuantum)
                * renderOriginQuantum
        return isFinite(quantized) ? quantized : value
    }

    function _replaceRenderOrigin(nextX, nextY, preserveView) {
        nextX = Number(nextX)
        nextY = Number(nextY)
        if (!isFinite(nextX) || !isFinite(nextY)) return false
        var deltaX = nextX - renderOriginX
        var deltaY = nextY - renderOriginY
        if (Math.abs(deltaX) + Math.abs(deltaY) <= 0.0001) return false

        var nextLayerX = cameraOffsetX
        var nextLayerY = cameraOffsetY
        var transformScale = Math.max(contentScale, 0.0001)
        if (preserveView && contentLayer) {
            nextLayerX += deltaX * transformScale
            nextLayerY += deltaY * transformScale
        }
        renderOriginX = nextX
        renderOriginY = nextY
        if (preserveView && contentLayer) {
            contentLayer.x = nextLayerX
            contentLayer.y = nextLayerY
        }
        renderOriginRebased(deltaX, deltaY)
        return true
    }

    function _maybeRebase() {
        if (!contentLayer || !_initialized) return false
        var centerLocalX = (width / 2.0 - cameraOffsetX) / safeScale
        var centerLocalY = (height / 2.0 - cameraOffsetY) / safeScale
        var nextX = renderOriginX
        var nextY = renderOriginY
        if (Math.abs(centerLocalX) >= renderRebaseThreshold) {
            var shiftedX = renderOriginX + _quantizedOrigin(centerLocalX)
            if (shiftedX !== renderOriginX) nextX = shiftedX
        }
        if (Math.abs(centerLocalY) >= renderRebaseThreshold) {
            var shiftedY = renderOriginY + _quantizedOrigin(centerLocalY)
            if (shiftedY !== renderOriginY) nextY = shiftedY
        }
        return _replaceRenderOrigin(nextX, nextY, true)
    }

    function _cameraStateForWorld(worldX, worldY, screenX, screenY) {
        worldX = Number(worldX)
        worldY = Number(worldY)
        if (!isFinite(worldX) || !isFinite(worldY)) return null
        var originX = renderOriginX
        var originY = renderOriginY
        if (Math.abs(worldX - originX) >= renderRebaseThreshold)
            originX = _quantizedOrigin(worldX)
        if (Math.abs(worldY - originY) >= renderRebaseThreshold)
            originY = _quantizedOrigin(worldY)
        return {
            "originX": originX,
            "originY": originY,
            "renderX": worldX - originX,
            "renderY": worldY - originY,
            "screenOffsetX": Number(screenX) - width / 2.0,
            "screenOffsetY": Number(screenY) - height / 2.0
        }
    }

    function _cameraStateIsValid(state) {
        return state
                && isFinite(Number(state.originX))
                && isFinite(Number(state.originY))
                && isFinite(Number(state.renderX))
                && isFinite(Number(state.renderY))
    }

    function _placeCameraComponentsAtScreen(originX, originY, renderX, renderY,
                                            screenX, screenY) {
        originX = Number(originX)
        originY = Number(originY)
        renderX = Number(renderX)
        renderY = Number(renderY)
        screenX = Number(screenX)
        screenY = Number(screenY)
        if (!contentLayer
                || !isFinite(originX) || !isFinite(originY)
                || !isFinite(renderX) || !isFinite(renderY)
                || !isFinite(screenX) || !isFinite(screenY)) return false

        if (Math.abs(renderX) >= renderRebaseThreshold) {
            var shiftX = _quantizedOrigin(renderX)
            var shiftedOriginX = originX + shiftX
            if (shiftedOriginX !== originX) {
                originX = shiftedOriginX
                renderX -= shiftX
            }
        }
        if (Math.abs(renderY) >= renderRebaseThreshold) {
            var shiftY = _quantizedOrigin(renderY)
            var shiftedOriginY = originY + shiftY
            if (shiftedOriginY !== originY) {
                originY = shiftedOriginY
                renderY -= shiftY
            }
        }

        var deltaX = originX - renderOriginX
        var deltaY = originY - renderOriginY
        renderOriginX = originX
        renderOriginY = originY
        contentLayer.x = screenX - renderX * safeScale
        contentLayer.y = screenY - renderY * safeScale
        if (Math.abs(deltaX) + Math.abs(deltaY) > 0.0001)
            renderOriginRebased(deltaX, deltaY)
        return true
    }

    function _placeCameraStateAtScreen(state, screenX, screenY) {
        if (!_cameraStateIsValid(state)) return false
        return _placeCameraComponentsAtScreen(
            state.originX,
            state.originY,
            state.renderX,
            state.renderY,
            screenX,
            screenY
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
            _panScreenX += deltaX
            _panScreenY += deltaY
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
        _lastPointerPanTime = 0.0
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
        _maybeRebase()
        if (updateVelocity) {
            var now = Date.now()
            if (_lastPointerPanTime > 0
                    && now - _lastPointerPanTime
                       > inertiaReleaseWindowMs) {
                velocityX = 0
                velocityY = 0
            }
            velocityX = velocityX * 0.4 + dx * 1.85
            velocityY = velocityY * 0.4 + dy * 1.85
            if (Math.abs(dx) + Math.abs(dy) > 0.0001)
                _lastPointerPanTime = now
        }
    }

    function startInertiaIfNeeded() {
        var inputAge = _lastPointerPanTime > 0
                ? Math.max(0.0, Date.now() - _lastPointerPanTime)
                : Infinity
        _lastPointerPanTime = 0.0
        _inertiaRunning = false
        if (inputAge <= inertiaReleaseWindowMs
                && Math.abs(velocityX) + Math.abs(velocityY) > 2) {
            _inertiaRunning = true
            return true
        }
        velocityX = 0
        velocityY = 0
        return false
    }

    function zoomAt(mouseX, mouseY, zoomIn) {
        zoomByFactor(mouseX, mouseY, zoomIn ? zoomFactor : (1.0 / zoomFactor))
    }

    function _applyAnchoredScale(nextScale) {
        contentScale = nextScale
        if (_zoomAnchorValid) {
            _placeCameraComponentsAtScreen(
                _zoomAnchorOriginX,
                _zoomAnchorOriginY,
                _zoomAnchorRenderX,
                _zoomAnchorRenderY,
                _zoomMouseX,
                _zoomMouseY
            )
        }
    }

    function _captureZoomAnchor(mouseX, mouseY) {
        var anchor = screenToRender(mouseX, mouseY)
        _zoomAnchorOriginX = renderOriginX
        _zoomAnchorOriginY = renderOriginY
        _zoomAnchorRenderX = anchor.x
        _zoomAnchorRenderY = anchor.y
        _zoomMouseX = Number(mouseX)
        _zoomMouseY = Number(mouseY)
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
        _captureZoomAnchor(mouseX, mouseY)
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

        stopMotion()
        _captureZoomAnchor(mouseX, mouseY)
        _zoomAnchorValid = true
        _applyAnchoredScale(targetScale)
        _zoomAnchorValid = false
        _maybeRebase()
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
        setCenterOnScreen(
            targetX,
            targetY,
            screenCenterX,
            screenCenterY,
            true,
            onFinished
        )
    }

    function setCenterOnScreen(targetX, targetY, screenCenterX, screenCenterY,
                               animated, onFinished) {
        targetX = Number(targetX)
        targetY = Number(targetY)
        screenCenterX = Number(screenCenterX)
        screenCenterY = Number(screenCenterY)
        if (!contentLayer
                || !isFinite(targetX) || !isFinite(targetY)
                || !isFinite(screenCenterX) || !isFinite(screenCenterY)) {
            return false
        }

        var state = _cameraStateForWorld(
            targetX,
            targetY,
            screenCenterX,
            screenCenterY
        )
        return _setCameraStateOnScreen(
            state,
            screenCenterX,
            screenCenterY,
            animated,
            onFinished
        )
    }

    function restoreCameraState(state, animated, onFinished) {
        if (!_cameraStateIsValid(state)) return false
        var offsetX = Number(state.screenOffsetX)
        var offsetY = Number(state.screenOffsetY)
        if (!isFinite(offsetX)) offsetX = 0.0
        if (!isFinite(offsetY)) offsetY = 0.0
        return _setCameraStateOnScreen(
            state,
            width / 2.0 + offsetX,
            height / 2.0 + offsetY,
            Boolean(animated),
            onFinished
        )
    }

    function _setCameraStateOnScreen(state, screenX, screenY, animated,
                                     onFinished) {
        screenX = Number(screenX)
        screenY = Number(screenY)
        if (!_cameraStateIsValid(state)
                || !isFinite(screenX) || !isFinite(screenY)) return false
        stopMotion()
        if (animated) {
            _startPanState(state, screenX, screenY, onFinished)
        } else {
            _placeCameraStateAtScreen(state, screenX, screenY)
            if (typeof onFinished === "function") onFinished()
        }
        return true
    }

    function smoothMoveTo(layerX, layerY, onFinished) {
        layerX = Number(layerX)
        layerY = Number(layerY)
        if (!isFinite(layerX) || !isFinite(layerY)) return false
        return _setCameraStateOnScreen({
            "originX": renderOriginX,
            "originY": renderOriginY,
            "renderX": (width / 2.0 - layerX) / safeScale,
            "renderY": (height / 2.0 - layerY) / safeScale
        }, width / 2.0, height / 2.0, true, onFinished)
    }

    function smoothPanByScreen(deltaX, deltaY, onFinished) {
        deltaX = Number(deltaX)
        deltaY = Number(deltaY)
        if (!isFinite(deltaX) || !isFinite(deltaY)) return false
        var target = screenToRender(
            width / 2.0 - deltaX,
            height / 2.0 - deltaY
        )
        return _setCameraStateOnScreen({
            "originX": renderOriginX,
            "originY": renderOriginY,
            "renderX": target.x,
            "renderY": target.y
        }, width / 2.0, height / 2.0, true, onFinished)
    }

    function _startPanState(state, screenX, screenY, onFinished) {
        if (!contentLayer || !_cameraStateIsValid(state)) return
        var current = captureCameraState(screenX, screenY)
        _panFromOriginX = current.originX
        _panFromOriginY = current.originY
        _panFromRenderX = current.renderX
        _panFromRenderY = current.renderY
        _panToOriginX = Number(state.originX)
        _panToOriginY = Number(state.originY)
        _panToRenderX = Number(state.renderX)
        _panToRenderY = Number(state.renderY)
        _panScreenX = screenX
        _panScreenY = screenY
        _panElapsed = 0.0
        _panFinishedCallback = typeof onFinished === "function"
                ? onFinished : null
        var originChanged = _panToOriginX !== _panFromOriginX
                || _panToOriginY !== _panFromOriginY
        var renderDistance = Math.abs(_panToRenderX - _panFromRenderX)
                + Math.abs(_panToRenderY - _panFromRenderY)
        _panRunning = originChanged || renderDistance > 0.0001
        if (!_panRunning) {
            _placeCameraComponentsAtScreen(
                _panToOriginX,
                _panToOriginY,
                _panToRenderX,
                _panToRenderY,
                _panScreenX,
                _panScreenY
            )
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

        _captureZoomAnchor(_pendingZoomMouseX, _pendingZoomMouseY)
        var newScale = Math.max(
            minScale,
            Math.min(maxScale, contentScale * Math.exp(step))
        )
        _zoomAnchorValid = Math.abs(newScale - contentScale) > 0.0001
        if (_zoomAnchorValid) _applyAnchoredScale(newScale)
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
        _maybeRebase()
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
        _maybeRebase()
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
        _applyAnchoredScale(Math.exp(nextLog))
        if (progress >= 1.0) {
            _applyAnchoredScale(_zoomTo)
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
        if (progress >= 1.0) {
            _placeCameraComponentsAtScreen(
                _panToOriginX,
                _panToOriginY,
                _panToRenderX,
                _panToRenderY,
                _panScreenX,
                _panScreenY
            )
            _panRunning = false
            _finishPan()
            return
        }
        // Interpolate the double-precision origin and the small render-local
        // offset independently. Collapsing them into one world coordinate
        // discards sub-ULP camera motion at legacy coordinates such as 1e38.
        _placeCameraComponentsAtScreen(
            _interpolateComponent(
                _panFromOriginX, _panToOriginX, eased
            ),
            _interpolateComponent(
                _panFromOriginY, _panToOriginY, eased
            ),
            _interpolateComponent(
                _panFromRenderX, _panToRenderX, eased
            ),
            _interpolateComponent(
                _panFromRenderY, _panToRenderY, eased
            ),
            _panScreenX,
            _panScreenY
        )
    }

    function _interpolateComponent(fromValue, toValue, amount) {
        if (fromValue === toValue || amount <= 0.0) return fromValue
        if (amount >= 1.0) return toValue
        // Weighted endpoints avoid overflowing `to - from` for long pans
        // between very large finite coordinates.
        return fromValue * (1.0 - amount) + toValue * amount
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
        _maybeRebase()
        zoomChanged(contentScale)
    }

    onZoomActiveChanged: {
        if (!zoomActive) zoomFinished(contentScale)
    }

}
