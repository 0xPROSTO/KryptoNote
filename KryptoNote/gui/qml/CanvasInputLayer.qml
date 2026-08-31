import QtQuick

Item {
    id: input
    required property var nodeModel
    required property var connectionModel
    required property var canvasController
    required property Item contentLayer
    required property var viewport
    required property var rubberBand
    property real contentScale: 1.0
    property real gridSize: 100.0
    property bool snapToGrid: false
    property bool isLinkMode: false
    property bool isEraserMode: false
    property bool isCtrlHeld: false
    property bool isShiftHeld: false
    property string gestureState: "idle"
    readonly property bool isPanning: gestureState === "canvasPan"
    property bool suppressingNextPress: false
    property bool suppressingMouseSequence: false
    signal contextMenuRequested(
        var sourceItem,
        real localX,
        real localY,
        real contentX,
        real contentY
    )

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
        property int activeButton: 0

        onPressed: function(mouse) {
            if (input.suppressingNextPress) {
                input.suppressingNextPress = false
                input.cancelPointerGesture()
                input.suppressingMouseSequence = true
                mouse.accepted = true
                return
            }

            input.viewport.stopMotion()
            lastPos = Qt.point(mouse.x, mouse.y)
            pressPos = Qt.point(mouse.x, mouse.y)
            activeButton = mouse.button
            input.transitionGesture("idle")

            if (mouse.button === Qt.RightButton && input.isShiftHeld) {
                input.isEraserMode = true
                input.transitionGesture("eraser")
                cursorShape = Qt.ForbiddenCursor
                mouse.accepted = true
                return
            }

            if (mouse.button === Qt.LeftButton && input.isCtrlHeld) {
                input.rubberBand.begin(mouse.x, mouse.y)
                input.transitionGesture("rubberBand")
                mouse.accepted = true
                return
            }

            if (mouse.button === Qt.LeftButton || mouse.button === Qt.MiddleButton) {
                input.transitionGesture("canvasPan")
                mouse.accepted = true
            }
        }

        onPositionChanged: function(mouse) {
            if (input.suppressingMouseSequence) {
                mouse.accepted = true
                return
            }

            var contentPos = input.viewport.screenToCanvas(mouse.x, mouse.y)

            if (input.isEraserMode) {
                mouse.accepted = true
                var hitRadius = 10 / Math.max(input.contentScale, 0.12)
                var renderPos = input.viewport.screenToRender(mouse.x, mouse.y)
                var connectionId = input.connectionModel.hit_test_connection_render(
                    input.viewport.renderOriginX,
                    input.viewport.renderOriginY,
                    renderPos.x,
                    renderPos.y,
                    hitRadius
                )
                if (connectionId > 0) {
                    input.canvasController.delete_connection(connectionId)
                }
                return
            }

            if (input.rubberBand.visible) {
                mouse.accepted = true
                input.rubberBand.updateBand(mouse.x, mouse.y)
                return
            }

            if (input.gestureState === "canvasPan" && dragging) {
                mouse.accepted = true
                input.viewport.panBy(mouse.x - lastPos.x, mouse.y - lastPos.y)
                lastPos = Qt.point(mouse.x, mouse.y)
            } else if (input.gestureState === "idle") {
                // Allow node/connection handlers above this fallback layer to
                // own a pointer that is not part of a canvas gesture.
                mouse.accepted = false
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
                input.transitionGesture("idle")
                cursorShape = Qt.ArrowCursor
                mouse.accepted = true
                return
            }

            if (input.rubberBand.visible) {
                input.rubberBand.finishSelection()
                input.transitionGesture("idle")
                mouse.accepted = true
                return
            }

            var wasPanning = input.gestureState === "canvasPan" && dragging
            if (wasPanning) {
                dragging = false
                input.viewport.startInertiaIfNeeded()
            }

            if (Math.abs(mouse.x - pressPos.x) < 3 && Math.abs(mouse.y - pressPos.y) < 3) {
                if (mouse.button === Qt.RightButton) {
                    var contentPos = input.viewport.screenToCanvas(
                        mouse.x,
                        mouse.y
                    )
                    input.contextMenuRequested(
                        canvasMouseArea,
                        mouse.x,
                        mouse.y,
                        contentPos.x,
                        contentPos.y
                    )
                    mouse.accepted = true
                } else if (wasPanning
                           && mouse.button === Qt.LeftButton
                           && !input.isShiftHeld) {
                    input.nodeModel.clear_selection()
                    input.nodeModel.clear_hovered()
                }
            }
            input.transitionGesture("idle")
            mouse.accepted = true
        }

        // PointerHandlers and native window focus changes can take the grab
        // away without a release.  Reset the FSM here so a later node drag is
        // never blocked by a stale canvas-pan state.
        onCanceled: input.cancelPointerGesture()
    }

    function transitionGesture(nextState) {
        gestureState = nextState
        canvasMouseArea.dragging = nextState === "canvasPan"
        if (nextState === "canvasPan") {
            canvasMouseArea.cursorShape = Qt.ClosedHandCursor
        } else if (nextState === "eraser") {
            canvasMouseArea.cursorShape = Qt.ForbiddenCursor
        } else {
            canvasMouseArea.cursorShape = Qt.ArrowCursor
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
        transitionGesture("idle")
        isEraserMode = false
        canvasMouseArea.activeButton = 0
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
            input.canvasController.toggle_link_mode_off()
        }
    }

    function resetModifiers() {
        isCtrlHeld = false
        isShiftHeld = false
        isLinkMode = false
        input.canvasController.toggle_link_mode_off()
    }

    function syncModifiers(ctrlHeld, shiftHeld) {
        isCtrlHeld = ctrlHeld
        isShiftHeld = shiftHeld
        isLinkMode = shiftHeld
        if (!shiftHeld) {
            input.canvasController.toggle_link_mode_off()
        }
    }

}
