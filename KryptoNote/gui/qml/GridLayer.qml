import QtQuick
import QtQuick.Window

ShaderEffect {
    id: grid
    required property var appTheme
    property Item contentLayer
    property real contentScale: 1.0
    property real gridSize: 100.0
    property real gridMain: 500.0

    property vector2d offset: contentLayer ? Qt.vector2d(contentLayer.x, contentLayer.y) : Qt.vector2d(0, 0)
    property real viewScale: contentScale
    property real devicePixelRatio: Screen.devicePixelRatio > 0 ? Screen.devicePixelRatio : 1.0
    property color gridColor: grid.appTheme.gridMain
    property color backgroundColor: "transparent"

    visible: grid.appTheme.gridEnabled
    opacity: grid.appTheme.gridOpacity
    fragmentShader: "grid.frag.qsb"
}
