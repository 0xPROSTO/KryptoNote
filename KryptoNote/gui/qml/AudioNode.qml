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
    property real nodeWidth: 260
    property real nodeHeight: 190
    property var tags: []

    anchors.fill: parent
    radius: 4
    color: audioNode.appTheme.bgNode
    border.width: isHovered ? 1.65 : (isSelected ? 1.5 : 1.1)
    border.color: isSelected ? audioNode.appTheme.accentMain
                 : (isHovered ? audioNode.appTheme.accentMain
                              : audioNode.appTheme.borderDefault)

    Text {
        id: titleText
        x: 12
        y: 7
        width: parent.width - 24
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
        y: titleText.y + titleText.contentHeight + 7
        width: parent.width - 20
        height: Math.max(74, waveform.height + 38)
        radius: 6
        color: audioNode.appTheme.bgPanel
        border.width: 1
        border.color: audioNode.appTheme.borderSubtle

        Row {
            id: playbackRow
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.top: parent.top
            anchors.topMargin: 7
            anchors.leftMargin: 7
            anchors.rightMargin: 7
            height: 30
            spacing: 6

            ToolButton {
                id: playButton
                width: 30
                height: 30
                icon.source: audioNode.viewerController.playbackNodeId === audioNode.nodeId
                             && audioNode.viewerController.playing
                             ? "../assets/icons/pause.svg"
                             : "../assets/icons/play.svg"
                icon.width: 16
                icon.height: 16
                icon.color: playButton.visualFocus || playButton.hovered
                            ? audioNode.appTheme.textMain : audioNode.appTheme.textDim
                hoverEnabled: true
                focusPolicy: Qt.TabFocus
                Accessible.name: audioNode.viewerController.playbackNodeId === audioNode.nodeId
                                 && audioNode.viewerController.playing
                                 ? "Pause audio" : "Play audio"
                background: Rectangle {
                    radius: 6
                    color: playButton.down ? audioNode.appTheme.whiteAlpha15
                         : playButton.hovered ? audioNode.appTheme.whiteAlpha10
                         : "transparent"
                    border.width: playButton.visualFocus ? 1 : 0
                    border.color: audioNode.appTheme.accentMain
                }
                onClicked: audioNode.viewerController.toggle_playback_for(audioNode.nodeId)
            }

            Text {
                width: 70
                height: parent.height
                text: audioNode.viewerController.playbackNodeId === audioNode.nodeId
                      ? audioNode.formatTime(audioNode.viewerController.position)
                        + " / " + audioNode.formatTime(audioNode.viewerController.duration)
                      : audioNode.formatTime(audioNode.mediaDuration * 1000)
                color: audioNode.appTheme.textMuted
                font.family: "Segoe UI"
                font.pointSize: 8
                verticalAlignment: Text.AlignVCenter
            }
        }

        AudioWaveform {
            id: waveform
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.leftMargin: 9
            anchors.rightMargin: 9
            anchors.bottom: parent.bottom
            anchors.bottomMargin: 7
            height: 30
            appTheme: audioNode.appTheme
            waveform: audioNode.audioWaveform
            enabled: audioNode.mediaDuration > 0
            progress: audioNode.viewerController.playbackNodeId === audioNode.nodeId
                      && audioNode.viewerController.duration > 0
                      ? audioNode.viewerController.position
                        / audioNode.viewerController.duration : 0
            onSeekRequested: function(fraction) {
                if (audioNode.mediaDuration > 0)
                    audioNode.viewerController.seek_for(
                        audioNode.nodeId,
                        fraction * Math.max(1, audioNode.viewerController.duration)
                    )
            }
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
        y: playerCard.y + playerCard.height + 5
        width: parent.width - 20
        height: visible ? Math.min(58, Math.max(18, implicitHeight)) : 0
        text: audioNode.nodeContent
        color: audioNode.appTheme.textMain
        font.family: audioNode.appTheme.textFontFamily
        font.pointSize: audioNode.textSize > 0 ? audioNode.textSize : 10
        textFormat: Text.MarkdownText
        wrapMode: Text.WordWrap
        clip: true
        visible: audioNode.nodeContent.trim().length > 0
    }

    TagDots {
        appTheme: audioNode.appTheme
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.bottom: footerLabel.top
        anchors.leftMargin: 10
        anchors.rightMargin: 10
        anchors.bottomMargin: 2
        tags: audioNode.tags
    }

    Text {
        id: footerLabel
        x: 10
        anchors.bottom: parent.bottom
        anchors.bottomMargin: 5
        width: parent.width - 20
        text: audioNode.metaSummary.length > 0 ? audioNode.metaSummary : "[AUDIO]"
        color: audioNode.appTheme.accentMain
        font.family: "Segoe UI"
        font.pointSize: 9
        elide: Text.ElideRight
    }

    function formatTime(milliseconds) {
        var total = Math.max(0, Math.floor(Number(milliseconds || 0) / 1000))
        var minutes = Math.floor(total / 60)
        var seconds = total % 60
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
        anchors.right: parent.right
        anchors.bottom: parent.bottom
    }
}
