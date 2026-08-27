import QtQuick

Item {
    id: deleteAnimation
    required property var canvasController
    required property var appTheme
    property Item targetItem
    property int nodeId: 0
    property bool deleting: false
    property real progress: 0.0

    onDeletingChanged: {
        if (deleting) {
            deletionOpacityAnim.start()
            deletionProgressAnim.start()
        } else {
            deletionOpacityAnim.stop()
            deletionProgressAnim.stop()
            progress = 0.0
            if (targetItem) {
                targetItem.opacity = 1.0
            }
        }
    }

    Rectangle {
        anchors.fill: parent
        radius: 4
        z: 100
        visible: deleteAnimation.deleting
        color: {
            if (!deleteAnimation.deleting) return "transparent"
            var p = deleteAnimation.progress
            var alpha = p < 0.33 ? (p / 0.33) * 0.7 : 0.7 * (1.0 - (p - 0.33) / 0.67)
            var danger = deleteAnimation.appTheme.dangerHover
            return Qt.rgba(danger.r, danger.g, danger.b, alpha)
        }
    }

    NumberAnimation {
        id: deletionOpacityAnim
        target: deleteAnimation.targetItem
        property: "opacity"
        from: 1.0
        to: 0.0
        duration: deleteAnimation.appTheme.durationPanel
        onFinished: deleteAnimation.canvasController.perform_delete(deleteAnimation.nodeId)
    }

    NumberAnimation {
        id: deletionProgressAnim
        target: deleteAnimation
        property: "progress"
        from: 0.0
        to: 1.0
        duration: deleteAnimation.appTheme.durationPanel
    }
}
