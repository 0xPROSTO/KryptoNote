import QtQuick


Rectangle {
    id: textNode

    property int nodeId: 0
    property string nodeTitle: ""
    property string nodeContent: ""
    property bool isSelected: false
    property bool isHovered: false
    property int titleSize: 14
    property int textSize: 12
    property real nodeWidth: 200
    property real nodeHeight: 150
    property real canvasScale: 1.0
    property real lodAmount: nodeTitle.length > 0
                             ? Math.max(0.0, Math.min(1.0, (0.43 - canvasScale) / 0.12))
                             : 0.0
    property bool lodBeacon: lodAmount > 0.02

    anchors.fill: parent
    radius: 4
    color: AppTheme.bgNode

    border.width: lodBeacon
                  ? Math.max(1.1, (1.45 + lodAmount * 0.45) / Math.max(canvasScale, 0.12))
                  : (isHovered ? 1.65 : (isSelected ? 1.5 : 1.1))
    border.color: isSelected ? AppTheme.accentMain : (isHovered ? AppTheme.accentMain : AppTheme.borderDefault)

    Behavior on border.color { ColorAnimation { duration: 120 } }
    Behavior on border.width { NumberAnimation { duration: 120 } }

    Text {
        id: titleText
        x: 12
        y: 8
        width: parent.width - 24
        text: textNode.nodeTitle
        visible: opacity > 0.01
        opacity: 1.0 - textNode.lodAmount
        color: AppTheme.accentMain
        font.family: "Segoe UI Semibold"
        font.pointSize: textNode.titleSize > 0 ? textNode.titleSize : 14
        font.bold: true
        wrapMode: Text.WordWrap
        elide: Text.ElideRight
        maximumLineCount: 3
    }

    Text {
        id: bodyText
        x: 12
        y: titleText.text.length > 0 ? (titleText.y + titleText.contentHeight + 6) : 8
        width: parent.width - 24
        height: parent.height - y - 4
        text: textNode.nodeContent
        visible: opacity > 0.01
        opacity: 1.0 - textNode.lodAmount
        color: AppTheme.textMain
        font.family: "Segoe UI"
        font.pointSize: textNode.textSize > 0 ? textNode.textSize : 12
        textFormat: Text.MarkdownText
        wrapMode: Text.WordWrap
        clip: true
    }

    Text {
        id: beaconText
        anchors.fill: parent
        anchors.margins: 10
        visible: opacity > 0.01
        opacity: textNode.lodAmount
        text: textNode.nodeTitle
        color: AppTheme.accentMain
        font.family: "Segoe UI Semibold"
        font.bold: true
        font.pointSize: 72
        fontSizeMode: Text.Fit
        minimumPointSize: 8
        horizontalAlignment: Text.AlignLeft
        verticalAlignment: Text.AlignVCenter
        wrapMode: Text.WordWrap
        elide: Text.ElideRight
    }

    property alias isResizeHovered: resizer._isHovered

    ResizeHandle {
        id: resizer
        nodeId: textNode.nodeId
        visible: !textNode.lodBeacon
        anchors.right: parent.right
        anchors.bottom: parent.bottom
    }
}
