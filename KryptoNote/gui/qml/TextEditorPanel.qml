import QtQuick
import QtQuick.Controls.Basic

Item {
    id: editor

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
    property var fontSizes: [8, 9, 10, 11, 12, 14, 16, 18, 20, 24, 28, 32, 36, 48, 64]

    signal requestedClose()
    signal requestedCenter(int nodeId)
    signal requestedReturn()

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
        var data = canvasController.get_text_editor_data(nextNodeId)
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

    function saveAndClose() {
        if (!hasContent || !loaded) {
            return
        }
        canvasController.save_text_content(
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
            canvasController.request_animated_delete(deleteId)
            return
        }

        canvasController.preview_text_content(
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
        canvasController.preview_text_content(
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
        color: "#1e1e1e"
    }

    Rectangle {
        width: 1
        anchors.left: parent.left
        anchors.top: parent.top
        anchors.bottom: parent.bottom
        color: "#303030"
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
        color: resizeMouse.containsMouse || resizeMouse.pressed ? AppTheme.accentMain : "transparent"
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
            color: "#26282b"

            HoverHandler { id: titleHover }

            TextField {
                id: titleInput
                anchors.left: parent.left
                anchors.right: titleSizeCombo.left
                anchors.verticalCenter: parent.verticalCenter
                anchors.leftMargin: 12
                anchors.rightMargin: 6
                text: ""
                placeholderText: "Title"
                selectByMouse: true
                color: "#f4f4f4"
                placeholderTextColor: "#73777d"
                font.family: "Segoe UI Semibold"
                font.pointSize: 12
                background: Item {}
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
            height: parent.height - titleField.height - metaRow.height - buttons.height - 30
            radius: 7
            color: "#26282b"

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
                    color: "#5a5a5a"
                }
                ScrollBar.vertical.background: Rectangle {
                    color: "transparent"
                }

                TextArea {
                    id: bodyInput
                    width: bodyScroll.availableWidth
                    implicitHeight: contentHeight + topPadding + bottomPadding
                    placeholderText: "Start typing..."
                    selectByMouse: true
                    wrapMode: TextEdit.WrapAtWordBoundaryOrAnywhere
                    color: "#f2f2f2"
                    placeholderTextColor: "#73777d"
                    font.family: "Segoe UI"
                    font.pointSize: 10
                    background: Item {}
                    onTextChanged: editor._preview()
                }
            }

            EditorFontSizeCombo {
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

        Row {
            id: metaRow
            width: parent.width
            height: 16
            spacing: 12

            Text {
                width: (parent.width - parent.spacing) / 2
                text: "Added: " + editor.createdAt
                color: "#8d949e"
                font.family: "Segoe UI"
                font.pointSize: 8
                elide: Text.ElideRight
            }

            Text {
                width: (parent.width - parent.spacing) / 2
                text: "Edited: " + editor.updatedAt
                color: "#8d949e"
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

            Rectangle {
                id: saveButton
                width: (parent.width - parent.spacing) / 2
                height: parent.height
                radius: 6
                scale: saveMouse.pressed && editor.hasContent ? 0.97 : 1.0
                color: !editor.hasContent ? "#3a3d41"
                       : (saveMouse.pressed ? "#1e6b3d"
                          : (saveMouse.containsMouse ? "#185733" : "#124326"))
                opacity: editor.hasContent ? 1.0 : 0.85

                Behavior on color { ColorAnimation { duration: 180 } }
                Behavior on opacity { NumberAnimation { duration: 180 } }
                Behavior on scale { NumberAnimation { duration: 80 } }

                Text {
                    anchors.centerIn: parent
                    text: "Save"
                    color: editor.hasContent ? "#ffffff" : "#a3a7ad"
                    font.family: "Segoe UI Semibold"
                    font.pointSize: 10
                }

                MouseArea {
                    id: saveMouse
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: editor.hasContent ? Qt.PointingHandCursor : Qt.ArrowCursor
                    enabled: editor.hasContent
                    onClicked: editor.saveAndClose()
                }

                ToolTip.visible: saveMouse.containsMouse
                ToolTip.text: "Save: Ctrl+S / Ctrl+Enter"
                ToolTip.delay: 450
            }

            Rectangle {
                id: cancelButton
                width: (parent.width - parent.spacing) / 2
                height: parent.height
                radius: 6
                scale: cancelMouse.pressed ? 0.97 : 1.0
                color: editor.hasContent
                       ? (cancelMouse.pressed ? "#682529"
                          : (cancelMouse.containsMouse ? "#512024" : "#3b1718"))
                       : (cancelMouse.pressed ? "#59343b"
                          : (cancelMouse.containsMouse ? "#442a30" : "#342326"))

                Behavior on color { ColorAnimation { duration: 180 } }
                Behavior on scale { NumberAnimation { duration: 80 } }

                Text {
                    anchors.centerIn: parent
                    text: "Delete"
                    opacity: editor.hasContent ? 0.0 : 1.0
                    color: "#f1d8dc"
                    font.family: "Segoe UI"
                    font.pointSize: 10
                    Behavior on opacity { NumberAnimation { duration: 130 } }
                }

                Text {
                    anchors.centerIn: parent
                    text: "Cancel"
                    opacity: editor.hasContent ? 1.0 : 0.0
                    color: "#ffffff"
                    font.family: "Segoe UI"
                    font.pointSize: 10
                    Behavior on opacity { NumberAnimation { duration: 130 } }
                }

                MouseArea {
                    id: cancelMouse
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: editor.cancelOrDelete()
                }

                ToolTip.visible: cancelMouse.containsMouse
                ToolTip.text: editor.hasContent ? "Cancel: Esc" : "Delete: Esc"
                ToolTip.delay: 450
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
