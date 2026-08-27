import QtQuick

Item {
    id: badge
    required property var appTheme
    property string line1: ""
    property string line2: ""
    property bool gridActive: false
    property bool active: false
    property real anchorX: 0
    property real anchorY: 0

    property string _displayLine1: ""
    property string _displayLine2: ""
    property bool _displayGridActive: false
    property real _displayAnchorX: 0
    property real _displayAnchorY: 0

    width: badgeRow.implicitWidth + 18
    height: Math.max(28, badgeRow.implicitHeight + 10)
    x: _displayAnchorX - width / 2
    y: _displayAnchorY - height / 2
    opacity: active ? 1 : 0
    visible: opacity > 0.001

    Accessible.ignored: true

    function latchDisplayState() {
        if (line1.length > 0) _displayLine1 = line1
        _displayLine2 = line2
        _displayGridActive = gridActive
        _displayAnchorX = anchorX
        _displayAnchorY = anchorY
    }

    onActiveChanged: {
        if (active) latchDisplayState()
    }
    onLine1Changed: {
        if (active) latchDisplayState()
    }
    onLine2Changed: {
        if (active) latchDisplayState()
    }
    onGridActiveChanged: {
        if (active) latchDisplayState()
    }
    onAnchorXChanged: {
        if (active) _displayAnchorX = anchorX
    }
    onAnchorYChanged: {
        if (active) _displayAnchorY = anchorY
    }

    Rectangle {
        anchors.fill: parent
        radius: 6
        color: badge.appTheme.bgPopover
        border.width: 1
        border.color: badge.appTheme.accentMain
    }

    Row {
        id: badgeRow
        anchors.centerIn: parent
        spacing: 7

        Column {
            spacing: 1

            Text {
                text: badge._displayLine1
                color: badge.appTheme.textMain
                font.family: "Consolas"
                font.pointSize: 8.5
                font.weight: Font.DemiBold
            }

            Text {
                visible: badge._displayLine2.length > 0
                text: badge._displayLine2
                color: badge.appTheme.textMain
                font.family: "Consolas"
                font.pointSize: 8.5
                font.weight: Font.DemiBold
            }
        }

        Rectangle {
            visible: badge._displayGridActive
            width: visible ? gridText.implicitWidth + 10 : 0
            height: 18
            anchors.verticalCenter: parent.verticalCenter
            radius: 5
            color: badge.appTheme.accentLow
            border.width: 1
            border.color: badge.appTheme.accentMain

            Text {
                id: gridText
                anchors.centerIn: parent
                text: "GRID"
                color: badge.appTheme.textAccent
                font.family: "Segoe UI Semibold"
                font.pointSize: 7
                font.weight: Font.Bold
            }
        }
    }

    Behavior on opacity {
        NumberAnimation {
            duration: badge.active
                      ? badge.appTheme.durationState
                      : badge.appTheme.durationExit
            easing.type: badge.active ? Easing.OutCubic : Easing.InCubic
        }
    }

}
