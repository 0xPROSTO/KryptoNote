pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Window


Popup {
    id: commandPalette
    objectName: "commandPalette"
    required property var appTheme
    required property var commandController
    required property var nodeModel

    signal requestedCenter(int nodeId)
    signal requestedFullSearch(string query)
    signal restoreFocusRequested()

    parent: Overlay.overlay
    z: 50
    modal: true
    dim: true
    focus: true
    padding: 0
    closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside

    readonly property int rowHeight: 40
    readonly property int headerHeight: 24
    readonly property int maxVisibleItems: 24
    property int selectedIndex: -1
    property int actionCount: 0
    property int headerCount: 0
    property var previousFocusItem: null
    property bool keyboardNavigationActive: true
    property bool pointerHoverArmed: false
    property bool pointerScenePositionKnown: false
    property real pointerSceneX: 0
    property real pointerSceneY: 0
    property real motionOffset: 0
    property string activeQuery: queryInput.text.trim()
    property alias queryText: queryInput.text
    readonly property var hostWindow: paletteContent.hostWindow
    readonly property int modelCount: combinedModel.count
    readonly property string selectedKind:
            selectedIndex >= 0 && selectedIndex < combinedModel.count
            ? combinedModel.get(selectedIndex).kind : ""
    readonly property string selectedTitle:
            selectedIndex >= 0 && selectedIndex < combinedModel.count
            ? combinedModel.get(selectedIndex).title : ""
    readonly property real listContentHeight: resultList.contentHeight
    readonly property real listViewportHeight: resultList.height
    readonly property bool inputFocused: queryInput.activeFocus
    readonly property real desiredListHeight:
            Math.min(actionCount, maxVisibleItems) * rowHeight
            + headerCount * headerHeight
    readonly property real maxPopupHeight: parent ? Math.max(180, parent.height - 32) : 720

    width: parent ? Math.min(760, Math.max(420, parent.width - 32)) : 760
    height: Math.min(maxPopupHeight, 70 + desiredListHeight)

    Behavior on height {
        enabled: commandPalette.visible && commandPalette.appTheme.motionEnabled
        NumberAnimation {
            id: heightAnimation
            duration: commandPalette.appTheme.durationPanel
            easing.type: Easing.InOutCubic
        }
    }

    x: parent ? Math.max(16, (parent.width - width) / 2) : 0
    y: parent
       ? Math.max(16, Math.min(parent.height * 0.31 - 26, parent.height - height - 16))
       : 0
    opacity: 1
    scale: 1
    transformOrigin: Item.Top

    Overlay.modal: Rectangle {
        color: commandPalette.appTheme.overlayDim

        Behavior on opacity {
            NumberAnimation {
                duration: commandPalette.appTheme.durationState
                easing.type: Easing.InOutQuad
            }
        }
    }

    background: Rectangle {
        color: commandPalette.appTheme.bgPopover
        radius: 10
        border.width: 1
        border.color: commandPalette.appTheme.borderHover
        transform: Translate { y: commandPalette.motionOffset }
    }

    enter: Transition {
        ParallelAnimation {
            NumberAnimation {
                property: "opacity"
                from: 0
                to: 1
                duration: commandPalette.appTheme.durationState
                easing.type: Easing.OutCubic
            }
            NumberAnimation {
                property: "scale"
                from: commandPalette.appTheme.motionEnabled ? 0.98 : 1
                to: 1
                duration: commandPalette.appTheme.motionEnabled
                          ? commandPalette.appTheme.durationPanel : 0
                easing.type: Easing.OutCubic
            }
            NumberAnimation {
                target: commandPalette
                property: "motionOffset"
                from: commandPalette.appTheme.motionEnabled ? -6 : 0
                to: 0
                duration: commandPalette.appTheme.motionEnabled
                          ? commandPalette.appTheme.durationPanel : 0
                easing.type: Easing.OutCubic
            }
        }
    }

    exit: Transition {
        ParallelAnimation {
            NumberAnimation {
                property: "opacity"
                from: 1
                to: 0
                duration: commandPalette.appTheme.durationExit
                easing.type: Easing.InOutQuad
            }
            NumberAnimation {
                property: "scale"
                from: 1
                to: commandPalette.appTheme.motionEnabled ? 0.996 : 1
                duration: commandPalette.appTheme.motionEnabled
                          ? commandPalette.appTheme.durationExit : 0
                easing.type: Easing.InOutCubic
            }
            NumberAnimation {
                target: commandPalette
                property: "motionOffset"
                from: 0
                to: commandPalette.appTheme.motionEnabled ? -3 : 0
                duration: commandPalette.appTheme.motionEnabled
                          ? commandPalette.appTheme.durationExit : 0
                easing.type: Easing.InOutCubic
            }
        }
    }

    onAboutToShow: {
        var hostWindow = commandPalette.hostWindow
        previousFocusItem = hostWindow ? hostWindow.activeFocusItem : null
        queryInput.text = ""
        searchDebounce.stop()
        keyboardNavigationActive = true
        resetPointerHoverTracking()
        refreshResults()
    }

    onOpened: Qt.callLater(function() {
        queryInput.forceActiveFocus()
    })

    onClosed: {
        searchDebounce.stop()
        resetPointerHoverTracking()
        var focusItem = previousFocusItem
        previousFocusItem = null
        Qt.callLater(function() {
            if (focusItem && focusItem.visible && focusItem.enabled
                    && typeof focusItem.forceActiveFocus === "function") {
                focusItem.forceActiveFocus()
            } else {
                commandPalette.restoreFocusRequested()
            }
        })
    }

    contentItem: Item {
        id: paletteContent
        readonly property var hostWindow: Window.window
        implicitWidth: commandPalette.width
        implicitHeight: commandPalette.height
        transform: Translate { y: commandPalette.motionOffset }

        Rectangle {
            id: inputSurface
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.top: parent.top
            anchors.margins: 8
            height: 46
            radius: 7
            color: commandPalette.appTheme.bgInput
            border.width: 1
            border.color: queryInput.activeFocus
                          ? commandPalette.appTheme.accentMain
                          : commandPalette.appTheme.borderDefault

            Behavior on border.color {
                ColorAnimation { duration: commandPalette.appTheme.durationState }
            }

            ToolButton {
                id: searchGlyph
                anchors.left: parent.left
                anchors.leftMargin: 5
                anchors.verticalCenter: parent.verticalCenter
                width: 32
                height: 32
                enabled: false
                display: AbstractButton.IconOnly
                icon.source: "../assets/icons/search.svg"
                icon.width: 17
                icon.height: 17
                icon.color: commandPalette.appTheme.textDim
                background: Item {}
                Accessible.ignored: true
            }

            TextField {
                id: queryInput
                objectName: "commandPaletteInput"
                focus: true
                anchors.left: searchGlyph.right
                anchors.right: shortcutHint.left
                anchors.top: parent.top
                anchors.bottom: parent.bottom
                anchors.rightMargin: 8
                leftPadding: 0
                rightPadding: 0
                selectByMouse: true
                placeholderText: "Type a command or search notes"
                color: commandPalette.appTheme.textMain
                placeholderTextColor: commandPalette.appTheme.textDim
                font.family: "Segoe UI Semibold"
                font.pointSize: 11
                background: Item {}
                ContextMenu.menu: null
                Accessible.name: "Command palette"
                Accessible.description: "Type a command or search the current project"

                onTextChanged: searchDebounce.restart()

                Keys.onShortcutOverride: function(event) {
                    if (commandPalette.isNavigationKey(event.key))
                        event.accepted = true
                }

                Keys.onPressed: function(event) {
                    if (event.key === Qt.Key_Down) {
                        commandPalette.startKeyboardNavigation()
                        commandPalette.moveSelection(1)
                        event.accepted = true
                    } else if (event.key === Qt.Key_Up) {
                        commandPalette.startKeyboardNavigation()
                        commandPalette.moveSelection(-1)
                        event.accepted = true
                    } else if (event.key === Qt.Key_Home) {
                        commandPalette.startKeyboardNavigation()
                        commandPalette.selectBoundary(true)
                        event.accepted = true
                    } else if (event.key === Qt.Key_End) {
                        commandPalette.startKeyboardNavigation()
                        commandPalette.selectBoundary(false)
                        event.accepted = true
                    } else if (event.key === Qt.Key_PageDown) {
                        commandPalette.startKeyboardNavigation()
                        commandPalette.movePage(1)
                        event.accepted = true
                    } else if (event.key === Qt.Key_PageUp) {
                        commandPalette.startKeyboardNavigation()
                        commandPalette.movePage(-1)
                        event.accepted = true
                    } else if (event.key === Qt.Key_Tab) {
                        commandPalette.completeSelectedCommand()
                        event.accepted = true
                    } else if (event.key === Qt.Key_Return
                               || event.key === Qt.Key_Enter) {
                        commandPalette.activateIndex(commandPalette.selectedIndex)
                        event.accepted = true
                    } else if (event.key === Qt.Key_Escape) {
                        commandPalette.close()
                        event.accepted = true
                    }
                }
            }

            Text {
                id: shortcutHint
                anchors.right: parent.right
                anchors.rightMargin: 12
                anchors.verticalCenter: parent.verticalCenter
                text: "Ctrl+Space"
                color: commandPalette.appTheme.textMuted
                font.family: "Segoe UI"
                font.pointSize: 8
                Accessible.ignored: true
            }
        }

        Rectangle {
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.top: inputSurface.bottom
            anchors.topMargin: 8
            height: 1
            color: commandPalette.appTheme.borderSubtle
        }

        ListView {
            id: resultList
            objectName: "commandPaletteResults"
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.top: inputSurface.bottom
            anchors.bottom: parent.bottom
            anchors.topMargin: 9
            anchors.bottomMargin: 7
            anchors.leftMargin: 6
            anchors.rightMargin: 6
            clip: true
            model: ListModel { id: combinedModel }
            currentIndex: commandPalette.selectedIndex
            boundsBehavior: Flickable.StopAtBounds
            Accessible.role: Accessible.List
            Accessible.name: "Commands and search results"

            ScrollBar.vertical: ScrollBar {
                policy: resultList.contentHeight > resultList.height
                        ? ScrollBar.AsNeeded : ScrollBar.AlwaysOff
            }

            delegate: Item {
                id: resultRow
                objectName: "commandPaletteResultRow"
                required property int index
                required property string kind
                required property bool selectable
                required property bool rowEnabled
                required property string commandId
                required property int nodeId
                required property string title
                required property string subtitle
                required property string shortcut
                required property string iconSource

                width: resultList.width
                height: kind === "header"
                        ? commandPalette.headerHeight : commandPalette.rowHeight
                clip: true
                readonly property bool pointerHighlighted:
                        !commandPalette.keyboardNavigationActive
                        && commandPalette.pointerHoverArmed
                        && rowHover.hovered
                readonly property bool keyboardHighlighted:
                        commandPalette.keyboardNavigationActive
                        && resultRow.index === commandPalette.selectedIndex
                readonly property bool visuallyHighlighted:
                        pointerHighlighted || keyboardHighlighted

                Rectangle {
                    id: selectionSurface
                    anchors.fill: parent
                    anchors.leftMargin: 2
                    anchors.rightMargin: 2
                    radius: 6
                    visible: resultRow.kind !== "header"
                    color: resultRow.visuallyHighlighted
                           ? commandPalette.appTheme.accentLow
                           : (resultRow.pointerHighlighted
                              ? commandPalette.appTheme.bgControlHover
                              : "transparent")
                    border.width: resultRow.visuallyHighlighted ? 1 : 0
                    border.color: commandPalette.appTheme.accentMain
                }

                Text {
                    visible: resultRow.kind === "header"
                    anchors.left: parent.left
                    anchors.leftMargin: 10
                    anchors.verticalCenter: parent.verticalCenter
                    text: resultRow.title
                    color: commandPalette.appTheme.textMuted
                    font.family: "Segoe UI Semibold"
                    font.pointSize: 8
                    font.capitalization: Font.AllUppercase
                    Accessible.ignored: true
                }

                ToolButton {
                    id: rowIcon
                    visible: resultRow.kind !== "header" && resultRow.iconSource.length > 0
                    anchors.left: parent.left
                    anchors.leftMargin: 5
                    anchors.verticalCenter: parent.verticalCenter
                    width: 34
                    height: 34
                    enabled: false
                    display: AbstractButton.IconOnly
                    opacity: resultRow.rowEnabled ? 1 : 0.5
                    icon.source: resultRow.iconSource
                    icon.width: 16
                    icon.height: 16
                    icon.color: resultRow.pointerHighlighted
                                || resultRow.keyboardHighlighted
                                ? commandPalette.appTheme.accentMain
                                : commandPalette.appTheme.textDim
                    background: Item {}
                    Accessible.ignored: true
                }

                Column {
                    visible: resultRow.kind !== "header"
                    anchors.left: rowIcon.visible ? rowIcon.right : parent.left
                    anchors.leftMargin: rowIcon.visible ? 1 : 12
                    anchors.right: shortcutText.visible ? shortcutText.left : parent.right
                    anchors.rightMargin: shortcutText.visible ? 12 : 14
                    anchors.verticalCenter: parent.verticalCenter
                    spacing: resultRow.subtitle.length > 0 ? 1 : 0
                    clip: true

                    Text {
                        width: parent.width
                        text: commandPalette.highlighted(resultRow.title)
                        textFormat: Text.StyledText
                        color: resultRow.rowEnabled
                               ? commandPalette.appTheme.textMain
                               : commandPalette.appTheme.textDisabled
                        font.family: "Segoe UI"
                        font.pointSize: 9
                        elide: Text.ElideRight
                        maximumLineCount: 1
                    }

                    Text {
                        width: parent.width
                        visible: resultRow.subtitle.length > 0
                        text: commandPalette.highlighted(resultRow.subtitle)
                        textFormat: Text.StyledText
                        color: resultRow.rowEnabled
                               ? commandPalette.appTheme.textDim
                               : commandPalette.appTheme.textDisabled
                        font.family: "Segoe UI"
                        font.pointSize: 8
                        elide: Text.ElideRight
                        maximumLineCount: 1
                    }
                }

                Text {
                    id: shortcutText
                    visible: resultRow.kind !== "header" && resultRow.shortcut.length > 0
                    anchors.right: parent.right
                    anchors.rightMargin: 12
                    anchors.verticalCenter: parent.verticalCenter
                    text: resultRow.shortcut
                    color: commandPalette.appTheme.textMuted
                    font.family: "Segoe UI"
                    font.pointSize: 8
                    Accessible.ignored: true
                }

                HoverHandler {
                    id: rowHover
                    enabled: resultRow.selectable && resultRow.rowEnabled
                    onHoveredChanged: {
                        if (hovered) {
                            commandPalette.updatePointerSelection(
                                resultRow.index,
                                rowHover.point.scenePosition
                            )
                        }
                    }
                    onPointChanged: {
                        if (hovered) {
                            commandPalette.updatePointerSelection(
                                resultRow.index,
                                rowHover.point.scenePosition
                            )
                        }
                    }
                }

                TapHandler {
                    enabled: resultRow.selectable && resultRow.rowEnabled
                    onTapped: commandPalette.activateIndex(resultRow.index)
                }

                Accessible.role: resultRow.selectable
                                 ? Accessible.ListItem : Accessible.StaticText
                Accessible.name: resultRow.title
                Accessible.description: resultRow.subtitle
            }
        }
    }

    Timer {
        id: searchDebounce
        interval: 60
        repeat: false
        onTriggered: commandPalette.refreshResults()
    }

    function openPalette() {
        if (visible) return
        open()
    }

    function closePalette() {
        if (visible) close()
    }

    function togglePalette() {
        if (visible) close()
        else open()
    }

    function appendRow(values) {
        combinedModel.append({
            "kind": String(values.kind || "command"),
            "selectable": Boolean(values.selectable),
            "rowEnabled": values.rowEnabled === undefined
                          ? true : Boolean(values.rowEnabled),
            "commandId": String(values.commandId || ""),
            "nodeId": Number(values.nodeId || 0),
            "title": String(values.title || ""),
            "subtitle": String(values.subtitle || ""),
            "shortcut": String(values.shortcut || ""),
            "iconSource": String(values.iconSource || "")
        })
    }

    function appendHeader(title) {
        appendRow({
            "kind": "header",
            "selectable": false,
            "rowEnabled": false,
            "title": title
        })
        headerCount += 1
    }

    function refreshResults() {
        // Reset the current item before rebuilding.  Keeping the same numeric
        // index through ListModel.clear() lets ListView reuse a stale
        // highlight position, which can paint selection over a section header
        // while activation still targets the correct command.
        keyboardNavigationActive = true
        resetPointerHoverTracking()
        selectedIndex = -1
        combinedModel.clear()
        actionCount = 0
        headerCount = 0
        var query = queryInput.text.trim()
        var commands = commandController.query_commands(query)
        if (commands.length > 0) {
            appendHeader("Commands")
            for (var i = 0; i < commands.length; i++) {
                var command = commands[i]
                appendRow({
                    "kind": "command",
                    "selectable": true,
                    "rowEnabled": command.enabled,
                    "commandId": command.id,
                    "title": command.label,
                    "subtitle": command.enabled ? "" : command.reason,
                    "shortcut": command.shortcut,
                    "iconSource": command.icon
                })
                actionCount += 1
            }
        }

        if (query.length > 0) {
            var results = nodeModel.search_nodes_by_filters(
                query, [], 0, 0, "", "", "relevance", 10
            )
            if (results.length > 0) {
                appendHeader("Search results")
                for (var j = 0; j < results.length; j++) {
                    var result = results[j]
                    appendRow({
                        "kind": "search",
                        "selectable": true,
                        "rowEnabled": true,
                        "nodeId": result.nodeId,
                        "title": result.title.length > 0 ? result.title : "(untitled)",
                        "subtitle": commandPalette.centeredPreview(result.preview, query),
                        "iconSource": commandPalette.nodeIcon(result.type)
                    })
                    actionCount += 1
                }
            }
            appendRow({
                "kind": "full-search",
                "selectable": true,
                "rowEnabled": true,
                "title": "Search: " + query,
                "subtitle": "Open the full search panel",
                "shortcut": "Enter",
                "iconSource": "../assets/icons/search.svg"
            })
            actionCount += 1
        }

        selectedIndex = firstSelectable(0, 1)
        if (selectedIndex >= 0) {
            resultList.positionViewAtIndex(selectedIndex, ListView.Contain)
        }
    }

    function startKeyboardNavigation() {
        keyboardNavigationActive = true
    }

    function resetPointerHoverTracking() {
        pointerHoverArmed = false
        pointerScenePositionKnown = false
    }

    function updatePointerSelection(index, scenePosition) {
        var nextX = Number(scenePosition.x)
        var nextY = Number(scenePosition.y)
        if (!pointerScenePositionKnown) {
            pointerScenePositionKnown = true
            pointerSceneX = nextX
            pointerSceneY = nextY
            return
        }
        var deltaX = nextX - pointerSceneX
        var deltaY = nextY - pointerSceneY
        if (deltaX * deltaX + deltaY * deltaY <= 1) return
        pointerSceneX = nextX
        pointerSceneY = nextY
        pointerHoverArmed = true
        keyboardNavigationActive = false
        selectIndex(index)
    }

    function firstSelectable(start, direction) {
        if (combinedModel.count <= 0) return -1
        var index = Math.max(0, Math.min(combinedModel.count - 1, start))
        while (index >= 0 && index < combinedModel.count) {
            var row = combinedModel.get(index)
            if (row.selectable && row.rowEnabled) return index
            index += direction
        }
        return -1
    }

    function selectIndex(index) {
        if (index < 0 || index >= combinedModel.count) return
        var row = combinedModel.get(index)
        if (!row.selectable || !row.rowEnabled) return
        selectedIndex = index
        resultList.positionViewAtIndex(index, ListView.Contain)
    }

    function moveSelection(direction) {
        if (combinedModel.count <= 0) return
        var index = selectedIndex
        for (var i = 0; i < combinedModel.count; i++) {
            index += direction
            if (index < 0) index = combinedModel.count - 1
            if (index >= combinedModel.count) index = 0
            var row = combinedModel.get(index)
            if (row.selectable && row.rowEnabled) {
                selectIndex(index)
                return
            }
        }
    }

    function movePage(direction) {
        var page = Math.max(1, Math.floor(resultList.height / rowHeight) - 1)
        if (selectedIndex < 0) {
            selectBoundary(direction < 0)
            return
        }
        var target = Math.max(
            0,
            Math.min(combinedModel.count - 1, selectedIndex + direction * page)
        )
        var index = firstSelectable(target, direction)
        if (index < 0) {
            index = direction < 0
                    ? firstSelectable(0, 1)
                    : firstSelectable(combinedModel.count - 1, -1)
        }
        if (index >= 0) selectIndex(index)
    }

    function isNavigationKey(key) {
        return key === Qt.Key_Down
                || key === Qt.Key_Up
                || key === Qt.Key_Home
                || key === Qt.Key_End
                || key === Qt.Key_PageDown
                || key === Qt.Key_PageUp
                || key === Qt.Key_Return
                || key === Qt.Key_Enter
                || key === Qt.Key_Tab
                || key === Qt.Key_Escape
    }

    function selectBoundary(first) {
        var index = first
                    ? firstSelectable(0, 1)
                    : firstSelectable(combinedModel.count - 1, -1)
        if (index >= 0) selectIndex(index)
    }

    function completeSelectedCommand() {
        if (selectedIndex < 0 || selectedIndex >= combinedModel.count) return
        var row = combinedModel.get(selectedIndex)
        if (row.kind !== "command" || !row.rowEnabled) return
        queryInput.text = row.title
        queryInput.cursorPosition = queryInput.text.length
    }

    function activateIndex(index) {
        if (index < 0 || index >= combinedModel.count) return
        var row = combinedModel.get(index)
        if (!row.selectable || !row.rowEnabled) return
        if (row.kind === "command") {
            var commandId = row.commandId
            close()
            Qt.callLater(function() {
                commandController.execute_command(commandId)
            })
        } else if (row.kind === "search") {
            var nodeId = row.nodeId
            close()
            Qt.callLater(function() {
                commandPalette.requestedCenter(nodeId)
            })
        } else if (row.kind === "full-search") {
            var query = queryInput.text.trim()
            close()
            Qt.callLater(function() {
                commandPalette.requestedFullSearch(query)
            })
        }
    }

    function escapeHtml(value) {
        return String(value || "")
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/\"/g, "&quot;")
            .replace(/'/g, "&#39;")
    }

    function highlighted(value) {
        var source = String(value || "")
        var needle = activeQuery
        if (needle.length <= 0) return escapeHtml(source)
        var foldedSource = source.toLocaleLowerCase()
        var foldedNeedle = needle.toLocaleLowerCase()
        var result = ""
        var offset = 0
        while (offset < source.length) {
            var index = foldedSource.indexOf(foldedNeedle, offset)
            if (index < 0) break
            result += escapeHtml(source.substring(offset, index))
            result += "<b>" + escapeHtml(
                source.substring(index, index + needle.length)
            ) + "</b>"
            offset = index + needle.length
        }
        return result + escapeHtml(source.substring(offset))
    }

    function singleLine(value) {
        return String(value || "").replace(/\s+/g, " ").trim()
    }

    function centeredPreview(value, needleValue) {
        var source = singleLine(value)
        var needle = String(needleValue || "").trim()
        if (source.length <= 0 || needle.length <= 0) return source

        var index = source.toLocaleLowerCase().indexOf(
            needle.toLocaleLowerCase()
        )
        if (index < 0) return source

        var start = Math.max(0, index - 44)
        var excerpt = source.substring(start).trim()
        if (start > 0 && excerpt.charAt(0) !== "…") excerpt = "…" + excerpt
        return excerpt
    }

    function nodeIcon(nodeType) {
        if (nodeType === "image") return "../assets/icons/image.svg"
        if (nodeType === "video") return "../assets/icons/video.svg"
        if (nodeType === "audio") return "../assets/icons/play.svg"
        if (nodeType === "frame") return "../assets/icons/frame.svg"
        return "../assets/icons/note.svg"
    }
}
