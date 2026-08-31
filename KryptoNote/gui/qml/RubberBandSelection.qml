import QtQuick

Rectangle {
    id: rubberBand
    required property var nodeModel
    required property var appTheme
    required property var viewport
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

    function finishSelection() {
        if (!rubberBand.viewport) {
            visible = false
            return
        }
        var first = rubberBand.viewport.screenToRender(x, y)
        var second = rubberBand.viewport.screenToRender(x + width, y + height)
        var rx1 = first.x
        var ry1 = first.y
        var rx2 = second.x
        var ry2 = second.y
        var selected = rubberBand.nodeModel.get_nodes_in_render_rect(
            rubberBand.viewport.renderOriginX,
            rubberBand.viewport.renderOriginY,
            rx1,
            ry1,
            rx2,
            ry2
        )
        rubberBand.nodeModel.add_selection(selected)
        visible = false
    }
}
