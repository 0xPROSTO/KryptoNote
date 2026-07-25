pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls.Basic

Popup {
    id: colorPopup
    required property var appTheme
    objectName: "tagColorPopup"
    parent: Overlay.overlay

    readonly property int dialogLayer: 42
    property string dialogTitle: "Tag color"
    property real colorHue: 0
    property real colorSaturation: 0
    property real colorValue: 1
    property color parsedColor: "#ffffff"
    readonly property color selectedColor: Qt.hsva(
        colorHue,
        colorSaturation,
        colorValue,
        1
    )

    signal colorAccepted(color selectedColor)

    z: dialogLayer
    width: Math.min(306, parent && parent.width > 0 ? parent.width - 24 : 306)
    height: Math.min(374, parent && parent.height > 0 ? parent.height - 24 : 374)
    margins: 12
    padding: 0
    modal: true
    dim: true
    focus: true
    closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside

    function colorToHex(nextColor) {
        var text = String(nextColor).toUpperCase()
        if (text.length === 9) return "#" + text.slice(3)
        return text.slice(0, 7)
    }

    function setFromColor(nextColor) {
        parsedColor = nextColor
        var nextHue = parsedColor.hsvHue
        colorHue = nextHue >= 0 ? nextHue : 0
        colorSaturation = parsedColor.hsvSaturation
        colorValue = parsedColor.hsvValue
        hexField.text = colorToHex(parsedColor)
    }

    function applyHexText() {
        var match = /^#?([0-9A-Fa-f]{6})$/.exec(hexField.text.trim())
        if (!match) return false
        parsedColor = "#" + match[1]
        setFromColor(parsedColor)
        return true
    }

    function openForColor(nextColor) {
        setFromColor(nextColor)
        x = Math.round((parent.width - width) / 2)
        y = Math.round((parent.height - height) / 2)
        open()
    }

    onSelectedColorChanged: {
        if (!hexField.activeFocus) {
            hexField.text = colorToHex(selectedColor)
        }
    }

    enter: Transition {
        ParallelAnimation {
            NumberAnimation {
                property: "opacity"
                from: 0
                to: 1
                duration: 150
                easing.type: Easing.OutCubic
            }
            NumberAnimation {
                property: "scale"
                from: 0.98
                to: 1
                duration: 150
                easing.type: Easing.OutCubic
            }
        }
    }

    exit: Transition {
        NumberAnimation {
            property: "opacity"
            from: 1
            to: 0
            duration: 110
            easing.type: Easing.OutCubic
        }
    }

    Overlay.modal: Rectangle {
        color: colorPopup.appTheme.overlayDim
    }

    background: Rectangle {
        color: colorPopup.appTheme.bgPopover
        radius: 12
        border.width: 1
        border.color: colorPopup.appTheme.borderDefault
    }

    contentItem: Item {
        implicitWidth: 306
        implicitHeight: 374

        Item {
            id: header
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.top: parent.top
            height: 46

            Text {
                anchors.left: parent.left
                anchors.leftMargin: 14
                anchors.verticalCenter: parent.verticalCenter
                text: colorPopup.dialogTitle
                color: colorPopup.appTheme.textMain
                font.family: "Segoe UI Semibold"
                font.pointSize: 10
            }

            ToolButton {
                id: closeColorButton
                width: 36
                height: 36
                anchors.right: parent.right
                anchors.rightMargin: 5
                anchors.verticalCenter: parent.verticalCenter
                hoverEnabled: true
                focusPolicy: Qt.TabFocus
                display: AbstractButton.IconOnly
                icon.source: "../assets/icons/close.svg"
                icon.width: 16
                icon.height: 16
                icon.color: hovered || visualFocus
                            ? colorPopup.appTheme.btnCancelText : colorPopup.appTheme.textDim
                background: Rectangle {
                    radius: 8
                    color: closeColorButton.down ? colorPopup.appTheme.whiteAlpha15
                         : closeColorButton.hovered ? colorPopup.appTheme.whiteAlpha05
                         : "transparent"
                    border.width: closeColorButton.visualFocus ? 1 : 0
                    border.color: colorPopup.appTheme.accentMain
                }
                Accessible.name: "Close color picker"
                ToolTip.visible: hovered
                ToolTip.text: Accessible.name
                ToolTip.delay: 500
                onClicked: colorPopup.close()
            }

            Rectangle {
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.bottom: parent.bottom
                height: 1
                color: colorPopup.appTheme.borderDefault
            }
        }

        Column {
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.top: header.bottom
            anchors.bottom: parent.bottom
            anchors.margins: 14
            spacing: 10

            Rectangle {
                id: saturationValueArea
                width: parent.width
                height: 154
                radius: 8
                color: Qt.hsva(colorPopup.colorHue, 1, 1, 1)

                Rectangle {
                    anchors.fill: parent
                    radius: parent.radius
                    gradient: Gradient {
                        orientation: Gradient.Horizontal
                        GradientStop { position: 0; color: "#ffffffff" }
                        GradientStop { position: 1; color: "#00ffffff" }
                    }
                }

                Rectangle {
                    anchors.fill: parent
                    radius: parent.radius
                    gradient: Gradient {
                        GradientStop { position: 0; color: "#001e1e1e" }
                        // Intentional: the color picker must still allow true black.
                        GradientStop { position: 1; color: "#ff000000" }
                    }
                }

                Rectangle {
                    anchors.fill: parent
                    radius: parent.radius
                    color: "transparent"
                    border.width: 1
                    border.color: colorPopup.appTheme.borderDefault
                }

                MouseArea {
                    anchors.fill: parent
                    cursorShape: Qt.CrossCursor

                    function updateColor(mouseX, mouseY) {
                        colorPopup.colorSaturation = Math.max(
                            0,
                            Math.min(1, mouseX / width)
                        )
                        colorPopup.colorValue = 1 - Math.max(
                            0,
                            Math.min(1, mouseY / height)
                        )
                    }

                    onPressed: function(mouse) {
                        updateColor(mouse.x, mouse.y)
                    }
                    onPositionChanged: function(mouse) {
                        if (pressed) updateColor(mouse.x, mouse.y)
                    }
                }

                Rectangle {
                    width: 14
                    height: 14
                    radius: 7
                    x: Math.round(
                        (saturationValueArea.width - width)
                        * colorPopup.colorSaturation
                    )
                    y: Math.round(
                        (saturationValueArea.height - height)
                        * (1 - colorPopup.colorValue)
                    )
                    color: "transparent"
                    border.width: 2
                    border.color: "#ffffff"

                    Rectangle {
                        anchors.fill: parent
                        anchors.margins: 2
                        radius: 5
                        color: "transparent"
                        border.width: 1
                        border.color: "#801e1e1e"
                    }
                }
            }

            Rectangle {
                id: hueBar
                width: parent.width
                height: 16
                radius: 8
                gradient: Gradient {
                    orientation: Gradient.Horizontal
                    GradientStop { position: 0.00; color: "#ff0000" }
                    GradientStop { position: 0.17; color: "#ffff00" }
                    GradientStop { position: 0.33; color: "#00ff00" }
                    GradientStop { position: 0.50; color: "#00ffff" }
                    GradientStop { position: 0.67; color: "#0000ff" }
                    GradientStop { position: 0.83; color: "#ff00ff" }
                    GradientStop { position: 1.00; color: "#ff0000" }
                }

                MouseArea {
                    anchors.fill: parent
                    cursorShape: Qt.PointingHandCursor

                    function updateHue(mouseX) {
                        colorPopup.colorHue = Math.max(
                            0,
                            Math.min(1, mouseX / width)
                        )
                    }

                    onPressed: function(mouse) {
                        updateHue(mouse.x)
                    }
                    onPositionChanged: function(mouse) {
                        if (pressed) updateHue(mouse.x)
                    }
                }

                Rectangle {
                    width: 4
                    height: 22
                    radius: 2
                    x: Math.round((hueBar.width - width) * colorPopup.colorHue)
                    anchors.verticalCenter: parent.verticalCenter
                    color: "#ffffff"
                    border.width: 1
                    border.color: colorPopup.appTheme.bgNode
                }
            }

            Flow {
                width: parent.width
                height: 24
                spacing: 6

                Repeater {
                    model: [
                        "#f2b84b",
                        "#7b8cff",
                        "#e6158b",
                        "#e05252",
                        "#e58a3a",
                        "#55b96b",
                        "#38b8b0",
                        "#4f8ee8",
                        "#9b6ee8"
                    ]

                    Rectangle {
                        required property var modelData
                        width: 24
                        height: 24
                        radius: 7
                        color: modelData
                        scale: presetMouse.pressed ? 0.92 : 1
                        border.width: colorPopup.colorToHex(colorPopup.selectedColor)
                                      === colorPopup.colorToHex(modelData) ? 2 : 1
                        border.color: border.width === 2
                                      ? colorPopup.appTheme.textMain : colorPopup.appTheme.borderHover

                        Behavior on scale {
                            NumberAnimation { duration: 80 }
                        }

                        MouseArea {
                            id: presetMouse
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: colorPopup.setFromColor(parent.modelData)
                        }
                    }
                }
            }

            Row {
                width: parent.width
                height: 34
                spacing: 8

                Rectangle {
                    width: 34
                    height: 34
                    radius: 7
                    color: colorPopup.selectedColor
                    border.width: 1
                    border.color: colorPopup.appTheme.borderHover
                }

                TextField {
                    id: hexField
                    objectName: "tagColorHexField"
                    width: parent.width - 42
                    height: 34
                    leftPadding: 10
                    rightPadding: 10
                    selectByMouse: true
                    maximumLength: 7
                    placeholderText: "#RRGGBB"
                    text: "#FFFFFF"
                    color: colorPopup.appTheme.textMain
                    placeholderTextColor: colorPopup.appTheme.textDim
                    font.family: "Segoe UI"
                    font.pointSize: 9
                    inputMethodHints: Qt.ImhPreferUppercase
                    ContextMenu.menu: null

                    property bool validHex: /^#?[0-9A-Fa-f]{6}$/.test(text.trim())

                    background: Rectangle {
                        radius: 7
                        color: colorPopup.appTheme.bgInput
                        border.width: hexField.activeFocus || !hexField.validHex ? 1 : 0
                        border.color: !hexField.validHex
                                      ? colorPopup.appTheme.dangerHover : colorPopup.appTheme.accentMain
                    }

                    onAccepted: colorPopup.applyHexText()
                    onEditingFinished: {
                        if (validHex) colorPopup.applyHexText()
                    }
                }
            }

            Row {
                width: parent.width
                height: 32
                spacing: 8

                Item {
                    width: parent.width - 160
                    height: 1
                }

                ToolButton {
                    id: cancelColorButton
                    width: 72
                    height: 32
                    hoverEnabled: true
                    focusPolicy: Qt.TabFocus
                    display: AbstractButton.TextBesideIcon
                    text: "Cancel"
                    spacing: 5
                    leftPadding: 7
                    rightPadding: 7
                    font.family: "Segoe UI"
                    font.pointSize: 9
                    palette.buttonText: colorPopup.appTheme.textMain
                    icon.source: "../assets/icons/close.svg"
                    icon.width: 13
                    icon.height: 13
                    icon.color: colorPopup.appTheme.textDim
                    background: Rectangle {
                        radius: 7
                        color: cancelColorButton.down ? colorPopup.appTheme.whiteAlpha15
                             : cancelColorButton.hovered ? colorPopup.appTheme.whiteAlpha10
                             : colorPopup.appTheme.bgNode
                        border.width: cancelColorButton.visualFocus ? 1.5 : 1
                        border.color: cancelColorButton.visualFocus
                                      ? colorPopup.appTheme.accentMain : colorPopup.appTheme.borderDefault
                        Behavior on color { ColorAnimation { duration: 120 } }
                    }
                    Accessible.name: text
                    onClicked: colorPopup.close()
                }

                ToolButton {
                    id: applyColorButton
                    objectName: "tagColorApplyButton"
                    width: 72
                    height: 32
                    enabled: hexField.validHex
                    opacity: enabled ? 1 : 0.45
                    hoverEnabled: true
                    focusPolicy: Qt.TabFocus
                    display: AbstractButton.TextBesideIcon
                    text: "Apply"
                    spacing: 5
                    leftPadding: 7
                    rightPadding: 7
                    font.family: "Segoe UI Semibold"
                    font.pointSize: 9
                    palette.buttonText: colorPopup.appTheme.textMain
                    icon.source: "../assets/icons/check.svg"
                    icon.width: 13
                    icon.height: 13
                    icon.color: colorPopup.appTheme.textMain
                    background: Rectangle {
                        radius: 7
                        color: applyColorButton.down ? colorPopup.appTheme.accentHover
                             : applyColorButton.hovered ? colorPopup.appTheme.accentHover
                             : colorPopup.appTheme.accentMain
                        border.width: applyColorButton.visualFocus ? 1.5 : 0
                        border.color: colorPopup.appTheme.textMain
                        Behavior on color { ColorAnimation { duration: 120 } }
                    }
                    Accessible.name: text
                    onClicked: {
                        if (!colorPopup.applyHexText()) return
                        colorPopup.colorAccepted(colorPopup.selectedColor)
                        colorPopup.close()
                    }
                }
            }
        }
    }
}
