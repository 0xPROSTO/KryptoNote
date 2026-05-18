import QtQuick

Item {
    Repeater {
        model: connectionModel
        delegate: Connection {}
    }
}
