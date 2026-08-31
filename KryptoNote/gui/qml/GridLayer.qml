import QtQuick

ShaderEffect {
    id: grid
    required property var appTheme
    property vector2d offset: Qt.vector2d(0, 0)
    property vector2d gridPhase: Qt.vector2d(0, 0)
    property vector2d mainGridPhase: Qt.vector2d(0, 0)
    property real viewScale: 1.0
    property vector2d viewportSize: Qt.vector2d(width, height)
    property real gridSize: 100.0
    property real gridMain: 500.0

    property color gridColor: grid.appTheme.gridMain
    property color backgroundColor: "transparent"

    visible: grid.appTheme.gridEnabled
    opacity: grid.appTheme.gridOpacity
    fragmentShader: "grid.frag.qsb"
}
