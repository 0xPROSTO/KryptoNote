pragma ComponentBehavior: Bound

import QtQuick

FocusScope {
    id: windowRoot

    required property var appTheme
    required property var canvasController
    required property var viewerController

    focus: true

    function commitPendingMediaEdits() {
        return mediaSurface.commitPendingEdits()
    }

    function promptDescriptionGuard(action) {
        if (!viewerController.descriptionDirty) return false
        mediaSurface.openDescriptionGuard(action)
        return true
    }

    MediaViewerSurface {
        id: mediaSurface
        anchors.fill: parent
        appTheme: windowRoot.appTheme
        canvasController: windowRoot.canvasController
        viewerController: windowRoot.viewerController
        expanded: false
        showExpand: false
        surfaceActive: windowRoot.viewerController.active
                       && windowRoot.viewerController.detached
        onCloseRequested: windowRoot.viewerController.close_viewer()
        onExpandRequested: {}
    }
}
