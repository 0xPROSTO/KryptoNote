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

            input.viewport.stopMotion()
            lastPos = Qt.point(mouse.x, mouse.y)
            pressPos = Qt.point(mouse.x, mouse.y)

            if (mouse.button === Qt.RightButton && input.isShiftHeld) {
                input.isEraserMode = true
                cursorShape = Qt.ForbiddenCursor
                mouse.accepted = true
                return
            }

            if (mouse.button === Qt.LeftButton && input.isCtrlHeld) {
                input.rubberBand.begin(mouse.x, mouse.y)
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

            var contentPos = mapToItem(input.contentLayer, mouse.x, mouse.y)
            mouse.accepted = false

            if (input.isEraserMode) {
                var hitRadius = 10 / Math.max(input.contentScale, 0.12)
                var connectionId = input.connectionModel.hit_test_connection(
                    contentPos.x,
                    contentPos.y,
                    hitRadius
                )
                if (connectionId > 0) {
                    input.canvasController.delete_connection(connectionId)
                }
                return
            }

            if (input.rubberBand.visible) {
                input.rubberBand.updateBand(mouse.x, mouse.y)
                return
            }

            if (dragging) {
                input.viewport.panBy(mouse.x - lastPos.x, mouse.y - lastPos.y)
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

            if (input.rubberBand.visible) {
                input.rubberBand.finishSelection(input.contentLayer, input.contentScale)
                return
            }

            if (dragging) {
                dragging = false
                input.isPanning = false
                cursorShape = Qt.ArrowCursor
                input.viewport.startInertiaIfNeeded()
            }

            if (Math.abs(mouse.x - pressPos.x) < 3 && Math.abs(mouse.y - pressPos.y) < 3) {
                if (mouse.button === Qt.LeftButton && !input.isShiftHeld) {
                    input.nodeModel.clear_selection()
                    input.nodeModel.clear_hovered()
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
