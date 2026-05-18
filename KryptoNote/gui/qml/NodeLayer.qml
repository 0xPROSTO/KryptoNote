import QtQuick

Item {
    Repeater {
        model: nodeModel
        delegate: NodeDelegate {}
    }
}
