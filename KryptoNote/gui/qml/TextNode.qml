import QtQuick


Rectangle {
    id: textNode
    required property var canvasRoot
    required property var nodeModel
    required property Item contentLayer

    required property var appTheme
    property int nodeId: 0
    required property Item delegateItem
    property string nodeTitle: ""
    property string nodeContent: ""
    property bool isSelected: false
    property bool isHovered: false
    property int titleSize: 14
    property int textSize: 12
    property real nodeWidth: 200
    property real nodeHeight: 150
    property real canvasScale: 1.0
    property var tags: []
    property real lodAmount: nodeTitle.length > 0
                             ? Math.max(0.0, Math.min(1.0, (0.43 - canvasScale) / 0.12))
                             : 0.0
    property bool lodBeacon: lodAmount > 0.02

    anchors.fill: parent
    radius: 4
    color: textNode.appTheme.bgNode

    border.width: lodBeacon
                  ? Math.max(1.1, (1.45 + lodAmount * 0.45) / Math.max(canvasScale, 0.12))
                  : (isHovered ? 1.65 : (isSelected ? 1.5 : 1.1))
    border.color: isSelected ? textNode.appTheme.accentMain : (isHovered ? textNode.appTheme.accentMain : textNode.appTheme.borderDefault)

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
        color: textNode.appTheme.accentMain
        font.family: "Segoe UI Semibold"
        font.pointSize: textNode.titleSize > 0 ? textNode.titleSize : 14
        font.bold: true
        wrapMode: Text.WordWrap
        elide: Text.ElideRight
        maximumLineCount: 3
    }

    TagDots {
        appTheme: textNode.appTheme
        id: tagSummary
        z: 2
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        anchors.leftMargin: 10
        anchors.rightMargin: 10
        anchors.bottomMargin: 10
        trailingInset: resizer.visible ? resizer.width : 0
        tags: textNode.tags
        opacity: 1.0 - textNode.lodAmount
    }

    Text {
        id: bodyText
        x: 12
        y: titleText.text.length > 0 ? (titleText.y + titleText.contentHeight + 6) : 8
        width: parent.width - 24
        height: Math.max(0, parent.height - y - 8)
        text: textNode.nodeContent
        visible: opacity > 0.01
        opacity: 1.0 - textNode.lodAmount
        color: textNode.appTheme.textMain
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
        color: textNode.appTheme.accentMain
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
        canvasRoot: textNode.canvasRoot
        nodeModel: textNode.nodeModel
        contentLayer: textNode.contentLayer
        appTheme: textNode.appTheme
        id: resizer
        nodeId: textNode.nodeId
        delegateItem: textNode.delegateItem
        anchors.right: parent.right
        anchors.bottom: parent.bottom
    }
}
