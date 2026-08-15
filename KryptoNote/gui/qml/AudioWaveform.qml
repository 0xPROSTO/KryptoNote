import QtQuick

Item {
    id: waveformRoot
    required property var appTheme
    property var waveform: []
    property real progress: 0.0
    signal seekRequested(real fraction)

    implicitHeight: 54
    activeFocusOnTab: true
    Accessible.role: Accessible.Slider
    Accessible.name: "Audio position"
    Accessible.description: "Activate and use the arrow keys to seek"

    Canvas {
        id: bars
        anchors.fill: parent
        opacity: waveformRoot.enabled ? 1.0 : 0.45
        onPaint: {
            var ctx = getContext("2d")
            ctx.clearRect(0, 0, width, height)
            var values = waveformRoot.waveform || []
            var count = values.length > 0 ? values.length : 96
            var gap = Math.max(1, width / count * 0.28)
            var barWidth = Math.max(1, width / count - gap)
            var center = height / 2
            for (var index = 0; index < count; index++) {
                var value = values.length > 0 ? Number(values[index]) : 0.12
                value = Math.max(0.04, Math.min(1.0, isNaN(value) ? 0.04 : value))
                var barHeight = Math.max(3, value * (height - 8))
                var x = index * width / count
                var played = (index + 0.5) / count <= waveformRoot.progress
                ctx.fillStyle = played
                        ? waveformRoot.appTheme.accentMain
                        : waveformRoot.appTheme.textDim
                ctx.fillRect(x, center - barHeight / 2, barWidth, barHeight)
            }
        }
    }

    Rectangle {
        anchors.fill: parent
        color: "transparent"
        border.width: waveformRoot.activeFocus ? 1 : 0
        border.color: waveformRoot.appTheme.accentMain
        radius: 4
    }

    MouseArea {
        anchors.fill: parent
        enabled: waveformRoot.enabled
        hoverEnabled: true
        cursorShape: Qt.PointingHandCursor
        onPressed: function(mouse) {
            waveformRoot.forceActiveFocus()
            waveformRoot.seekRequested(Math.max(0, Math.min(1, mouse.x / width)))
        }
        onPositionChanged: function(mouse) {
            if (pressed)
                waveformRoot.seekRequested(Math.max(0, Math.min(1, mouse.x / width)))
        }
    }

    Keys.onPressed: function(event) {
        if (!waveformRoot.enabled) return
        if (event.key === Qt.Key_Left) {
            waveformRoot.seekRequested(Math.max(0, waveformRoot.progress - 0.05))
            event.accepted = true
        } else if (event.key === Qt.Key_Right) {
            waveformRoot.seekRequested(Math.min(1, waveformRoot.progress + 0.05))
            event.accepted = true
        }
    }

    onWaveformChanged: bars.requestPaint()
    onProgressChanged: bars.requestPaint()
    onEnabledChanged: bars.requestPaint()
    onWidthChanged: bars.requestPaint()
    onHeightChanged: bars.requestPaint()
}
