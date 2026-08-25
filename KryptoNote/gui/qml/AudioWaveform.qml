import QtQuick

Item {
    id: waveformRoot
    required property var appTheme
    property var waveform: []
    property real progress: 0.0
    property real playbackDuration: 0.0
    property bool playing: false
    property real visualProgress: 0.0
    property real anchorProgress: 0.0
    property double anchorTime: 0
    readonly property var displayWaveform: normalizeWaveform(waveform)
    signal seekRequested(real fraction)

    implicitHeight: 54
    activeFocusOnTab: true
    Accessible.role: Accessible.Slider
    Accessible.name: "Audio position"
    Accessible.description: "Activate and use the arrow keys to seek"

    function clampedProgress(value) {
        var number = Number(value)
        return isNaN(number) ? 0 : Math.max(0, Math.min(1, number))
    }

    function percentile(sortedValues, fraction) {
        if (sortedValues.length === 0) return 0
        var position = Math.max(
            0,
            Math.min(sortedValues.length - 1,
                     fraction * (sortedValues.length - 1))
        )
        var lower = Math.floor(position)
        var upper = Math.ceil(position)
        if (lower === upper) return sortedValues[lower]
        var amount = position - lower
        return sortedValues[lower] * (1 - amount)
                + sortedValues[upper] * amount
    }

    function normalizeWaveform(values) {
        var source = values || []
        var clean = []
        var positive = []
        for (var index = 0; index < source.length; ++index) {
            var value = Number(source[index])
            value = isNaN(value) ? 0 : Math.max(0, Math.min(1, value))
            clean.push(value)
            if (value > 0.00001) positive.push(value)
        }
        if (positive.length === 0) return clean
        positive.sort(function(left, right) { return left - right })
        var low = percentile(positive, 0.10)
        var high = percentile(positive, 0.95)
        if (high - low <= Math.max(0.002, high * 0.01)) {
            return clean.map(function(value) { return value > 0 ? 0.62 : 0.04 })
        }
        var spread = Math.max(high - low, high * 0.12, 0.01)
        var floor = Math.max(0, low - spread * 0.25)
        var denominator = Math.max(0.00001, high - floor)
        return clean.map(function(value) {
            if (value <= 0.00001) return 0.04
            var normalized = Math.max(0, Math.min(1, (value - floor) / denominator))
            return 0.08 + 0.92 * Math.pow(normalized, 0.82)
        })
    }

    function synchronizeProgress(force) {
        var next = clampedProgress(progress)
        var duration = Math.max(0, Number(playbackDuration) || 0)
        var driftMilliseconds = Math.abs(next - visualProgress) * duration
        if (force || !playing || duration <= 0 || driftMilliseconds > 750) {
            visualProgress = next
        } else {
            visualProgress = clampedProgress(
                visualProgress + (next - visualProgress) * 0.12
            )
        }
        anchorProgress = visualProgress
        anchorTime = Date.now()
    }

    function drawBars(context, canvasWidth, canvasHeight, values,
                      fillColor, alpha) {
        var count = values.length
        if (count <= 0) return
        var slotWidth = canvasWidth / count
        var gap = Math.max(1, slotWidth * 0.30)
        var barWidth = Math.max(1, slotWidth - gap)
        var center = canvasHeight / 2
        context.fillStyle = fillColor
        context.globalAlpha = alpha
        for (var index = 0; index < count; ++index) {
            var barHeight = Math.max(3, values[index] * (canvasHeight - 6))
            var x = index * slotWidth + gap / 2
            context.fillRect(
                x,
                center - barHeight / 2,
                barWidth,
                barHeight
            )
        }
        context.globalAlpha = 1
    }

    function requestWaveformPaint() {
        neutralBars.requestPaint()
        playedBars.requestPaint()
    }

    FrameAnimation {
        running: waveformRoot.playing
                 && waveformRoot.playbackDuration > 0
                 && waveformRoot.visualProgress < 1
        onTriggered: {
            var elapsedMilliseconds = Math.max(
                0, Date.now() - waveformRoot.anchorTime
            )
            waveformRoot.visualProgress = waveformRoot.clampedProgress(
                waveformRoot.anchorProgress
                + elapsedMilliseconds / waveformRoot.playbackDuration
            )
        }
    }

    Item {
        id: barsLayer
        anchors.fill: parent
        opacity: waveformRoot.enabled ? 1.0 : 0.45
        readonly property int barCount:
            (waveformRoot.displayWaveform || []).length
        readonly property real slotWidth:
            barCount > 0 ? width / barCount : 0
        readonly property real slotGap:
            barCount > 0 ? Math.max(1, slotWidth * 0.30) : 0
        readonly property real barWidth:
            barCount > 0 ? Math.max(1, slotWidth - slotGap) : 0
        readonly property real playedWidth: Math.max(
            0, Math.min(width, width * waveformRoot.visualProgress)
        )
        readonly property real solidPlayedWidth: Math.floor(playedWidth)
        readonly property real edgeOpacity:
            playedWidth - solidPlayedWidth
        readonly property int edgeBarIndex: barCount > 0
            ? Math.min(
                barCount - 1,
                Math.max(0, Math.floor(solidPlayedWidth / slotWidth))
            ) : 0
        readonly property real edgeSlotOffset: barCount > 0
            ? solidPlayedWidth - edgeBarIndex * slotWidth : 0
        readonly property bool edgeCoversBar:
            barCount > 0
            && solidPlayedWidth < width
            && edgeSlotOffset >= slotGap / 2
            && edgeSlotOffset < slotGap / 2 + barWidth
        readonly property real edgeBarValue:
            barCount > 0
            ? Number(waveformRoot.displayWaveform[edgeBarIndex]) || 0
            : 0

        Canvas {
            id: neutralBars
            anchors.fill: parent
            antialiasing: true

            onPaint: {
                var context = getContext("2d")
                context.clearRect(0, 0, width, height)
                waveformRoot.drawBars(
                    context,
                    width,
                    height,
                    waveformRoot.displayWaveform || [],
                    waveformRoot.appTheme.textDim,
                    0.58
                )
            }
        }

        Item {
            id: playedClip
            anchors.left: parent.left
            anchors.top: parent.top
            anchors.bottom: parent.bottom
            width: barsLayer.solidPlayedWidth
            clip: true

            Canvas {
                id: playedBars
                width: barsLayer.width
                height: barsLayer.height
                antialiasing: true

                onPaint: {
                    var context = getContext("2d")
                    context.clearRect(0, 0, width, height)
                    waveformRoot.drawBars(
                        context,
                        width,
                        height,
                        waveformRoot.displayWaveform || [],
                        waveformRoot.appTheme.accentMain,
                        1.0
                    )
                }
            }
        }

        Rectangle {
            id: fractionalPlayedEdge
            x: barsLayer.solidPlayedWidth
            y: (parent.height - height) / 2
            width: Math.min(1, Math.max(0, parent.width - x))
            height: Math.max(
                3, barsLayer.edgeBarValue * (parent.height - 6)
            )
            color: waveformRoot.appTheme.accentMain
            opacity: barsLayer.edgeOpacity
            visible: barsLayer.edgeCoversBar && opacity > 0.001
        }
    }

    Connections {
        target: waveformRoot.appTheme
        function onPaletteChanged() {
            waveformRoot.requestWaveformPaint()
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
        id: waveformPointer
        anchors.fill: parent
        enabled: waveformRoot.enabled
        hoverEnabled: true
        preventStealing: true
        acceptedButtons: Qt.LeftButton
        cursorShape: Qt.PointingHandCursor
        onPressed: function(mouse) {
            mouse.accepted = true
            waveformRoot.seekRequested(Math.max(0, Math.min(1, mouse.x / width)))
        }
        onPositionChanged: function(mouse) {
            if (pressed) {
                mouse.accepted = true
                waveformRoot.seekRequested(Math.max(0, Math.min(1, mouse.x / width)))
            }
        }
    }

    Keys.onPressed: function(event) {
        if (!waveformRoot.enabled) return
        if (event.key === Qt.Key_Left) {
            waveformRoot.seekRequested(Math.max(0, waveformRoot.visualProgress - 0.05))
            event.accepted = true
        } else if (event.key === Qt.Key_Right) {
            waveformRoot.seekRequested(Math.min(1, waveformRoot.visualProgress + 0.05))
            event.accepted = true
        }
    }

    onProgressChanged: synchronizeProgress(false)
    onPlayingChanged: synchronizeProgress(true)
    onPlaybackDurationChanged: synchronizeProgress(true)
    onDisplayWaveformChanged: requestWaveformPaint()
    onWidthChanged: requestWaveformPaint()
    onHeightChanged: requestWaveformPaint()
    Component.onCompleted: {
        synchronizeProgress(true)
        requestWaveformPaint()
    }
}
