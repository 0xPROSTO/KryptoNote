pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls.Basic


ToolTip {
    id: control

    required property var appTheme

    leftPadding: 8
    rightPadding: 8
    topPadding: 5
    bottomPadding: 5
    font.family: control.appTheme.textFontFamily
    font.pointSize: 9

    contentItem: Text {
        text: control.text
        color: control.appTheme.textMain
        font: control.font
        wrapMode: Text.Wrap
    }

    background: Rectangle {
        radius: 4
        color: control.appTheme.bgPopover
        border.width: 1
        border.color: control.appTheme.borderDefault
    }
}
