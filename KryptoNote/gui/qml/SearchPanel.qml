pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls.Basic

Item {
    id: searchPanel
    required property var nodeModel
    required property var canvasController

    required property var appTheme
    property bool open: false
    property bool panelVisible: false
    property bool resizing: resizeMouse.pressed
    property real preferredWidth: parent ? parent.width * 0.24 : 320
    property real minPanelWidth: parent ? Math.max(280, parent.width * 0.12) : 280
    property real maxPanelWidth: parent ? parent.width * 0.42 : 560
    property real slideOffset: open ? 0 : -width
    property int currentIndex: -1
    property string lastQuery: ""
    property string sortKey: "relevance"
    property string sortLabel: "Relevance"
    property bool convertingTags: false

    signal requestedCenter(int nodeId)
    signal requestedCloseCompensation(real panelWidth)
    signal statusChanged(string message)

    width: Math.max(minPanelWidth, Math.min(maxPanelWidth, preferredWidth))
    height: parent ? parent.height : 0
    visible: panelVisible
    x: slideOffset

    onOpenChanged: {
        if (open) {
            hideTimer.stop()
            panelVisible = true
            focusSearchInput()
        } else {
            tagMenu.close()
            filterMenu.close()
            sortMenu.close()
            hideTimer.restart()
        }
    }

    Shortcut {
        sequence: "Esc"
        context: Qt.ApplicationShortcut
        enabled: searchPanel.open
        onActivated: searchPanel.closePanel()
    }

    Rectangle { anchors.fill: parent; color: searchPanel.appTheme.bgPanel }
    Rectangle {
        width: 1
        anchors.right: parent.right; anchors.top: parent.top; anchors.bottom: parent.bottom
        color: searchPanel.appTheme.borderDefault
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
        z: 5
        width: 7
        anchors.right: parent.right; anchors.top: parent.top; anchors.bottom: parent.bottom
        color: resizeMouse.containsMouse || resizeMouse.pressed ? searchPanel.appTheme.accentMain : "transparent"
        opacity: resizeMouse.containsMouse || resizeMouse.pressed ? 0.55 : 0
        Behavior on opacity { NumberAnimation { duration: 120 } }

        MouseArea {
            id: resizeMouse
            anchors.fill: parent
            hoverEnabled: true
            preventStealing: true
            cursorShape: Qt.SizeHorCursor
            property real pressSceneX: 0
            property real startPreferredWidth: 0
            onPressed: function(mouse) {
                pressSceneX = mapToItem(searchPanel.parent, mouse.x, mouse.y).x
                startPreferredWidth = searchPanel.preferredWidth
            }
            onPositionChanged: function(mouse) {
                if (!pressed) return
                var sceneX = mapToItem(searchPanel.parent, mouse.x, mouse.y).x
                searchPanel.preferredWidth = Math.max(
                    searchPanel.minPanelWidth,
                    Math.min(searchPanel.maxPanelWidth, startPreferredWidth + sceneX - pressSceneX)
                )
            }
        }
    }

    Column {
        id: headerColumn
        z: 2
        anchors.left: parent.left; anchors.right: parent.right; anchors.top: parent.top
        anchors.leftMargin: 14; anchors.rightMargin: 14; anchors.topMargin: 14
        spacing: 8

        Rectangle {
            id: searchField
            objectName: "searchField"
            width: parent.width
            height: 42
            radius: 8
            color: searchPanel.appTheme.bgInput
            border.width: 1
            border.color: searchInput.activeFocus
                          ? searchPanel.appTheme.accentMain
                          : (searchFieldHover.hovered ? searchPanel.appTheme.borderHover
                                                      : searchPanel.appTheme.borderDefault)

            Behavior on border.color { ColorAnimation { duration: 120 } }
            HoverHandler { id: searchFieldHover }

            ToolButton {
                id: leadingSearchIcon
                objectName: "searchLeadingIcon"
                anchors.left: parent.left
                anchors.leftMargin: 4
                anchors.verticalCenter: parent.verticalCenter
                width: 30
                height: 30
                enabled: false
                opacity: 0.78
                display: AbstractButton.IconOnly
                icon.source: "../assets/icons/search.svg"
                icon.width: 16
                icon.height: 16
                icon.color: searchPanel.appTheme.textDim
                background: Item {}
                Accessible.ignored: true
            }

            TextField {
                id: searchInput
                objectName: "searchInput"
                anchors.left: leadingSearchIcon.right; anchors.right: tagButton.left
                anchors.top: parent.top; anchors.bottom: parent.bottom
                anchors.leftMargin: 1; anchors.rightMargin: 6
                leftPadding: 0
                rightPadding: 0
                placeholderText: "Search notes"
                selectByMouse: true
                color: searchPanel.appTheme.textMain
                placeholderTextColor: searchPanel.appTheme.textDim
                font.family: "Segoe UI Semibold"; font.pointSize: 10
                background: Item {}
                ContextMenu.menu: null
                onTextChanged: {
                    if (!searchPanel.convertingTags) {
                        if (text.endsWith(" ")) searchPanel.captureTypedTags()
                        searchPanel.invalidateSearch()
                    }
                }
                Keys.onPressed: function(event) {
                    if (event.key === Qt.Key_Return || event.key === Qt.Key_Enter) {
                        searchPanel.searchOrNext()
                        event.accepted = true
                    }
                }
            }

            HeaderButton {
                id: tagButton
                anchors.right: findButton.left; anchors.rightMargin: 4
                anchors.verticalCenter: parent.verticalCenter
                width: 32
                iconSource: "../assets/icons/tag.svg"
                toolTip: "Add tag filter"
                active: tagMenu.visible || selectedTagModel.count > 0
                onClicked: {
                    if (!tagMenu.visible) searchPanel.refreshSearchTags()
                    searchPanel.toggleBelow(tagMenu, tagButton)
                }
            }
            HeaderButton {
                id: findButton
                anchors.right: closeButton.left; anchors.rightMargin: 4
                anchors.verticalCenter: parent.verticalCenter
                width: 62
                text: "Find"
                iconSource: "../assets/icons/search.svg"
                prominent: true
                toolTip: "Find next (Enter)"
                onClicked: searchPanel.searchOrNext()
            }
            HeaderButton {
                id: closeButton
                anchors.right: parent.right; anchors.rightMargin: 4
                anchors.verticalCenter: parent.verticalCenter
                width: 32
                iconSource: "../assets/icons/close.svg"
                toolTip: "Close"
                danger: true
                onClicked: searchPanel.closePanel()
            }
        }

        Flickable {
            id: selectedTagsStrip
            width: parent.width
            height: selectedTagModel.count > 0 ? 25 : 0
            visible: height > 0
            contentWidth: selectedTagsRow.width
            contentHeight: height
            flickableDirection: Flickable.HorizontalFlick
            boundsBehavior: Flickable.StopAtBounds
            clip: true

            Row {
                id: selectedTagsRow
                height: parent.height
                spacing: 5
                Repeater {
                    model: ListModel { id: selectedTagModel }
                    Rectangle {
                        id: searchTagChip
                        required property int tagId
                        required property string tagName
                        required property string tagColor
                        property color chipColor: tagColor
                        height: 23
                        width: Math.min(160, Math.max(48, chipText.implicitWidth + 34))
                        radius: 7
                        color: Qt.rgba(chipColor.r, chipColor.g, chipColor.b, 0.18)
                        border.width: 1; border.color: chipColor
                        Text {
                            id: chipText
                            anchors.left: parent.left; anchors.leftMargin: 8
                            anchors.right: removeChipButton.left; anchors.rightMargin: 2
                            anchors.verticalCenter: parent.verticalCenter
                            text: "@" + searchTagChip.tagName
                            color: searchPanel.appTheme.textMain
                            elide: Text.ElideRight
                            font.family: "Segoe UI Semibold"; font.pointSize: 8
                        }
                        ToolButton {
                            id: removeChipButton
                            anchors.right: parent.right; anchors.rightMargin: 2
                            anchors.verticalCenter: parent.verticalCenter
                            width: 20; height: 20
                            hoverEnabled: true
                            focusPolicy: Qt.TabFocus
                            display: AbstractButton.IconOnly
                            icon.source: "../assets/icons/close.svg"
                            icon.width: 11; icon.height: 11
                            icon.color: hovered || visualFocus
                                        ? searchPanel.appTheme.btnCancelText : searchPanel.appTheme.textDim
                            background: Rectangle {
                                radius: 5
                                color: removeChipButton.down ? searchPanel.appTheme.whiteAlpha15
                                     : removeChipButton.hovered ? searchPanel.appTheme.whiteAlpha10
                                     : "transparent"
                                border.width: removeChipButton.visualFocus ? 1 : 0
                                border.color: searchPanel.appTheme.accentMain
                            }
                            Accessible.name: "Remove @" + searchTagChip.tagName + " filter"
                            ToolTip.visible: hovered
                            ToolTip.text: Accessible.name
                            ToolTip.delay: 500
                            onClicked: {
                                searchPanel.removeSelectedTag(searchTagChip.tagId)
                                searchPanel.invalidateSearch()
                            }
                        }
                    }
                }
            }
        }

        Row {
            width: parent.width
            height: 30
            spacing: 6
            ToolbarButton {
                id: filtersButton
                width: Math.min(112, (parent.width - parent.spacing) * 0.42)
                text: searchPanel.activeFilterCount() > 0
                      ? "Filters · " + searchPanel.activeFilterCount() : "Filters"
                iconSource: "../assets/icons/filter.svg"
                active: filterMenu.visible || searchPanel.activeFilterCount() > 0
                onClicked: searchPanel.toggleBelow(filterMenu, filtersButton)
            }
            ToolbarButton {
                id: sortButton
                width: parent.width - filtersButton.width - parent.spacing
                text: "Sort: " + searchPanel.sortLabel
                iconSource: "../assets/icons/sort.svg"
                active: sortMenu.visible
                onClicked: searchPanel.toggleBelow(sortMenu, sortButton)
            }
        }
    }

    Rectangle {
        id: divider
        anchors.left: parent.left; anchors.right: parent.right
        anchors.top: headerColumn.bottom; anchors.topMargin: 10
        height: 1; color: searchPanel.appTheme.borderDefault
    }

    ListView {
        id: resultList
        anchors.left: parent.left; anchors.right: parent.right
        anchors.top: divider.bottom; anchors.bottom: parent.bottom
        anchors.leftMargin: 14; anchors.rightMargin: 14; anchors.topMargin: 10
        clip: true
        spacing: 8
        model: ListModel { id: resultModel }
        boundsBehavior: Flickable.StopAtBounds
        cacheBuffer: Math.max(0, height * 2)
        currentIndex: searchPanel.currentIndex

        ScrollBar.vertical: ScrollBar {
            policy: resultList.contentHeight > resultList.height ? ScrollBar.AsNeeded : ScrollBar.AlwaysOff
        }

        delegate: Rectangle {
            id: resultCard
            required property int index
            required property int nodeId
            required property string title
            required property string preview
            required property string meta
            width: resultList.width - 2
            height: Math.min(218, Math.max(82, resultContent.implicitHeight + 20))
            radius: 7
            clip: true
            color: resultMouse.containsMouse ? searchPanel.appTheme.bgControl : searchPanel.appTheme.bgNode
            border.width: index === searchPanel.currentIndex ? 1.5 : 1
            border.color: index === searchPanel.currentIndex ? searchPanel.appTheme.accentMain : searchPanel.appTheme.borderDefault
            Behavior on color { ColorAnimation { duration: 110 } }

            Column {
                id: resultContent
                x: 11; y: 9; width: parent.width - 22; spacing: 5
                Text {
                    width: parent.width
                    text: resultCard.title.length > 0 ? resultCard.title : "(untitled)"
                    color: searchPanel.appTheme.accentMain
                    font.family: "Segoe UI Semibold"; font.pointSize: 10
                    elide: Text.ElideRight; maximumLineCount: 1
                }
                Text {
                    width: parent.width
                    text: resultCard.preview
                    color: searchPanel.appTheme.textMain
                    font.family: "Segoe UI"; font.pointSize: 9
                    textFormat: Text.MarkdownText
                    wrapMode: Text.WordWrap; elide: Text.ElideRight
                    maximumLineCount: 7
                }
                Text {
                    width: parent.width
                    text: resultCard.meta
                    color: searchPanel.appTheme.textDim
                    font.family: "Segoe UI"; font.pointSize: 8
                    elide: Text.ElideRight; maximumLineCount: 1
                }
            }
            MouseArea {
                id: resultMouse
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onClicked: searchPanel.activateResult(resultCard.index)
            }
        }
    }

    Popup {
        id: tagMenu
        parent: searchPanel
        z: 20
        width: Math.min(260, searchPanel.width - 28)
        height: Math.min(310, tagMenuContent.implicitHeight + topPadding + bottomPadding)
        padding: 10
        modal: true; dim: false
        focus: true
        closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside
        background: MenuBackground {}
        contentItem: Column {
            id: tagMenuContent
            spacing: 7
            MenuTitle { text: "Filter by tag" }
            Text {
                visible: searchTagMenuModel.count === 0
                height: visible ? 30 : 0
                text: "No tags yet"
                color: searchPanel.appTheme.textDim; font.pointSize: 9
                verticalAlignment: Text.AlignVCenter
            }
            ListView {
                id: searchTagList
                width: parent.width
                height: Math.min(245, contentHeight)
                model: ListModel { id: searchTagMenuModel }
                spacing: 2; clip: true; boundsBehavior: Flickable.StopAtBounds
                delegate: MenuRow {
                    required property int tagId
                    required property string tagName
                    required property string tagColor
                    required property bool selected
                    width: searchTagList.width
                    text: "@" + tagName
                    dotColor: tagColor
                    checked: selected
                    onClicked: {
                        searchPanel.toggleSelectedTag(tagId, tagName, tagColor)
                        searchPanel.refreshSearchTags()
                        searchPanel.invalidateSearch()
                    }
                }
            }
        }
    }

    Popup {
        id: filterMenu
        parent: searchPanel
        z: 20
        width: Math.min(300, searchPanel.width - 28)
        height: filterMenuContent.implicitHeight + topPadding + bottomPadding
        padding: 10
        modal: true; dim: false
        focus: true
        closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside
        background: MenuBackground {}
        contentItem: Column {
            id: filterMenuContent
            spacing: 8
            MenuTitle { text: "Filters" }
            Row {
                width: parent.width; height: 32; spacing: 6
                FilterInput { id: minCharsInput; width: (parent.width - 6) / 2; placeholder: "Min characters"; numeric: true }
                FilterInput { id: maxCharsInput; width: (parent.width - 6) / 2; placeholder: "Max characters"; numeric: true }
            }
            Row {
                width: parent.width; height: 32; spacing: 6
                FilterInput { id: createdAfterInput; width: (parent.width - 6) / 2; placeholder: "From YYYY-MM-DD" }
                FilterInput { id: createdBeforeInput; width: (parent.width - 6) / 2; placeholder: "To YYYY-MM-DD" }
            }
            Row {
                width: parent.width; height: 30; spacing: 6
                ToolbarButton {
                    width: (parent.width - 6) / 2
                    text: "Clear"
                    iconSource: "../assets/icons/reset.svg"
                    onClicked: {
                        minCharsInput.text = ""; maxCharsInput.text = ""
                        createdAfterInput.text = ""; createdBeforeInput.text = ""
                        filterMenu.close(); searchPanel.invalidateSearch()
                    }
                }
                ToolbarButton {
                    width: (parent.width - 6) / 2
                    text: "Apply"
                    iconSource: "../assets/icons/check.svg"
                    active: true
                    onClicked: { filterMenu.close(); searchPanel.invalidateSearch() }
                }
            }
        }
    }

    Popup {
        id: sortMenu
        parent: searchPanel
        z: 20
        width: Math.min(230, searchPanel.width - 28)
        height: sortMenuContent.implicitHeight + topPadding + bottomPadding
        padding: 8
        modal: true; dim: false
        focus: true
        closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside
        background: MenuBackground {}
        contentItem: Column {
            id: sortMenuContent
            spacing: 2
            Repeater {
                model: [
                    {key: "relevance", label: "Relevance"},
                    {key: "newest", label: "Newest first"},
                    {key: "oldest", label: "Oldest first"},
                    {key: "chars_desc", label: "Most characters"},
                    {key: "chars_asc", label: "Fewest characters"},
                    {key: "title", label: "Title A–Z"}
                ]
                MenuRow {
                    required property var modelData
                    width: parent.width
                    text: modelData.label
                    checked: searchPanel.sortKey === modelData.key
                    onClicked: {
                        searchPanel.sortKey = modelData.key
                        searchPanel.sortLabel = modelData.label
                        sortMenu.close()
                        searchPanel.invalidateSearch()
                    }
                }
            }
        }
    }

    component HeaderButton: ToolButton {
        id: headerControl
        property string toolTip: ""
        property bool active: false
        property bool danger: false
        property bool prominent: false
        property url iconSource: ""
        height: 30
        hoverEnabled: true
        focusPolicy: Qt.TabFocus
        display: text.length > 0 ? AbstractButton.TextBesideIcon : AbstractButton.IconOnly
        spacing: 5
        leftPadding: text.length > 0 ? 8 : 0
        rightPadding: text.length > 0 ? 8 : 0
        font.family: "Segoe UI Semibold"
        font.pointSize: 8
        palette.buttonText: danger ? searchPanel.appTheme.btnCancelText : searchPanel.appTheme.textMain
        icon.source: iconSource
        icon.width: 15
        icon.height: 15
        icon.color: danger ? (hovered ? searchPanel.appTheme.btnCancelText : searchPanel.appTheme.textDim)
                           : (active || prominent ? searchPanel.appTheme.textMain : searchPanel.appTheme.textDim)
        Accessible.name: toolTip.length > 0 ? toolTip : text

        background: Rectangle {
            radius: 6
            color: headerControl.down
                   ? (headerControl.prominent ? searchPanel.appTheme.accentHover : searchPanel.appTheme.bgControlPressed)
                   : (headerControl.hovered
                      ? (headerControl.prominent ? searchPanel.appTheme.accentMain : searchPanel.appTheme.bgControlHover)
                      : (headerControl.active || headerControl.prominent
                         ? searchPanel.appTheme.accentLow : "transparent"))
            border.width: headerControl.visualFocus || headerControl.active
                          || headerControl.prominent ? 1 : 0
            border.color: searchPanel.appTheme.accentMain
            Behavior on color { ColorAnimation { duration: 110 } }
        }

        ToolTip.visible: toolTip.length > 0 && hovered
        ToolTip.text: toolTip
        ToolTip.delay: 500
    }

    component ToolbarButton: ToolButton {
        id: toolbarControl
        property bool active: false
        property url iconSource: ""
        height: 30
        hoverEnabled: true
        focusPolicy: Qt.TabFocus
        display: iconSource.toString().length > 0
                 ? AbstractButton.TextBesideIcon : AbstractButton.TextOnly
        spacing: 6
        leftPadding: 8
        rightPadding: 8
        font.family: "Segoe UI Semibold"
        font.pointSize: 8
        palette.buttonText: active ? searchPanel.appTheme.textMain : searchPanel.appTheme.textDim
        icon.source: iconSource
        icon.width: 14
        icon.height: 14
        icon.color: active ? searchPanel.appTheme.textMain : searchPanel.appTheme.textDim

        background: Rectangle {
            radius: 6
            color: toolbarControl.down ? searchPanel.appTheme.bgControlPressed
                 : toolbarControl.hovered ? searchPanel.appTheme.bgControlHover
                 : toolbarControl.active ? searchPanel.appTheme.accentLow : searchPanel.appTheme.bgControl
            border.width: 1
            border.color: toolbarControl.visualFocus || toolbarControl.active
                          ? searchPanel.appTheme.accentMain : searchPanel.appTheme.borderDefault
            Behavior on color { ColorAnimation { duration: 110 } }
        }
    }

    component FilterInput: Rectangle {
        property alias text: filterField.text
        property alias placeholder: filterField.placeholderText
        property bool numeric: false
        height: 32; radius: 6; color: searchPanel.appTheme.bgInput
        border.width: 1
        border.color: filterField.activeFocus
                      ? searchPanel.appTheme.accentMain : searchPanel.appTheme.borderSubtle
        TextField {
            id: filterField
            anchors.fill: parent; anchors.leftMargin: 8; anchors.rightMargin: 8
            selectByMouse: true
            color: searchPanel.appTheme.textMain; placeholderTextColor: searchPanel.appTheme.textDim
            font.family: "Segoe UI"; font.pointSize: 8; background: Item {}
            ContextMenu.menu: null
            validator: parent.numeric ? intValidator : null
        }
        IntValidator { id: intValidator; bottom: 0 }
    }

    component MenuBackground: Rectangle {
        color: searchPanel.appTheme.bgPopover; radius: 9
        border.width: 1; border.color: searchPanel.appTheme.borderDefault
    }
    component MenuTitle: Text {
        width: parent ? parent.width : 0; height: 24
        color: searchPanel.appTheme.textMain
        font.family: "Segoe UI Semibold"; font.pointSize: 9
        verticalAlignment: Text.AlignVCenter
    }
    component MenuRow: Rectangle {
        id: menuRow
        property string text: ""
        property color dotColor: "transparent"
        property bool checked: false
        signal clicked()
        height: 32; radius: 6
        color: rowMouse.containsMouse ? searchPanel.appTheme.bgControlHover
             : checked ? searchPanel.appTheme.accentLow : "transparent"
        Rectangle {
            visible: menuRow.dotColor.a > 0
            width: 9; height: 9; radius: 5
            anchors.left: parent.left; anchors.leftMargin: 8
            anchors.verticalCenter: parent.verticalCenter
            color: menuRow.dotColor
        }
        Text {
            anchors.left: parent.left; anchors.leftMargin: menuRow.dotColor.a > 0 ? 25 : 9
            anchors.right: checkIcon.left; anchors.rightMargin: 6
            anchors.verticalCenter: parent.verticalCenter
            text: menuRow.text; color: searchPanel.appTheme.textMain
            font.family: "Segoe UI"; font.pointSize: 9; elide: Text.ElideRight
        }
        ToolButton {
            id: checkIcon
            anchors.right: parent.right
            anchors.rightMargin: 5
            anchors.verticalCenter: parent.verticalCenter
            width: 24
            height: 24
            visible: menuRow.checked
            enabled: false
            opacity: 1
            display: AbstractButton.IconOnly
            icon.source: "../assets/icons/check.svg"
            icon.width: 14
            icon.height: 14
            icon.color: searchPanel.appTheme.accentMain
            background: null
        }
        MouseArea {
            id: rowMouse; anchors.fill: parent; hoverEnabled: true
            cursorShape: Qt.PointingHandCursor; onClicked: parent.clicked()
        }
    }

    Timer {
        id: hideTimer; interval: 230; repeat: false
        onTriggered: if (!searchPanel.open) searchPanel.panelVisible = false
    }
    Timer {
        id: searchDebounce
        interval: 150
        repeat: false
        onTriggered: searchPanel.performSearch(searchInput.text.trim())
    }
    Behavior on slideOffset { NumberAnimation { duration: 220; easing.type: Easing.OutCubic } }

    function toggleBelow(popup, anchorItem) {
        if (popup.visible) {
            popup.close()
            return
        }
        if (popup !== tagMenu) tagMenu.close()
        if (popup !== filterMenu) filterMenu.close()
        if (popup !== sortMenu) sortMenu.close()
        var point = anchorItem.mapToItem(searchPanel, 0, anchorItem.height + 5)
        popup.x = Math.max(8, Math.min(point.x, searchPanel.width - popup.width - 8))
        popup.y = point.y
        popup.open()
    }

    function activeFilterCount() {
        var count = 0
        if (minCharsInput.text.length > 0) count++
        if (maxCharsInput.text.length > 0) count++
        if (createdAfterInput.text.length > 0) count++
        if (createdBeforeInput.text.length > 0) count++
        return count
    }

    function selectedTagIndex(tagId) {
        for (var i = 0; i < selectedTagModel.count; i++) {
            if (selectedTagModel.get(i).tagId === tagId) return i
        }
        return -1
    }

    function toggleSelectedTag(tagId, tagName, tagColor) {
        var index = selectedTagIndex(tagId)
        if (index >= 0) selectedTagModel.remove(index)
        else selectedTagModel.append({"tagId": tagId, "tagName": tagName, "tagColor": tagColor})
    }

    function removeSelectedTag(tagId) {
        var index = selectedTagIndex(tagId)
        if (index >= 0) selectedTagModel.remove(index)
    }

    function refreshSearchTags() {
        searchTagMenuModel.clear()
        var tags = searchPanel.canvasController.get_all_tags()
        for (var i = 0; i < tags.length; i++) {
            searchTagMenuModel.append({
                "tagId": tags[i].id,
                "tagName": tags[i].name,
                "tagColor": tags[i].color,
                "selected": selectedTagIndex(tags[i].id) >= 0
            })
        }
    }

    function syncTagsAndRefresh() {
        var tags = searchPanel.canvasController.get_all_tags()
        var tagsById = {}
        for (var i = 0; i < tags.length; i++) tagsById[tags[i].id] = tags[i]
        for (var j = selectedTagModel.count - 1; j >= 0; j--) {
            var selected = selectedTagModel.get(j)
            var current = tagsById[selected.tagId]
            if (!current) {
                selectedTagModel.remove(j)
            } else {
                selectedTagModel.setProperty(j, "tagName", current.name)
                selectedTagModel.setProperty(j, "tagColor", current.color)
            }
        }
        refreshSearchTags()
        invalidateSearch()
    }


    function captureTypedTags() {
        if (convertingTags) return
        var words = searchInput.text.split(/\s+/)
        var tags = searchPanel.canvasController.get_all_tags()
        var remaining = []
        convertingTags = true
        for (var i = 0; i < words.length; i++) {
            var word = words[i]
            if (word.length > 1 && word.charAt(0) === "@") {
                var wanted = word.substring(1).toLowerCase()
                var found = false
                for (var j = 0; j < tags.length; j++) {
                    if (tags[j].name.toLowerCase() === wanted) {
                        if (selectedTagIndex(tags[j].id) < 0) {
                            selectedTagModel.append({
                                "tagId": tags[j].id,
                                "tagName": tags[j].name,
                                "tagColor": tags[j].color
                            })
                        }
                        found = true
                        break
                    }
                }
                if (!found) remaining.push(word)
            } else if (word.length > 0) {
                remaining.push(word)
            }
        }
        searchInput.text = remaining.join(" ")
        if (searchInput.text.length > 0) searchInput.text += " "
        searchInput.cursorPosition = searchInput.text.length
        convertingTags = false
    }

    function selectedTagIds() {
        var ids = []
        for (var i = 0; i < selectedTagModel.count; i++) {
            ids.push(selectedTagModel.get(i).tagId)
        }
        return ids
    }

    function hasCriteria() {
        return searchInput.text.trim().length > 0 || selectedTagModel.count > 0
               || activeFilterCount() > 0
    }

    function clearResults() {
        resultModel.clear()
        currentIndex = -1
        lastQuery = ""
        statusChanged("Ready")
    }

    function invalidateSearch() {
        if (!hasCriteria()) {
            searchDebounce.stop()
            clearResults()
            return
        }
        if (open) {
            searchDebounce.restart()
        }
    }

    function openPanel() {
        open = true; focusSearchInput(); publishStatus()
    }
    function closePanel() {
        if (open) requestedCloseCompensation(width)
        searchDebounce.stop()
        open = false; statusChanged("Ready")
    }
    function focusSearchInput() {
        searchPanel.forceActiveFocus()
        Qt.callLater(function() {
            searchInput.forceActiveFocus()
            searchInput.selectAll()
        })
    }

    function searchSignature() {
        return searchInput.text.trim() + "|" + selectedTagIds().join(",") + "|"
             + minCharsInput.text + "|" + maxCharsInput.text + "|"
             + createdAfterInput.text + "|" + createdBeforeInput.text + "|" + sortKey
    }

    function searchOrNext() {
        searchDebounce.stop()
        captureTypedTags()
        if (!hasCriteria()) {
            clearResults()
            return
        }
        var signature = searchSignature()
        if (signature === lastQuery && resultModel.count > 0) {
            activateResult((currentIndex + 1) % resultModel.count)
            return
        }
        lastQuery = signature
        performSearch(searchInput.text.trim())
    }

    function performSearch(textQuery) {
        lastQuery = searchSignature()
        resultModel.clear()
        var results = searchPanel.nodeModel.search_nodes_by_filters(
            textQuery,
            selectedTagIds(),
            minCharsInput.text.length > 0 ? parseInt(minCharsInput.text) : 0,
            maxCharsInput.text.length > 0 ? parseInt(maxCharsInput.text) : 0,
            createdAfterInput.text.trim(),
            createdBeforeInput.text.trim(),
            sortKey,
            200
        )
        for (var i = 0; i < results.length; i++) resultModel.append(results[i])
        currentIndex = resultModel.count > 0 ? 0 : -1
        if (currentIndex >= 0) activateResult(currentIndex)
        else publishStatus()
    }

    function activateResult(index) {
        if (index < 0 || index >= resultModel.count) return
        currentIndex = index
        resultList.positionViewAtIndex(index, ListView.Contain)
        requestedCenter(resultModel.get(index).nodeId)
        publishStatus()
    }
    function publishStatus() {
        if (!open) return
        statusChanged(resultModel.count <= 0
                      ? "Search: 0 found"
                      : "Search: " + (currentIndex + 1) + "/" + resultModel.count)
    }
}
