pragma ComponentBehavior: Bound
import QtQuick

Item {
    id: connectionLayer
    required property var viewportModel
    required property var canvasRoot
    required property var canvasController
    required property var appTheme

    Repeater {
        model: connectionLayer.viewportModel
        delegate: Connection {
            canvasRoot: connectionLayer.canvasRoot
            canvasController: connectionLayer.canvasController
            appTheme: connectionLayer.appTheme
        }
    }
}
