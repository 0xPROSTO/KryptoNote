pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls.Basic

ToolButton {
    id: control

    required property var appTheme
    required property url iconSource
    property bool confirm: false
    property bool destructive: false
    property bool compact: false
    property string toolTipText: ""

    width: 108
    height: 30
    hoverEnabled: true
    focusPolicy: Qt.TabFocus
    display: compact ? AbstractButton.IconOnly : AbstractButton.TextBesideIcon
    spacing: compact ? 0 : 6
    font.family: confirm ? "Segoe UI Semibold" : "Segoe UI"
    font.pointSize: 9
    opacity: enabled ? 1.0 : 0.85
    icon.source: iconSource
    icon.width: 14
    icon.height: 14
    icon.color: !enabled ? control.appTheme.textDim
                : confirm ? control.appTheme.btnApplyText
                : destructive ? control.appTheme.btnCancelText
                : hovered || visualFocus ? control.appTheme.textMain
                : control.appTheme.textDim
    palette.buttonText: !enabled ? control.appTheme.textDim
                         : confirm ? control.appTheme.btnApplyText
                         : destructive ? control.appTheme.btnCancelText
                         : control.appTheme.textMain
    scale: down ? 0.97 : 1.0

    background: Rectangle {
        radius: 6
        color: !control.enabled ? control.appTheme.bgNode
             : control.confirm ? (control.down ? control.appTheme.successHover
                                  : control.hovered ? control.appTheme.btnApplyHover
                                  : control.appTheme.btnApply)
             : control.destructive ? (control.down || control.hovered
                                      ? control.appTheme.btnCancelHover
                                      : control.appTheme.btnCancel)
             : control.down ? control.appTheme.whiteAlpha15
             : control.hovered ? control.appTheme.whiteAlpha10
             : control.appTheme.bgNode
        border.width: control.visualFocus ? 1.5 : 1
        border.color: control.visualFocus ? control.appTheme.accentMain
                    : control.confirm ? control.appTheme.btnApplyBorder
                    : control.destructive ? control.appTheme.btnCancelBorder
                    : control.appTheme.borderDefault
        Behavior on color { ColorAnimation { duration: 140 } }
    }

    Behavior on opacity { NumberAnimation { duration: 140 } }
    Behavior on scale { NumberAnimation { duration: 80 } }
    Accessible.name: toolTipText.length > 0 ? toolTipText : text

    ThemedToolTip {
        appTheme: control.appTheme
        visible: control.hovered && control.toolTipText.length > 0
        text: control.toolTipText
        delay: 450
    }
}
