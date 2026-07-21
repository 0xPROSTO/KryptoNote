pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls.Basic

ComboBox {
    id: combo

    required property var appTheme
    property var fontSizes: []
    property bool reveal: false

    width: 72
    height: 28
    model: fontSizes
    opacity: reveal || hovered || popup.visible ? 1.0 : 0.0
    enabled: opacity > 0.05
    displayText: currentValue + "pt"
    font.pointSize: 10

    background: Rectangle {
        radius: 6
        color: combo.appTheme.bgInput
        border.width: 1
        border.color: combo.appTheme.borderDefault
    }

    contentItem: Text {
        text: combo.displayText
        color: combo.appTheme.textMain
        font: combo.font
        rightPadding: 14
        horizontalAlignment: Text.AlignHCenter
        verticalAlignment: Text.AlignVCenter
    }

    indicator: Canvas {
        width: 10
        height: 7
        x: combo.width - width - 8
        y: (combo.height - height) / 2 + 1
        onPaint: {
            var ctx = getContext("2d")
            ctx.reset()
            ctx.strokeStyle = combo.appTheme.textDim
            ctx.lineWidth = 1.7
            ctx.lineCap = "round"
            ctx.lineJoin = "round"
            ctx.beginPath()
            ctx.moveTo(1.5, 1.5)
            ctx.lineTo(width / 2, height - 1.5)
            ctx.lineTo(width - 1.5, 1.5)
            ctx.stroke()
        }
    }

    popup.background: Rectangle {
        color: combo.appTheme.bgPopover
        border.width: 1
        border.color: combo.appTheme.borderDefault
    }

    delegate: ItemDelegate {
        id: option
        required property var modelData

        width: combo.width
        height: 26

        contentItem: Text {
            text: option.modelData + "pt"
            color: combo.appTheme.textMain
            font.pointSize: 10
            verticalAlignment: Text.AlignVCenter
        }

        background: Rectangle {
            color: option.highlighted ? combo.appTheme.bgControlHover : combo.appTheme.bgPopover
        }
    }

    Behavior on opacity { NumberAnimation { duration: 130 } }
}
