import QtQuick
import QtQuick.Controls.Basic

Rectangle {
    id: audioNode
    required property var canvasRoot
    required property var nodeModel
    required property Item contentLayer
    required property var appTheme
    required property Item delegateItem
    required property var viewerController
    property int nodeId: 0
    property string nodeTitle: ""
    property string nodeContent: ""
    property string mediaType: "audio"
    property string metaSummary: ""
    property var audioWaveform: []
    property real mediaDuration: 0
    property int textSize: 10
    property bool isSelected: false
    property bool isHovered: false
    property real nodeWidth: 360
    property real nodeHeight: 108
    property var tags: []
    readonly property bool hasDescription: nodeContent.trim().length > 0
    readonly property bool playbackIsCurrent:
            viewerController.playbackNodeId === nodeId
    readonly property real effectiveDuration:
            playbackIsCurrent && viewerController.duration > 0
            ? viewerController.duration : mediaDuration * 1000
    readonly property real compactMinimumHeight:
            108 + (hasDescription ? 24 : 0)
            + (tags && tags.length > 0 ? 24 : 0)

    anchors.fill: parent
    radius: 4
    color: audioNode.appTheme.bgNode
    border.width: isHovered ? 1.65 : (isSelected ? 1.5 : 1.1)
    border.color: isSelected ? audioNode.appTheme.accentMain
                 : (isHovered ? audioNode.appTheme.accentMain
                              : audioNode.appTheme.borderDefault)

    Behavior on border.color { ColorAnimation { duration: 120 } }
    Behavior on border.width { NumberAnimation { duration: 120 } }

    Text {
        id: titleText
        x: 10
        y: 6
        width: parent.width - 20
        text: audioNode.nodeTitle
        color: audioNode.appTheme.textMain
        font.family: "Segoe UI Semibold"
        font.pointSize: 12
        font.bold: true
        elide: Text.ElideRight
        maximumLineCount: 1
    }

    Rectangle {
        id: playerCard
        x: 10
        y: titleText.y + titleText.contentHeight + 5
        width: parent.width - 20
        height: 54
        radius: 6
        color: audioNode.appTheme.bgPanel
        border.width: 1
        border.color: audioNode.appTheme.borderSubtle

        ToolButton {
            id: playButton
            width: 36
            height: 36
            anchors.left: parent.left
            anchors.leftMargin: 8
            anchors.verticalCenter: parent.verticalCenter
            icon.source: audioNode.playbackIsCurrent
                         && audioNode.viewerController.playing
                         ? "../assets/icons/pause.svg"
                         : "../assets/icons/play.svg"
            icon.width: 16
            icon.height: 16
            icon.color: playButton.down
                        ? audioNode.appTheme.textMain
                        : audioNode.appTheme.accentMain
            hoverEnabled: true
            focusPolicy: Qt.TabFocus
            scale: down ? 0.96 : 1
            Accessible.name: audioNode.playbackIsCurrent
                             && audioNode.viewerController.playing
                             ? "Pause audio" : "Play audio"
            background: Rectangle {
                radius: width / 2
                color: playButton.down ? audioNode.appTheme.accentHover
                     : playButton.hovered ? audioNode.appTheme.accentLow
                     : audioNode.appTheme.bgNode
                border.width: playButton.visualFocus ? 1.5 : 1
                border.color: playButton.visualFocus
                              ? audioNode.appTheme.accentMain
                              : audioNode.appTheme.borderDefault
                Behavior on color { ColorAnimation { duration: 100 } }
            }
            Behavior on scale {
                NumberAnimation { duration: 80; easing.type: Easing.OutCubic }
            }
            onClicked: audioNode.viewerController.toggle_playback_for(
                audioNode.nodeId
            )
        }

        AudioWaveform {
            id: waveform
            anchors.left: playButton.right
            anchors.right: parent.right
            anchors.top: parent.top
            anchors.leftMargin: 8
            anchors.rightMargin: 8
            anchors.topMargin: 5
            height: 28
            appTheme: audioNode.appTheme
            waveform: audioNode.audioWaveform
            enabled: audioNode.mediaDuration > 0
            playing: audioNode.playbackIsCurrent
                     && audioNode.viewerController.playing
            playbackDuration: audioNode.effectiveDuration
            progress: audioNode.playbackIsCurrent
                      && audioNode.viewerController.duration > 0
                      ? audioNode.viewerController.position
                        / audioNode.viewerController.duration : 0
            onSeekRequested: function(fraction) {
                if (audioNode.effectiveDuration > 0)
                    audioNode.viewerController.seek_for(
                        audioNode.nodeId,
                        fraction * audioNode.effectiveDuration
                    )
            }
        }

        Text {
            anchors.left: waveform.left
            anchors.right: waveform.right
            anchors.top: waveform.bottom
            height: 16
            text: audioNode.playbackIsCurrent
                  ? audioNode.formatTime(audioNode.viewerController.position)
                    + " / " + audioNode.formatTime(audioNode.effectiveDuration)
                  : audioNode.formatTime(audioNode.effectiveDuration)
            color: audioNode.appTheme.textMuted
            font.family: "Segoe UI"
            font.pointSize: 8
            verticalAlignment: Text.AlignVCenter
        }

        Text {
            anchors.centerIn: waveform
            text: "Waveform unavailable"
            visible: audioNode.audioWaveform.length === 0
                     || audioNode.mediaDuration <= 0
            color: audioNode.appTheme.textDim
            font.family: audioNode.appTheme.textFontFamily
            font.pointSize: 8
        }
    }

    Text {
        id: descriptionText
        x: 10
        y: playerCard.y + playerCard.height + 6
        width: parent.width - 20
        height: audioNode.hasDescription
                ? Math.max(0, Math.min(
                    58,
                    implicitHeight,
                    (tagSummary.visible ? tagSummary.y : footerLabel.y) - y - 4
                ))
                : 0
        text: audioNode.nodeContent
        color: audioNode.appTheme.textMain
        font.family: audioNode.appTheme.textFontFamily
        font.pointSize: audioNode.textSize > 0 ? audioNode.textSize : 10
        textFormat: Text.MarkdownText
        wrapMode: Text.WordWrap
        clip: true
        visible: audioNode.hasDescription && height > 0
    }

    TagDots {
        id: tagSummary
        appTheme: audioNode.appTheme
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.bottom: footerLabel.top
        anchors.leftMargin: 10
        anchors.rightMargin: 10
        anchors.bottomMargin: 4
        tags: audioNode.tags
    }

    Text {
        id: footerLabel
        x: 10
        anchors.bottom: parent.bottom
        anchors.bottomMargin: 4
        width: parent.width - 20
        text: audioNode.metaSummary.length > 0
              ? audioNode.metaSummary : "[AUDIO]"
        color: audioNode.appTheme.accentMain
        font.family: "Segoe UI"
        font.pointSize: 8.5
        elide: Text.ElideRight
        maximumLineCount: 1
    }

    function formatTime(milliseconds) {
        var total = Math.max(0, Math.floor(Number(milliseconds || 0) / 1000))
        var hours = Math.floor(total / 3600)
        var minutes = Math.floor((total % 3600) / 60)
        var seconds = total % 60
        if (hours > 0)
            return hours + ":" + String(minutes).padStart(2, "0")
                    + ":" + String(seconds).padStart(2, "0")
        return minutes + ":" + String(seconds).padStart(2, "0")
    }

    property alias isResizeHovered: resizer._isHovered
    ResizeHandle {
        id: resizer
        canvasRoot: audioNode.canvasRoot
        nodeModel: audioNode.nodeModel
        contentLayer: audioNode.contentLayer
        appTheme: audioNode.appTheme
        nodeId: audioNode.nodeId
        delegateItem: audioNode.delegateItem
        minimumNodeWidth: 260
        minimumNodeHeight: audioNode.compactMinimumHeight
        anchors.right: parent.right
        anchors.bottom: parent.bottom
    }
}
