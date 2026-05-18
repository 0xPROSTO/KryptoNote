import QtQuick


Rectangle {
    id: mediaNode

    property int nodeId: 0
    property string nodeTitle: ""
    property string mediaType: "image"
    property string metaSummary: ""
    property bool isSelected: false
    property bool isHovered: false
    property real nodeWidth: 220
    property real nodeHeight: 220

    anchors.fill: parent
    radius: 4
    color: AppTheme.bgNode

    border.width: isHovered ? 1.65 : (isSelected ? 1.5 : 1.1)
    border.color: isSelected ? AppTheme.accentMain : (isHovered ? AppTheme.accentMain : AppTheme.borderDefault)

    Behavior on border.color { ColorAnimation { duration: 120 } }
    Behavior on border.width { NumberAnimation { duration: 120 } }

    Text {
        id: titleText
        x: 10
        y: 5
        width: parent.width - 20
        text: mediaNode.nodeTitle
        color: AppTheme.textMain
        font.family: "Segoe UI Semibold"
        font.pointSize: 12
        font.bold: true
        elide: Text.ElideRight
        maximumLineCount: 1
    }

    Rectangle {
        x: 10
        y: titleText.y + titleText.contentHeight + 5
        width: parent.width - 20
        height: parent.height - y - footerLabel.contentHeight - 10
        color: "#1e1f22"
        radius: 3
        border.color: "#333333"
        border.width: 1
        visible: height > 10

        Image {
            id: thumbImage
            anchors.fill: parent
            anchors.margins: 2
            source: "image://thumbnails/" + mediaNode.nodeId
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
            color: AppTheme.textMuted
            font.pointSize: 10
            visible: thumbImage.status === Image.Error || thumbImage.status === Image.Null
        }
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
        color: AppTheme.accentMain
        font.family: "Segoe UI"
        font.pointSize: 9
        elide: Text.ElideRight
        maximumLineCount: 1
    }

    property alias isResizeHovered: resizer._isHovered

    ResizeHandle {
        id: resizer
        nodeId: mediaNode.nodeId
        anchors.right: parent.right
        anchors.bottom: parent.bottom
    }
}
