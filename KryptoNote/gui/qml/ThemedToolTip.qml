pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls.Basic


ToolTip {
    id: control

    required property var appTheme
    property real motionOffset: 0

    opacity: 1.0
    scale: 1.0
    transformOrigin: Item.Bottom

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
        transform: Translate { y: control.motionOffset }
    }

    background: Rectangle {
        radius: 4
        color: control.appTheme.bgPopover
        border.width: 1
        border.color: control.appTheme.borderDefault
        transform: Translate { y: control.motionOffset }
    }

    enter: Transition {
        ParallelAnimation {
            NumberAnimation {
                property: "opacity"; from: 0; to: 1
                duration: control.appTheme.durationPress
                easing.type: Easing.OutCubic
            }
            NumberAnimation {
                property: "scale"
                from: control.appTheme.motionEnabled ? 0.985 : 1; to: 1
                duration: control.appTheme.motionEnabled
                          ? control.appTheme.durationPress : 0
                easing.type: Easing.OutCubic
            }
            NumberAnimation {
                target: control; property: "motionOffset"; from: -2; to: 0
                duration: control.appTheme.motionEnabled
                          ? control.appTheme.durationPress : 0
                easing.type: Easing.OutCubic
            }
        }
    }

    exit: Transition {
        ParallelAnimation {
            NumberAnimation {
                property: "opacity"; from: 1; to: 0
                duration: control.appTheme.durationExit
                easing.type: Easing.InCubic
            }
            NumberAnimation {
                property: "scale"; from: 1
                to: control.appTheme.motionEnabled ? 0.99 : 1
                duration: control.appTheme.motionEnabled
                          ? control.appTheme.durationExit : 0
                easing.type: Easing.InCubic
            }
            NumberAnimation {
                target: control; property: "motionOffset"; from: 0; to: -1
                duration: control.appTheme.motionEnabled
                          ? control.appTheme.durationExit : 0
                easing.type: Easing.InCubic
            }
        }
    }
}
