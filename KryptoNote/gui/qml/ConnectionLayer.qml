pragma ComponentBehavior: Bound
import QtQuick

Item {
    id: connectionLayer
    required property var viewportModel
    required property var canvasRoot
    required property var canvasController
    required property var appTheme
    property var pendingRevealIds: []
    signal revealConsumed(int connectionId)

    Repeater {
        model: connectionLayer.viewportModel
        delegate: Connection {
            canvasRoot: connectionLayer.canvasRoot
            canvasController: connectionLayer.canvasController
            appTheme: connectionLayer.appTheme
            revealRequested: connectionLayer.pendingRevealIds.indexOf(
                model.connId
            ) !== -1
            onRevealAccepted: function(connectionId) {
                connectionLayer.revealConsumed(connectionId)
            }
        }
    }
}
