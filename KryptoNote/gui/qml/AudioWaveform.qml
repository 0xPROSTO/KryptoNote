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
    readonly property var displayWaveform:
            buildDetailedContour(normalizeWaveform(waveform))
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
        var low = percentile(positive, 0.05)
        var high = percentile(positive, 0.98)
        if (high - low <= Math.max(0.002, high * 0.01)) {
            return clean.map(function(value) { return value > 0 ? 0.5 : 0 })
        }
        var spread = Math.max(high - low, high * 0.12, 0.01)
        var floor = Math.max(0, low - spread * 0.15)
        var denominator = Math.max(0.00001, high - floor)
        return clean.map(function(value) {
            if (value <= 0.00001) return 0
            var normalized = Math.max(0, Math.min(1, (value - floor) / denominator))
            return Math.pow(normalized, 1.08)
        })
    }

    function buildDetailedContour(values) {
        var source = values || []
        if (source.length < 2) return source

        var toothPattern = [0.12, -0.08, 0.06, -0.13, 0.10, -0.05]
        var subdivisions = toothPattern.length
        var detailed = [source[0]]
        for (var index = 1; index < source.length; ++index) {
            var previous = source[index - 1]
            var current = source[index]
            var detailWeight = 0.35 + 0.65 * Math.max(previous, current)
            for (var step = 1; step < subdivisions; ++step) {
                var amount = step / subdivisions
                var base = previous * (1 - amount) + current * amount
                var patternIndex = (index * 3 + step) % toothPattern.length
                detailed.push(Math.max(0, Math.min(
                    1,
                    base * (1 + toothPattern[patternIndex] * detailWeight)
                )))
            }
            detailed.push(current)
        }
        return detailed
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

    function drawEnvelope(context, canvasWidth, canvasHeight, values,
                          fillColor, alpha) {
        var count = values.length
        if (count <= 0) return
        var center = canvasHeight / 2
        var halfHeight = Math.max(
            1,
            Math.min((canvasHeight - 4) / 2, canvasHeight * 0.38)
        )
        context.fillStyle = fillColor
        context.globalAlpha = alpha
        var amplitudes = []
        for (var index = 0; index < count; ++index) {
            amplitudes.push(Math.max(0.35, values[index] * halfHeight))
        }
        var xStep = count > 1 ? canvasWidth / (count - 1) : canvasWidth
        context.beginPath()
        context.moveTo(0, center - amplitudes[0])
        for (var topIndex = 1; topIndex < count; ++topIndex)
            context.lineTo(topIndex * xStep, center - amplitudes[topIndex])
        for (var bottomIndex = count - 1; bottomIndex >= 0; --bottomIndex)
            context.lineTo(bottomIndex * xStep, center + amplitudes[bottomIndex])
        context.closePath()
        context.fill()
        context.globalAlpha = 1
    }

    function requestWaveformPaint() {
        neutralWaveform.requestPaint()
        playedWaveform.requestPaint()
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
        readonly property real playedWidth: Math.max(
            0, Math.min(width, width * waveformRoot.visualProgress)
        )

        Canvas {
            id: neutralWaveform
            anchors.fill: parent
            antialiasing: true

            onPaint: {
                var context = getContext("2d")
                context.clearRect(0, 0, width, height)
                waveformRoot.drawEnvelope(
                    context,
                    width,
                    height,
                    waveformRoot.displayWaveform || [],
                    waveformRoot.appTheme.textDim,
                    0.68
                )
            }
        }

        Item {
            id: playedClip
            anchors.left: parent.left
            anchors.top: parent.top
            anchors.bottom: parent.bottom
            width: barsLayer.playedWidth
            clip: true

            Canvas {
                id: playedWaveform
                width: barsLayer.width
                height: barsLayer.height
                antialiasing: true

                onPaint: {
                    var context = getContext("2d")
                    context.clearRect(0, 0, width, height)
                    waveformRoot.drawEnvelope(
                        context,
                        width,
                        height,
                        waveformRoot.displayWaveform || [],
                        waveformRoot.appTheme.accentMain,
                        0.62
                    )
                }
            }
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
