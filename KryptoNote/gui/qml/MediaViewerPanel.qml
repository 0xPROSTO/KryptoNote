pragma ComponentBehavior: Bound

import QtQuick

Item {
    id: panel
    objectName: "mediaViewerPanel"

    required property var appTheme
    required property var canvasController
    required property var viewerController
    property bool open: false
    property bool expanded: false
    property bool panelVisible: false
    property bool userResized: false
    property bool expansionTransition: false
    property string pendingAction: ""
    property real preferredWidth: 520
    readonly property real minPanelWidth: parent ? parent.width * 0.25 : 320
    readonly property real maxPanelWidth: parent ? parent.width * 0.75 : 960
    readonly property real mediaAspectRatio: Math.max(
        1.0,
        Number(viewerController.mediaAspectRatio) || 1.0
    )
    readonly property real automaticWidthRatio: 0.40 + 0.15 * Math.min(
        1.0,
        (mediaAspectRatio - 1.0) / (16.0 / 9.0 - 1.0)
    )
    readonly property real automaticWidth: parent
                                           ? parent.width * automaticWidthRatio
                                           : 520
    readonly property real collapsedWidth: Math.max(
        minPanelWidth,
        Math.min(maxPanelWidth, userResized ? preferredWidth : automaticWidth)
    )
    property real slideOffset: open ? 0 : width
    readonly property bool resizing: resizeMouse.pressed
    readonly property bool tagPickerOpen: mediaSurface.tagPickerOpen
    readonly property bool renameEditing: mediaSurface.renameEditing

    signal requestedClose()
    signal requestedCenter(int nodeId)
    signal expandedChangedByUser(bool expanded)

    width: expanded && parent
           ? parent.width
           : collapsedWidth
    height: parent ? parent.height : 0
    x: parent ? parent.width - width + slideOffset : 0
    visible: panelVisible

    onCollapsedWidthChanged: {
        if (!open || expanded || expansionTransition || resizing) return
        Qt.callLater(function() {
            if (panel.open && !panel.expanded && !panel.resizing)
                panel.requestedCenter(panel.viewerController.nodeId)
        })
    }

    onOpenChanged: {
        if (open) {
            hideTimer.stop()
            panelVisible = true
            Qt.callLater(function() {
                if (panel.open) mediaSurface.forceActiveFocus()
            })
        } else {
            resetExpanded()
            hideTimer.restart()
        }
    }

    function closeTagPicker() {
        return mediaSurface.closeTagPicker()
    }

    function cancelRename() {
        return mediaSurface.cancelRename()
    }

    function commitPendingEdits() {
        return mediaSurface.commitPendingEdits()
    }

    function promptDescriptionGuard(action) {
        if (!viewerController.descriptionDirty) return false
        mediaSurface.openDescriptionGuard(action)
        return true
    }

    function resetExpanded() {
        expansionTimer.stop()
        expansionTransition = false
        pendingAction = ""
        expanded = false
    }

    function collapseOrClose() {
        if (expanded) {
            setExpanded(false)
        } else {
            mediaSurface.requestClose()
        }
    }

    function requestCloseAnimated() {
        runAfterCollapse("close")
    }

    function requestCloseGuarded() {
        mediaSurface.requestClose()
    }

    function requestDetachAnimated() {
        runAfterCollapse("detach")
    }

    function runAfterCollapse(action) {
        pendingAction = action
        if (expanded) {
            setExpanded(false)
        } else if (!expansionTransition) {
            executePendingAction()
        }
    }

    function executePendingAction() {
        var action = pendingAction
        pendingAction = ""
        if (action === "close")
            requestedClose()
        else if (action === "detach")
            viewerController.request_detach()
    }

    function setExpanded(nextExpanded) {
        if (expanded === nextExpanded) return
        expansionTransition = true
        expanded = nextExpanded
        expansionTimer.restart()
    }

    function toggleExpanded() {
        setExpanded(!expanded)
    }

    Timer {
        id: hideTimer
        interval: 230
        repeat: false
        onTriggered: panel.panelVisible = false
    }

    Timer {
        id: expansionTimer
        interval: 280
        repeat: false
        onTriggered: {
            panel.expansionTransition = false
            if (panel.pendingAction.length > 0) {
                panel.executePendingAction()
            } else {
                panel.expandedChangedByUser(panel.expanded)
            }
        }
    }

    Connections {
        target: panel.viewerController
        function onSessionOpened() { panel.userResized = false }
    }

    Behavior on slideOffset {
        NumberAnimation { duration: 220; easing.type: Easing.OutCubic }
    }

    Behavior on width {
        enabled: panel.expansionTransition && panel.open && !panel.resizing
        NumberAnimation { duration: 260; easing.type: Easing.OutCubic }
    }

    Rectangle {
        id: resizeGrip
        z: 3
        width: 7
        anchors.left: parent.left
        anchors.top: parent.top
        anchors.bottom: parent.bottom
        visible: panel.open && !panel.expanded && !panel.expansionTransition
        color: resizeMouse.containsMouse || resizeMouse.pressed
               ? panel.appTheme.accentMain : "transparent"
        opacity: resizeMouse.containsMouse || resizeMouse.pressed ? 0.55 : 0

        Behavior on opacity { NumberAnimation { duration: 120 } }

        MouseArea {
            id: resizeMouse
            anchors.fill: parent
            hoverEnabled: true
            preventStealing: true
            acceptedButtons: Qt.LeftButton
            cursorShape: Qt.SizeHorCursor
            property real pressSceneX: 0
            property real startPreferredWidth: 0

            onPressed: function(mouse) {
                mouse.accepted = true
                pressSceneX = resizeMouse.mapToItem(panel.parent, mouse.x, mouse.y).x
                startPreferredWidth = panel.collapsedWidth
                panel.preferredWidth = startPreferredWidth
                panel.userResized = true
            }
            onPositionChanged: function(mouse) {
                if (!pressed) return
                mouse.accepted = true
                var sceneX = resizeMouse.mapToItem(
                    panel.parent,
                    mouse.x,
                    mouse.y
                ).x
                var nextWidth = startPreferredWidth - (sceneX - pressSceneX)
                panel.preferredWidth = Math.max(
                    panel.minPanelWidth,
                    Math.min(panel.maxPanelWidth, nextWidth)
                )
                panel.requestedCenter(panel.viewerController.nodeId)
            }
        }
    }

    MouseArea {
        anchors.fill: parent
        acceptedButtons: Qt.LeftButton | Qt.RightButton | Qt.MiddleButton
        hoverEnabled: true
        preventStealing: true
        onWheel: function(wheel) { wheel.accepted = true }
    }

    MediaViewerSurface {
        id: mediaSurface
        anchors.fill: parent
        appTheme: panel.appTheme
        canvasController: panel.canvasController
        viewerController: panel.viewerController
        expanded: panel.expanded
        showExpand: true
        enabled: panel.pendingAction.length === 0
        surfaceActive: panel.open && panel.panelVisible
        onCloseRequested: panel.requestCloseAnimated()
        onDetachRequested: panel.requestDetachAnimated()
        onExpandRequested: panel.toggleExpanded()
    }
}
