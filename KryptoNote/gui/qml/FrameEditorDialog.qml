pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls.Basic


Popup {
    id: editor
    required property var canvasController
    required property var appTheme
    parent: Overlay.overlay

    property int nodeId: 0
    property bool loaded: false
    property bool committed: false
    property bool loading: false
    property string originalTitle: ""
    property string originalColor: ""
    property real originalOpacity: 0.21
    property string selectedColor: ""
    property real defaultOpacity: 0.21
    readonly property color effectiveColor: selectedColor.length > 0
                                            ? selectedColor
                                            : editor.appTheme.bgPanel

    signal requestedTagPicker(int nodeId, var anchorItem)
    signal requestedClose()

    z: 38
    width: Math.min(
        480,
        parent && parent.width > 0 ? parent.width - 24 : 480
    )
    height: Math.min(
        460,
        parent && parent.height > 0 ? parent.height - 24 : 460
    )
    margins: 12
    padding: 0
    modal: true
    dim: true
    focus: true
    closePolicy: Popup.CloseOnEscape

    function openForFrame(nextNodeId) {
        var data = editor.canvasController.get_frame_editor_data(nextNodeId)
        if (!data || data.length < 4) return

        loading = true
        nodeId = nextNodeId
        originalTitle = data[0]
        originalColor = data[1]
        originalOpacity = data[2]
        defaultOpacity = data[3]
        selectedColor = originalColor
        titleInput.text = originalTitle
        opacitySlider.value = originalOpacity
        refreshTags()
        loaded = true
        committed = false
        loading = false

        x = Math.round((parent.width - width) / 2)
        y = Math.round((parent.height - height) / 2)
        open()
        titleInput.forceActiveFocus()
        titleInput.selectAll()
    }

    function refreshTags() {
        frameTagModel.clear()
        var tags = editor.canvasController.get_node_tags(nodeId)
        for (var i = 0; i < tags.length; i++) {
            frameTagModel.append({
                "tagName": tags[i].name,
                "tagColor": tags[i].color
            })
        }
    }

    function preview() {
        if (loading || !loaded) return
        editor.canvasController.preview_frame_properties(
            nodeId,
            titleInput.text,
            selectedColor,
            opacitySlider.value
        )
    }

    function chooseColor(nextColor) {
        selectedColor = colorPopup.colorToHex(nextColor)
        preview()
    }

    function resetAppearance() {
        selectedColor = ""
        opacitySlider.value = defaultOpacity
        preview()
    }

    function saveAndClose() {
        if (!loaded) return
        if (!editor.canvasController.save_frame_properties(
                nodeId,
                titleInput.text,
                selectedColor,
                opacitySlider.value
        )) return
        committed = true
        close()
    }

    onClosed: {
        if (colorPopup.visible) colorPopup.close()
        if (loaded && !committed) {
            editor.canvasController.preview_frame_properties(
                nodeId,
                originalTitle,
                originalColor,
                originalOpacity
            )
        }
        loaded = false
        committed = false
        nodeId = 0
        requestedClose()
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
                from: 0.985
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
        color: editor.appTheme.overlayDim
    }

    background: Rectangle {
        color: editor.appTheme.bgPopover
        radius: 12
        border.width: 1
        border.color: editor.appTheme.borderDefault
    }

    contentItem: Item {
        implicitWidth: 480
        implicitHeight: 460

        Item {
            id: header
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.top: parent.top
            height: 50

            Text {
                anchors.left: parent.left
                anchors.leftMargin: 16
                anchors.verticalCenter: parent.verticalCenter
                text: "Frame settings"
                color: editor.appTheme.textMain
                font.family: "Segoe UI Semibold"
                font.pointSize: 11
            }

            ToolButton {
                id: closeButton
                width: 38
                height: 38
                anchors.right: parent.right
                anchors.rightMargin: 6
                anchors.verticalCenter: parent.verticalCenter
                hoverEnabled: true
                focusPolicy: Qt.TabFocus
                display: AbstractButton.IconOnly
                icon.source: "../assets/icons/close.svg"
                icon.width: 16
                icon.height: 16
                icon.color: hovered || visualFocus
                            ? editor.appTheme.btnCancelText
                            : editor.appTheme.textDim
                background: Rectangle {
                    radius: 8
                    color: closeButton.down
                           ? editor.appTheme.whiteAlpha15
                           : closeButton.hovered
                             ? editor.appTheme.whiteAlpha05
                             : "transparent"
                    border.width: closeButton.visualFocus ? 1 : 0
                    border.color: editor.appTheme.accentMain
                }
                Accessible.name: "Close frame settings"
                ToolTip.visible: hovered
                ToolTip.text: Accessible.name
                ToolTip.delay: 450
                onClicked: editor.close()
            }

            Rectangle {
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.bottom: parent.bottom
                height: 1
                color: editor.appTheme.borderDefault
            }
        }

        Column {
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.top: header.bottom
            anchors.bottom: footer.top
            anchors.margins: 16
            spacing: 12

            Text {
                text: "Title"
                color: editor.appTheme.textMuted
                font.family: "Segoe UI"
                font.pointSize: 8
            }

            TextField {
                id: titleInput
                width: parent.width
                height: 36
                leftPadding: 11
                rightPadding: 11
                selectByMouse: true
                placeholderText: "Untitled Frame"
                text: ""
                color: editor.appTheme.textMain
                placeholderTextColor: editor.appTheme.textDim
                font.family: "Segoe UI Semibold"
                font.pointSize: 10
                ContextMenu.menu: null
                background: Rectangle {
                    radius: 7
                    color: editor.appTheme.bgInput
                    border.width: titleInput.activeFocus ? 1 : 0
                    border.color: editor.appTheme.accentMain
                }
                onTextChanged: editor.preview()
                Keys.onPressed: function(event) {
                    if ((event.modifiers & Qt.ControlModifier)
                            && (event.key === Qt.Key_Return
                                || event.key === Qt.Key_Enter
                                || event.key === Qt.Key_S)) {
                        editor.saveAndClose()
                        event.accepted = true
                    }
                }
            }

            Rectangle {
                id: previewSurface
                width: parent.width
                height: 106
                radius: 8
                color: editor.appTheme.bgCanvas
                border.width: 1
                border.color: editor.appTheme.borderSubtle

                Rectangle {
                    id: previewFill
                    anchors.fill: previewOutline
                    radius: 7
                    color: editor.effectiveColor
                    opacity: opacitySlider.value
                }

                Rectangle {
                    id: previewOutline
                    anchors.fill: parent
                    anchors.margins: 12
                    radius: 7
                    color: "transparent"
                    border.width: 1
                    border.color: editor.appTheme.borderHover
                }

                Rectangle {
                    anchors.horizontalCenter: previewOutline.horizontalCenter
                    y: previewOutline.y - height / 2
                    width: Math.min(
                        previewOutline.width - 24,
                        Math.max(90, previewTitle.implicitWidth + 50)
                    )
                    height: 26
                    radius: 13
                    color: editor.appTheme.bgNode
                    border.width: 1
                    border.color: editor.appTheme.borderHover

                    Text {
                        id: previewTitle
                        anchors.fill: parent
                        anchors.leftMargin: 12
                        anchors.rightMargin: 12
                        text: titleInput.text.trim().length > 0
                              ? titleInput.text
                              : "Untitled Frame"
                        color: editor.appTheme.textMain
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                        elide: Text.ElideRight
                        font.family: "Segoe UI Semibold"
                        font.pointSize: 8
                    }
                }
            }

            Row {
                width: parent.width
                height: 38
                spacing: 8

                Rectangle {
                    width: 38
                    height: 38
                    radius: 8
                    color: editor.effectiveColor
                    border.width: 1
                    border.color: editor.appTheme.borderHover

                    Rectangle {
                        anchors.fill: parent
                        radius: parent.radius
                        color: "transparent"
                        border.width: editor.selectedColor.length === 0 ? 2 : 0
                        border.color: editor.appTheme.textMuted
                    }
                }

                ToolButton {
                    id: chooseColorButton
                    width: parent.width - resetButton.width - 54
                    height: parent.height
                    hoverEnabled: true
                    focusPolicy: Qt.TabFocus
                    display: AbstractButton.TextBesideIcon
                    text: editor.selectedColor.length > 0
                          ? editor.selectedColor.toUpperCase()
                          : "Theme default"
                    spacing: 7
                    font.family: "Segoe UI"
                    font.pointSize: 9
                    palette.buttonText: editor.appTheme.textMain
                    icon.source: "../assets/icons/palette.svg"
                    icon.width: 15
                    icon.height: 15
                    icon.color: hovered || visualFocus
                                ? editor.appTheme.accentMain
                                : editor.appTheme.textDim
                    background: Rectangle {
                        radius: 7
                        color: chooseColorButton.down
                               ? editor.appTheme.bgControlPressed
                               : chooseColorButton.hovered
                                 ? editor.appTheme.bgControlHover
                                 : editor.appTheme.bgNode
                        border.width: chooseColorButton.visualFocus ? 1.5 : 1
                        border.color: chooseColorButton.visualFocus
                                      ? editor.appTheme.accentMain
                                      : editor.appTheme.borderDefault
                    }
                    onClicked: colorPopup.openForColor(
                        editor.effectiveColor
                    )
                }

                ToolButton {
                    id: resetButton
                    width: 92
                    height: parent.height
                    hoverEnabled: true
                    focusPolicy: Qt.TabFocus
                    display: AbstractButton.TextBesideIcon
                    text: "Reset"
                    spacing: 6
                    font.family: "Segoe UI"
                    font.pointSize: 9
                    palette.buttonText: editor.appTheme.textMuted
                    icon.source: "../assets/icons/reset.svg"
                    icon.width: 14
                    icon.height: 14
                    icon.color: editor.appTheme.textMuted
                    background: Rectangle {
                        radius: 7
                        color: resetButton.down
                               ? editor.appTheme.whiteAlpha15
                               : resetButton.hovered
                                 ? editor.appTheme.whiteAlpha10
                                 : "transparent"
                        border.width: resetButton.visualFocus ? 1 : 0
                        border.color: editor.appTheme.accentMain
                    }
                    onClicked: editor.resetAppearance()
                }
            }

            Row {
                width: parent.width
                height: 34
                spacing: 10

                Text {
                    width: 72
                    anchors.verticalCenter: parent.verticalCenter
                    text: "Opacity"
                    color: editor.appTheme.textMuted
                    font.family: "Segoe UI"
                    font.pointSize: 9
                }

                Slider {
                    id: opacitySlider
                    width: parent.width - 126
                    anchors.verticalCenter: parent.verticalCenter
                    from: 0
                    to: 0.9
                    stepSize: 0.01
                    value: editor.defaultOpacity
                    live: true

                    background: Rectangle {
                        x: opacitySlider.leftPadding
                        y: opacitySlider.topPadding
                           + opacitySlider.availableHeight / 2
                           - height / 2
                        width: opacitySlider.availableWidth
                        height: 4
                        radius: 2
                        color: editor.appTheme.sliderTrack

                        Rectangle {
                            width: opacitySlider.visualPosition * parent.width
                            height: parent.height
                            radius: parent.radius
                            color: editor.appTheme.accentMain
                        }
                    }

                    handle: Rectangle {
                        x: opacitySlider.leftPadding
                           + opacitySlider.visualPosition
                             * (opacitySlider.availableWidth - width)
                        y: opacitySlider.topPadding
                           + opacitySlider.availableHeight / 2
                           - height / 2
                        width: 16
                        height: 16
                        radius: 8
                        color: opacitySlider.hovered || opacitySlider.pressed
                               ? editor.appTheme.sliderHandleHover
                               : editor.appTheme.sliderHandle
                        border.width: 1
                        border.color: editor.appTheme.bgNode
                    }

                    onValueChanged: editor.preview()
                }

                Text {
                    width: 44
                    anchors.verticalCenter: parent.verticalCenter
                    text: Math.round(opacitySlider.value * 100) + "%"
                    color: editor.appTheme.textMain
                    horizontalAlignment: Text.AlignRight
                    font.family: "Segoe UI Semibold"
                    font.pointSize: 9
                }
            }

            Rectangle {
                id: tagRow
                width: parent.width
                height: 38
                radius: 7
                color: editor.appTheme.bgNode
                border.width: 1
                border.color: editor.appTheme.borderDefault
                clip: true

                Flickable {
                    anchors.left: parent.left
                    anchors.right: tagsButton.left
                    anchors.top: parent.top
                    anchors.bottom: parent.bottom
                    anchors.leftMargin: 8
                    anchors.rightMargin: 6
                    contentWidth: tagChips.implicitWidth
                    contentHeight: height
                    flickableDirection: Flickable.HorizontalFlick
                    boundsBehavior: Flickable.StopAtBounds
                    interactive: contentWidth > width
                    clip: true

                    Row {
                        id: tagChips
                        width: implicitWidth
                        height: parent.height
                        spacing: 6

                        Repeater {
                            model: ListModel { id: frameTagModel }

                            Rectangle {
                                required property string tagName
                                required property string tagColor
                                anchors.verticalCenter: parent.verticalCenter
                                width: Math.min(
                                    180,
                                    Math.max(
                                        48,
                                        frameTagText.implicitWidth + 28
                                    )
                                )
                                height: 22
                                radius: 6
                                color: editor.appTheme.whiteAlpha05
                                border.width: 1
                                border.color: tagColor

                                Rectangle {
                                    width: 7
                                    height: 7
                                    radius: 4
                                    color: parent.tagColor
                                    anchors.left: parent.left
                                    anchors.leftMargin: 7
                                    anchors.verticalCenter: parent.verticalCenter
                                }

                                Text {
                                    id: frameTagText
                                    anchors.left: parent.left
                                    anchors.leftMargin: 18
                                    anchors.right: parent.right
                                    anchors.rightMargin: 6
                                    anchors.verticalCenter: parent.verticalCenter
                                    text: "@" + parent.tagName
                                    color: editor.appTheme.textMain
                                    elide: Text.ElideRight
                                    font.family: "Segoe UI"
                                    font.pointSize: 8
                                }
                            }
                        }
                    }
                }

                Text {
                    anchors.left: parent.left
                    anchors.leftMargin: 10
                    anchors.verticalCenter: parent.verticalCenter
                    visible: frameTagModel.count === 0
                    text: "No tags assigned"
                    color: editor.appTheme.textDim
                    font.family: "Segoe UI"
                    font.pointSize: 8
                }

                ToolButton {
                    id: tagsButton
                    width: 78
                    height: 28
                    anchors.right: parent.right
                    anchors.rightMargin: 4
                    anchors.verticalCenter: parent.verticalCenter
                    hoverEnabled: true
                    focusPolicy: Qt.TabFocus
                    display: AbstractButton.TextBesideIcon
                    text: "Tags"
                    spacing: 5
                    font.family: "Segoe UI Semibold"
                    font.pointSize: 8
                    palette.buttonText: hovered || visualFocus
                                        ? editor.appTheme.textMain
                                        : editor.appTheme.textDim
                    icon.source: "../assets/icons/tag.svg"
                    icon.width: 13
                    icon.height: 13
                    icon.color: hovered || visualFocus
                                ? editor.appTheme.textMain
                                : editor.appTheme.textDim
                    background: Rectangle {
                        radius: 6
                        color: tagsButton.down
                               ? editor.appTheme.whiteAlpha15
                               : tagsButton.hovered
                                 ? editor.appTheme.whiteAlpha10
                                 : "transparent"
                        border.width: tagsButton.visualFocus ? 1 : 0
                        border.color: editor.appTheme.accentMain
                    }
                    onClicked: editor.requestedTagPicker(
                        editor.nodeId, tagsButton
                    )
                }
            }
        }

        Row {
            id: footer
            anchors.right: parent.right
            anchors.rightMargin: 16
            anchors.bottom: parent.bottom
            anchors.bottomMargin: 14
            width: 218
            height: 34
            spacing: 10

            ToolButton {
                id: cancelButton
                width: (parent.width - parent.spacing) / 2
                height: parent.height
                hoverEnabled: true
                focusPolicy: Qt.TabFocus
                display: AbstractButton.TextBesideIcon
                text: "Cancel"
                spacing: 6
                font.family: "Segoe UI"
                font.pointSize: 9
                palette.buttonText: editor.appTheme.btnCancelText
                icon.source: "../assets/icons/close.svg"
                icon.width: 14
                icon.height: 14
                icon.color: editor.appTheme.btnCancelText
                background: Rectangle {
                    radius: 7
                    color: cancelButton.down
                           ? editor.appTheme.whiteAlpha15
                           : cancelButton.hovered
                             ? editor.appTheme.btnCancelHover
                             : editor.appTheme.btnCancel
                    border.width: cancelButton.visualFocus ? 1.5 : 1
                    border.color: cancelButton.visualFocus
                                  ? editor.appTheme.accentMain
                                  : editor.appTheme.btnCancelBorder
                }
                onClicked: editor.close()
            }

            ToolButton {
                id: saveButton
                width: (parent.width - parent.spacing) / 2
                height: parent.height
                hoverEnabled: true
                focusPolicy: Qt.TabFocus
                display: AbstractButton.TextBesideIcon
                text: "Save"
                spacing: 6
                font.family: "Segoe UI Semibold"
                font.pointSize: 9
                palette.buttonText: editor.appTheme.btnApplyText
                icon.source: "../assets/icons/save.svg"
                icon.width: 14
                icon.height: 14
                icon.color: editor.appTheme.btnApplyText
                background: Rectangle {
                    radius: 7
                    color: saveButton.down
                           ? editor.appTheme.successHover
                           : saveButton.hovered
                             ? editor.appTheme.btnApplyHover
                             : editor.appTheme.btnApply
                    border.width: saveButton.visualFocus ? 1.5 : 1
                    border.color: saveButton.visualFocus
                                  ? editor.appTheme.accentMain
                                  : editor.appTheme.btnApplyBorder
                }
                onClicked: editor.saveAndClose()
            }
        }
    }

    TagColorPopup {
        id: colorPopup
        appTheme: editor.appTheme
        dialogTitle: "Frame color"
        onColorAccepted: function(nextColor) {
            editor.chooseColor(nextColor)
        }
    }
}
