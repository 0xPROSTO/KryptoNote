pragma ComponentBehavior: Bound

import QtQuick

FocusScope {
    id: windowRoot

    // Reuse the same QObject contract as the embedded canvas. This avoids
    // QVariant-map conversion for detached QQuickView windows on Linux.
    // qmllint disable unqualified
    property var canvasRuntime: canvasRuntimeContext
    // qmllint enable unqualified
    readonly property var appTheme: canvasRuntime ? canvasRuntime.appTheme : null
    readonly property var canvasController: canvasRuntime
            ? canvasRuntime.canvasController : null
    readonly property var viewerController: canvasRuntime
            ? canvasRuntime.viewerController : null

    signal applicationCloseRequested()

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
        onApplicationCloseRequested: {
            windowRoot.viewerController.close_viewer()
            windowRoot.applicationCloseRequested()
        }
        onExpandRequested: {}
    }
}
