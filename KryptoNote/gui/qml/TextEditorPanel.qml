pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls.Basic

Item {
    id: editor
    required property var canvasController

    required property var appTheme
    property bool open: false
    property int nodeId: 0
    property bool loaded: false
    property bool draftNode: false
    property string originalTitle: ""
    property string originalContent: ""
    property int originalTitleSize: 14
    property int originalTextSize: 10
    property string createdAt: "-"
    property string updatedAt: "-"
    property bool _loading: false
    property bool panelVisible: false
    property bool resizing: resizeMouse.pressed
    property bool userResized: false
    property real preferredWidth: parent ? parent.width * 0.33 : 360
    property real minPanelWidth: Math.min(300, parent ? parent.width * 0.5 : 300)
    property real maxPanelWidth: parent ? parent.width * 0.5 : 560
    property real slideOffset: open ? 0 : width
    property bool hasContent: titleInput.text.trim().length > 0 || bodyInput.text.trim().length > 0
    readonly property bool dirty: loaded && (
        titleInput.text !== originalTitle
        || bodyInput.text !== originalContent
        || _selectedTitleSize() !== originalTitleSize
        || _selectedTextSize() !== originalTextSize
    )
    property var fontSizes: [8, 9, 10, 11, 12, 14, 16, 18, 20, 24, 28, 32, 36, 48, 64]

    signal requestedClose()
    signal requestedCenter(int nodeId)
    signal requestedReturn()
    signal requestedTagPicker(int nodeId, var anchorItem)

    width: Math.max(minPanelWidth, Math.min(maxPanelWidth, preferredWidth))
    height: parent ? parent.height : 0
    visible: panelVisible

    onOpenChanged: {
        if (open) {
            hideTimer.stop()
            panelVisible = true
        } else {
            hideTimer.restart()
        }
    }

    onMaxPanelWidthChanged: {
        if (preferredWidth > maxPanelWidth) {
            preferredWidth = maxPanelWidth
        }
    }

    function openForNode(nextNodeId) {
        var data = editor.canvasController.get_text_editor_data(nextNodeId)
        if (!data || data.length < 4) {
            return
        }

        _loading = true
        nodeId = nextNodeId
        originalTitle = data[0]
        originalContent = data[1]
        originalTitleSize = data[2]
        originalTextSize = data[3]
        draftNode = data.length > 4 ? data[4] : false
        createdAt = data.length > 5 ? data[5] : "-"
        updatedAt = data.length > 6 ? data[6] : "-"
        refreshTags()
        titleInput.text = originalTitle
        bodyInput.text = originalContent
        titleSizeCombo.currentIndex = _fontIndex(originalTitleSize)
        bodySizeCombo.currentIndex = _fontIndex(originalTextSize)
        loaded = true
        open = true
        _loading = false
        titleInput.forceActiveFocus()
        requestedCenter(nodeId)
    }

    function refreshTags() {
        editorTagModel.clear()
        var tags = editor.canvasController.get_node_tags(nodeId)
        for (var i = 0; i < tags.length; i++) {
            editorTagModel.append({
                "tagName": tags[i].name,
                "tagColor": tags[i].color
            })
        }
    }

    function saveAndClose() {
        if (!hasContent || !loaded) {
            return
        }
        editor.canvasController.save_text_content(
            nodeId,
            titleInput.text,
            bodyInput.text,
            _selectedTitleSize(),
            _selectedTextSize()
        )
        closeWithoutRestore()
    }

    function cancelOrDelete() {
        if (!loaded) {
            closeWithoutRestore()
            return
        }

        if (!hasContent) {
            var deleteId = nodeId
            closeWithoutRestore()
            editor.canvasController.request_animated_delete(deleteId)
            return
        }

        editor.canvasController.preview_text_content(
            nodeId,
            originalTitle,
            originalContent,
            originalTitleSize,
            originalTextSize
        )
        closeWithoutRestore()
    }

    function closeWithoutRestore() {
        open = false
        loaded = false
        nodeId = 0
        requestedReturn()
        requestedClose()
    }

    function _preview() {
        if (_loading || !loaded) {
            return
        }
        editor.canvasController.preview_text_content(
            nodeId,
            titleInput.text,
            bodyInput.text,
            _selectedTitleSize(),
            _selectedTextSize()
        )
    }

    function _fontIndex(size) {
        for (var i = 0; i < fontSizes.length; i++) {
            if (fontSizes[i] === size) {
                return i
            }
        }
        return 5
    }

    function _selectedTitleSize() {
        return titleSizeCombo.currentIndex >= 0 ? fontSizes[titleSizeCombo.currentIndex] : 14
    }

    function _selectedTextSize() {
        return bodySizeCombo.currentIndex >= 0 ? fontSizes[bodySizeCombo.currentIndex] : 10
    }

    Rectangle {
        anchors.fill: parent
        color: editor.appTheme.bgPanel
    }

    Rectangle {
        width: 1
        anchors.left: parent.left
        anchors.top: parent.top
        anchors.bottom: parent.bottom
        color: editor.appTheme.borderDefault
    }

    MouseArea {
        anchors.fill: parent
        acceptedButtons: Qt.LeftButton | Qt.RightButton | Qt.MiddleButton
        hoverEnabled: true
        preventStealing: true
        onWheel: function(wheel) { wheel.accepted = true }
    }

    Rectangle {
        id: resizeGrip
        width: 7
        anchors.left: parent.left
        anchors.top: parent.top
        anchors.bottom: parent.bottom
        color: resizeMouse.containsMouse || resizeMouse.pressed ? editor.appTheme.accentMain : "transparent"
        opacity: resizeMouse.containsMouse || resizeMouse.pressed ? 0.55 : 0.0

        Behavior on opacity { NumberAnimation { duration: 120 } }

        MouseArea {
            id: resizeMouse
            anchors.fill: parent
            hoverEnabled: true
            preventStealing: true
            acceptedButtons: Qt.LeftButton
            cursorShape: Qt.SizeHorCursor
            property real pressSceneX: 0
            property real startPreferredWidth: 0

            onPressed: function(mouse) {
                mouse.accepted = true
                pressSceneX = resizeMouse.mapToItem(editor.parent, mouse.x, mouse.y).x
                startPreferredWidth = editor.preferredWidth
                editor.userResized = true
            }

            onPositionChanged: function(mouse) {
                mouse.accepted = true
                if (!pressed) {
                    return
                }
                var sceneX = resizeMouse.mapToItem(editor.parent, mouse.x, mouse.y).x
                var nextWidth = startPreferredWidth - (sceneX - pressSceneX)
                editor.preferredWidth = Math.max(editor.minPanelWidth, Math.min(editor.maxPanelWidth, nextWidth))
                editor.requestedCenter(editor.nodeId)
            }

            onReleased: function(mouse) {
                mouse.accepted = true
            }
        }
    }

    Column {
        anchors.fill: parent
        anchors.leftMargin: 18
        anchors.rightMargin: 10
        anchors.topMargin: 14
        anchors.bottomMargin: 14
        spacing: 10

        Rectangle {
            id: titleField
            width: parent.width
            height: 34
            radius: 7
            color: editor.appTheme.bgNode

            HoverHandler { id: titleHover }

            TextField {
                id: titleInput
                objectName: "editorTitleInput"
                anchors.left: parent.left
                anchors.right: titleSizeCombo.left
                anchors.verticalCenter: parent.verticalCenter
                anchors.leftMargin: 12
                anchors.rightMargin: 6
                text: ""
                placeholderText: "Title"
                selectByMouse: true
                color: editor.appTheme.textMain
                placeholderTextColor: editor.appTheme.textDim
                font.family: "Segoe UI Semibold"
                font.pointSize: 12
                background: Item {}
                ContextMenu.menu: null
                onTextChanged: editor._preview()
                Keys.onPressed: function(event) {
                    if ((event.key === Qt.Key_Return || event.key === Qt.Key_Enter)
                            && event.modifiers === Qt.NoModifier) {
                        bodyInput.forceActiveFocus()
                        bodyInput.cursorPosition = bodyInput.text.length
                        event.accepted = true
                    }
                }
            }

            EditorFontSizeCombo {
                appTheme: editor.appTheme
                id: titleSizeCombo
                anchors.right: parent.right
                anchors.rightMargin: 4
                anchors.verticalCenter: parent.verticalCenter
                fontSizes: editor.fontSizes
                reveal: titleHover.hovered
                onCurrentIndexChanged: editor._preview()
            }
        }

        Rectangle {
            id: bodyField
            width: parent.width
            height: parent.height - titleField.height - tagRow.height - metaRow.height - buttons.height - 40
            radius: 7
            color: editor.appTheme.bgNode

            HoverHandler { id: bodyHover }

            ScrollView {
                id: bodyScroll
                anchors.fill: parent
                anchors.margins: 12
                anchors.topMargin: 14
                anchors.rightMargin: 12
                clip: true
                ScrollBar.horizontal.policy: ScrollBar.AlwaysOff
                ScrollBar.vertical.policy: bodyInput.contentHeight > bodyScroll.height
                                           ? ScrollBar.AsNeeded : ScrollBar.AlwaysOff
                ScrollBar.vertical.contentItem: Rectangle {
                    implicitWidth: 4
                    radius: 2
                    color: editor.appTheme.borderHover
                }
                ScrollBar.vertical.background: Rectangle {
                    color: "transparent"
                }

                TextArea {
                    id: bodyInput
                    objectName: "editorBodyInput"
                    width: bodyScroll.availableWidth
                    implicitHeight: contentHeight + topPadding + bottomPadding
                    placeholderText: "Start typing..."
                    selectByMouse: true
                    wrapMode: TextEdit.WrapAtWordBoundaryOrAnywhere
                    color: editor.appTheme.textMain
                    placeholderTextColor: editor.appTheme.textDim
                    font.family: "Segoe UI"
                    font.pointSize: 10
                    background: Item {}
                    ContextMenu.menu: null
                    onTextChanged: editor._preview()
                }
            }

            EditorFontSizeCombo {
                appTheme: editor.appTheme
                id: bodySizeCombo
                z: 3
                anchors.right: parent.right
                anchors.top: parent.top
                anchors.rightMargin: 8
                anchors.topMargin: 8
                fontSizes: editor.fontSizes
                reveal: bodyHover.hovered
                onCurrentIndexChanged: editor._preview()
            }
        }

        Rectangle {
            id: tagRow
            width: parent.width
            height: 34
            radius: 7
            color: editor.appTheme.bgNode
            border.width: 1
            border.color: editor.appTheme.borderDefault
            clip: true

            Flickable {
                id: tagChipViewport
                objectName: "editorTagChipViewport"
                anchors.left: parent.left
                anchors.right: addTagsButton.left
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
                        model: ListModel { id: editorTagModel }

                        Rectangle {
                            id: editorTagChip
                            objectName: "editorTagChip"
                            required property string tagName
                            required property string tagColor
                            anchors.verticalCenter: parent.verticalCenter
                            width: Math.min(220, Math.max(48, chipText.implicitWidth + 30))
                            height: 22
                            radius: 6
                            color: editor.appTheme.whiteAlpha05
                            border.width: 1
                            border.color: editorTagChip.tagColor

                            Rectangle {
                                width: 7
                                height: 7
                                radius: 4
                                color: editorTagChip.tagColor
                                anchors.left: parent.left
                                anchors.leftMargin: 7
                                anchors.verticalCenter: parent.verticalCenter
                            }

                            Text {
                                id: chipText
                                objectName: "editorTagChipText"
                                anchors.left: parent.left
                                anchors.leftMargin: 18
                                anchors.right: parent.right
                                anchors.rightMargin: 6
                                anchors.verticalCenter: parent.verticalCenter
                                text: "@" + editorTagChip.tagName
                                color: editor.appTheme.textMain
                                elide: Text.ElideRight
                                font.family: "Segoe UI"
                                font.pointSize: 8
                            }
                        }
                    }
                }
            }

            ToolButton {
                id: addTagsButton
                width: 70
                height: 26
                anchors.right: parent.right
                anchors.rightMargin: 4
                anchors.verticalCenter: parent.verticalCenter
                hoverEnabled: true
                focusPolicy: Qt.TabFocus
                display: AbstractButton.TextBesideIcon
                text: "Tags"
                spacing: 5
                leftPadding: 7
                rightPadding: 7
                font.family: "Segoe UI Semibold"
                font.pointSize: 8
                palette.buttonText: hovered || visualFocus
                                    ? editor.appTheme.textMain : editor.appTheme.textDim
                icon.source: "../assets/icons/tag.svg"
                icon.width: 13
                icon.height: 13
                icon.color: hovered || visualFocus
                            ? editor.appTheme.textMain : editor.appTheme.textDim
                scale: down ? 0.97 : 1.0
                Behavior on scale {
                    NumberAnimation {
                        duration: editor.appTheme.motionEnabled ? 80 : 0
                        easing.type: Easing.OutCubic
                    }
                }
                background: Rectangle {
                    radius: 6
                    color: addTagsButton.down ? editor.appTheme.whiteAlpha15
                         : addTagsButton.hovered ? editor.appTheme.whiteAlpha10
                         : "transparent"
                    border.width: addTagsButton.visualFocus ? 1 : 0
                    border.color: editor.appTheme.accentMain
                }
                Accessible.name: "Manage tags"
                ThemedToolTip {
                    appTheme: editor.appTheme
                    visible: addTagsButton.hovered
                    text: addTagsButton.Accessible.name
                    delay: 500
                }
                onClicked: editor.requestedTagPicker(editor.nodeId, addTagsButton)
            }
        }

        Row {
            id: metaRow
            width: parent.width
            height: 16
            spacing: 12

            Text {
                width: (parent.width - parent.spacing) / 2
                text: "Added: " + editor.createdAt
                color: editor.appTheme.textMuted
                font.family: "Segoe UI"
                font.pointSize: 8
                elide: Text.ElideRight
            }

            Text {
                width: (parent.width - parent.spacing) / 2
                text: "Edited: " + editor.updatedAt
                color: editor.appTheme.textMuted
                font.family: "Segoe UI"
                font.pointSize: 8
                elide: Text.ElideRight
                horizontalAlignment: Text.AlignRight
            }
        }

        Row {
            id: buttons
            width: Math.min(parent.width, 236)
            height: 30
            spacing: 10

            ToolButton {
                id: saveButton
                width: (parent.width - parent.spacing) / 2
                height: parent.height
                enabled: editor.hasContent
                opacity: editor.hasContent ? 1.0 : 0.85
                hoverEnabled: true
                focusPolicy: Qt.TabFocus
                display: AbstractButton.TextBesideIcon
                text: "Save"
                spacing: 6
                font.family: "Segoe UI Semibold"
                font.pointSize: 9
                palette.buttonText: enabled ? editor.appTheme.btnApplyText : editor.appTheme.textDim
                icon.source: "../assets/icons/save.svg"
                icon.width: 14
                icon.height: 14
                icon.color: enabled ? editor.appTheme.btnApplyText : editor.appTheme.textDim
                scale: down ? 0.97 : 1.0

                background: Rectangle {
                    radius: 6
                    color: !saveButton.enabled ? editor.appTheme.bgNode
                         : saveButton.down ? editor.appTheme.successHover
                         : saveButton.hovered ? editor.appTheme.btnApplyHover
                         : editor.appTheme.btnApply
                    border.width: saveButton.visualFocus ? 1.5 : 1
                    border.color: saveButton.visualFocus
                                  ? editor.appTheme.accentMain : editor.appTheme.btnApplyBorder
                    Behavior on color { ColorAnimation { duration: 140 } }
                }

                Behavior on opacity { NumberAnimation { duration: 140 } }
                Behavior on scale { NumberAnimation { duration: 80 } }
                Accessible.name: text
                ThemedToolTip {
                    appTheme: editor.appTheme
                    visible: saveButton.hovered
                    text: "Save: Ctrl+S / Ctrl+Enter"
                    delay: 450
                }
                onClicked: editor.saveAndClose()
            }

            ToolButton {
                id: cancelButton
                property bool destructive: !editor.hasContent
                width: (parent.width - parent.spacing) / 2
                height: parent.height
                hoverEnabled: true
                focusPolicy: Qt.TabFocus
                display: AbstractButton.TextBesideIcon
                text: destructive ? "Delete" : "Cancel"
                spacing: 6
                font.family: "Segoe UI"
                font.pointSize: 9
                palette.buttonText: destructive
                                    ? editor.appTheme.btnCancelText : editor.appTheme.textMain
                icon.source: destructive
                             ? "../assets/icons/delete.svg" : "../assets/icons/close.svg"
                icon.width: 14
                icon.height: 14
                icon.color: destructive
                            ? editor.appTheme.btnCancelText : editor.appTheme.textDim
                scale: down ? 0.97 : 1.0

                background: Rectangle {
                    radius: 6
                    color: cancelButton.destructive
                         ? (cancelButton.down || cancelButton.hovered
                            ? editor.appTheme.btnCancelHover : editor.appTheme.btnCancel)
                         : cancelButton.down ? editor.appTheme.bgControlPressed
                         : cancelButton.hovered ? editor.appTheme.bgControlHover
                         : editor.appTheme.bgNode
                    border.width: cancelButton.visualFocus ? 1.5 : 1
                    border.color: cancelButton.visualFocus ? editor.appTheme.accentMain
                                : cancelButton.destructive
                                  ? editor.appTheme.btnCancelBorder : editor.appTheme.borderDefault
                }

                Behavior on scale {
                    NumberAnimation {
                        duration: editor.appTheme.motionEnabled ? 80 : 0
                        easing.type: Easing.OutCubic
                    }
                }
                Accessible.name: text
                ThemedToolTip {
                    appTheme: editor.appTheme
                    visible: cancelButton.hovered
                    text: editor.hasContent ? "Cancel: Esc" : "Delete: Esc"
                    delay: 450
                }
                onClicked: editor.cancelOrDelete()
            }
        }
    }

    Timer {
        id: hideTimer
        interval: 230
        repeat: false
        onTriggered: {
            if (!editor.open) {
                editor.panelVisible = false
            }
        }
    }

}
