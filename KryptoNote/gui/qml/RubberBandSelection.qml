import QtQuick

Rectangle {
    id: rubberBand
    required property var nodeModel
    required property var appTheme
    visible: false
    color: "transparent"
    border.color: rubberBand.appTheme ? rubberBand.appTheme.accentMain : "#e6158b"
    border.width: 1
    opacity: 0.4
    z: 100

    property point start: Qt.point(0, 0)

    Rectangle {
        anchors.fill: parent
        color: rubberBand.appTheme ? rubberBand.appTheme.accentMain : "#e6158b"
        opacity: 0.08
    }

    function begin(mouseX, mouseY) {
        start = Qt.point(mouseX, mouseY)
        x = mouseX
        y = mouseY
        width = 0
        height = 0
        visible = true
    }

    function updateBand(mouseX, mouseY) {
        x = Math.min(start.x, mouseX)
        y = Math.min(start.y, mouseY)
        width = Math.abs(mouseX - start.x)
        height = Math.abs(mouseY - start.y)
    }

    function finishSelection(contentLayer, contentScale) {
        var rx1 = (x - contentLayer.x) / contentScale
        var ry1 = (y - contentLayer.y) / contentScale
        var rx2 = ((x + width) - contentLayer.x) / contentScale
        var ry2 = ((y + height) - contentLayer.y) / contentScale
        var selected = rubberBand.nodeModel.get_nodes_in_rect(rx1, ry1, rx2, ry2)
        rubberBand.nodeModel.add_selection(selected)
        visible = false
    }
}
