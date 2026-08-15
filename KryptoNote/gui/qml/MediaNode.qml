import QtQuick


Rectangle {
    id: mediaNode
    required property var canvasRoot
    required property var nodeModel
    required property Item contentLayer

    required property var appTheme
    property int nodeId: 0
    required property Item delegateItem
    property string nodeTitle: ""
    property string nodeContent: ""
    property string mediaType: "image"
    property string metaSummary: ""
    property bool isSelected: false
    property bool isHovered: false
    property int textSize: 10
    property real nodeWidth: 220
    property real nodeHeight: 220
    property var tags: []
    property bool thumbnailRequested: false

    anchors.fill: parent
    radius: 4
    color: mediaNode.appTheme.bgNode

    border.width: isHovered ? 1.65 : (isSelected ? 1.5 : 1.1)
    border.color: isSelected ? mediaNode.appTheme.accentMain : (isHovered ? mediaNode.appTheme.accentMain : mediaNode.appTheme.borderDefault)

    Behavior on border.color { ColorAnimation { duration: 120 } }
    Behavior on border.width { NumberAnimation { duration: 120 } }

    Text {
        id: titleText
        x: 10
        y: 5
        width: parent.width - 20
        text: mediaNode.nodeTitle
        color: mediaNode.appTheme.textMain
        font.family: "Segoe UI Semibold"
        font.pointSize: 12
        font.bold: true
        elide: Text.ElideRight
        maximumLineCount: 1
    }

    Rectangle {
        id: mediaFrame
        x: 10
        y: titleText.y + titleText.contentHeight + 5
        width: parent.width - 20
        height: Math.max(24, parent.height - y - footerLabel.contentHeight
                         - descriptionText.height - 12)
        color: mediaNode.appTheme.bgPanel
        radius: 3
        border.color: mediaNode.appTheme.borderDefault
        border.width: 1
        visible: height > 10

        Image {
            id: thumbImage
            anchors.fill: parent
            anchors.margins: 2
            source: mediaNode.thumbnailRequested
                    ? "image://thumbnails/" + mediaNode.nodeId
                    : ""
            sourceSize.width: Math.min(800, Math.max(256, Math.ceil(mediaNode.nodeWidth * 1.5)))
            sourceSize.height: Math.min(800, Math.max(256, Math.ceil(mediaNode.nodeHeight * 1.5)))
            fillMode: Image.PreserveAspectFit
            asynchronous: true
            smooth: true
            cache: false

            onStatusChanged: {
                if (status === Image.Error) {
                    console.log("QML: Failed to load thumbnail for media node", mediaNode.nodeId);
                }
            }
        }

        Text {
            anchors.centerIn: parent
            text: "No Thumbnail"
            color: mediaNode.appTheme.textMuted
            font.pointSize: 10
            visible: mediaNode.thumbnailRequested
                     && (thumbImage.status === Image.Error || thumbImage.status === Image.Null)
        }
    }

    Text {
        id: descriptionText
        x: 10
        y: mediaFrame.y + mediaFrame.height + 4
        width: parent.width - 20
        height: visible ? Math.min(72, Math.max(18, implicitHeight)) : 0
        text: mediaNode.nodeContent
        color: mediaNode.appTheme.textMain
        font.family: mediaNode.appTheme.textFontFamily
        font.pointSize: mediaNode.textSize > 0 ? mediaNode.textSize : 10
        textFormat: Text.MarkdownText
        wrapMode: Text.WordWrap
        clip: true
        visible: mediaNode.nodeContent.trim().length > 0
    }

    Timer {
        interval: 40 + (mediaNode.nodeId % 8) * 25
        running: !mediaNode.thumbnailRequested
        repeat: false
        onTriggered: mediaNode.thumbnailRequested = true
    }

    Text {
        id: footerLabel
        x: 10
        anchors.bottom: parent.bottom
        anchors.bottomMargin: 5
        width: parent.width - 20
        text: mediaNode.metaSummary.length > 0
              ? mediaNode.metaSummary
              : "[" + mediaNode.mediaType.toUpperCase() + "]"
        color: mediaNode.appTheme.accentMain
        font.family: "Segoe UI"
        font.pointSize: 9
        elide: Text.ElideRight
        maximumLineCount: 1
    }

    TagDots {
        appTheme: mediaNode.appTheme
        id: tagSummary
        z: 2
        anchors.left: mediaFrame.left
        anchors.right: mediaFrame.right
        anchors.bottom: mediaFrame.bottom
        anchors.leftMargin: 6
        anchors.rightMargin: 6
        anchors.bottomMargin: 6
        tags: mediaNode.tags
    }

    property alias isResizeHovered: resizer._isHovered

    ResizeHandle {
        canvasRoot: mediaNode.canvasRoot
        nodeModel: mediaNode.nodeModel
        contentLayer: mediaNode.contentLayer
        appTheme: mediaNode.appTheme
        id: resizer
        nodeId: mediaNode.nodeId
        delegateItem: mediaNode.delegateItem
        anchors.right: parent.right
        anchors.bottom: parent.bottom
    }
}
