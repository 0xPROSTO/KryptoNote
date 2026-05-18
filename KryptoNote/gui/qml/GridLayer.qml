import QtQuick
import QtQuick.Window

ShaderEffect {
    id: grid
    property Item contentLayer
    property real contentScale: 1.0
    property real gridSize: 100.0
    property real gridMain: 500.0

    property vector2d offset: contentLayer ? Qt.vector2d(contentLayer.x, contentLayer.y) : Qt.vector2d(0, 0)
    property real viewScale: contentScale
    property real devicePixelRatio: Screen.devicePixelRatio > 0 ? Screen.devicePixelRatio : 1.0
    property color gridColor: "#252525"
    property color backgroundColor: "transparent"

    fragmentShader: "grid.frag.qsb"
}
