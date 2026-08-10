pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls.Basic

ToolButton {
    id: control

    required property var appTheme
    required property url iconSource
    required property string accessibleName
    property bool emphasized: false
    property bool destructive: false

    width: 34
    height: 34
    hoverEnabled: true
    focusPolicy: Qt.TabFocus
    display: AbstractButton.IconOnly
    icon.source: iconSource
    icon.width: 16
    icon.height: 16
    icon.color: !enabled ? control.appTheme.textDisabled
                : destructive && (hovered || visualFocus)
                  ? control.appTheme.btnCancelText
                : emphasized || hovered || visualFocus
                  ? control.appTheme.textMain
                : control.appTheme.textDim
    opacity: enabled ? 1.0 : 0.48
    scale: down ? 0.96 : 1.0

    background: Rectangle {
        radius: 7
        color: !control.enabled ? "transparent"
             : control.down ? control.appTheme.whiteAlpha15
             : control.hovered ? control.appTheme.whiteAlpha10
             : control.emphasized ? control.appTheme.whiteAlpha05
             : "transparent"
        border.width: control.visualFocus ? 1 : 0
        border.color: control.appTheme.accentMain
        Behavior on color { ColorAnimation { duration: 120 } }
    }

    Behavior on scale { NumberAnimation { duration: 80 } }
    Accessible.name: accessibleName
    ToolTip.visible: hovered && accessibleName.length > 0
    ToolTip.text: accessibleName
    ToolTip.delay: 450
}
