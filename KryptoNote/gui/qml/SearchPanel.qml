import QtQuick
import QtQuick.Controls.Basic

Item {
    id: searchPanel

    property bool open: false
    property bool panelVisible: false
    focus: open
    property bool resizing: resizeMouse.pressed
    property real preferredWidth: parent ? parent.width * 0.20 : 260
    property real minPanelWidth: parent ? Math.max(220, parent.width * 0.10) : 220
    property real maxPanelWidth: parent ? parent.width * 0.40 : 520
    property real slideOffset: open ? 0 : -width
    property int currentIndex: -1
    property string lastQuery: ""

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
            hideTimer.restart()
        }
    }

    onMaxPanelWidthChanged: {
        if (preferredWidth > maxPanelWidth) {
            preferredWidth = maxPanelWidth
        }
    }

    Shortcut {
        sequence: "Esc"
        context: Qt.ApplicationShortcut
        enabled: searchPanel.open
        onActivated: searchPanel.closePanel()
    }

    Rectangle {
        anchors.fill: parent
        color: "#1e1e1e"
    }

    Rectangle {
        width: 1
        anchors.right: parent.right
        anchors.top: parent.top
        anchors.bottom: parent.bottom
        color: "#303030"
    }

    MouseArea {
        id: inputBlocker
        anchors.fill: parent
        z: 0
        acceptedButtons: Qt.LeftButton | Qt.RightButton | Qt.MiddleButton
        hoverEnabled: true
        preventStealing: true
        propagateComposedEvents: false
        onPressed: function(mouse) { mouse.accepted = true }
        onReleased: function(mouse) { mouse.accepted = true }
        onClicked: function(mouse) { mouse.accepted = true }
        onWheel: function(wheel) { wheel.accepted = true }
    }

    Rectangle {
        id: resizeGrip
        width: 7
        anchors.right: parent.right
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
                pressSceneX = resizeMouse.mapToItem(searchPanel.parent, mouse.x, mouse.y).x
                startPreferredWidth = searchPanel.preferredWidth
            }

            onPositionChanged: function(mouse) {
                mouse.accepted = true
                if (!pressed) {
                    return
                }
                var sceneX = resizeMouse.mapToItem(searchPanel.parent, mouse.x, mouse.y).x
                var nextWidth = startPreferredWidth + (sceneX - pressSceneX)
                searchPanel.preferredWidth = Math.max(searchPanel.minPanelWidth, Math.min(searchPanel.maxPanelWidth, nextWidth))
            }

            onReleased: function(mouse) {
                mouse.accepted = true
            }
        }
    }

    Item {
        z: 1
        anchors.fill: parent

        Rectangle {
            id: searchField
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.top: parent.top
            anchors.leftMargin: 14
            anchors.rightMargin: 14
            anchors.topMargin: 14
            height: 34
            radius: 7
            color: "#26282b"

            TextField {
                id: searchInput
                anchors.left: parent.left
                anchors.right: searchButton.left
                anchors.top: parent.top
                anchors.bottom: parent.bottom
                anchors.leftMargin: 12
                anchors.rightMargin: 6
                text: ""
                placeholderText: "Search"
                selectByMouse: true
                color: "#f4f4f4"
                placeholderTextColor: "#73777d"
                font.family: "Segoe UI Semibold"
                font.pointSize: 12
                background: Item {}
                Keys.onPressed: function(event) {
                    if (event.key === Qt.Key_Return || event.key === Qt.Key_Enter) {
                        searchPanel.searchOrNext()
                        event.accepted = true
                    }
                }
            }

            Rectangle {
                id: searchButton
                width: 54
                height: parent.height - 8
                anchors.right: closeButton.left
                anchors.rightMargin: 4
                anchors.verticalCenter: parent.verticalCenter
                radius: 6
                scale: searchMouse.pressed ? 0.96 : 1.0
                color: searchMouse.pressed
                       ? "#40464d"
                       : (searchMouse.containsMouse ? "#3a4047" : "#2b2f34")

                Behavior on color { ColorAnimation { duration: 110 } }
                Behavior on scale { NumberAnimation { duration: 80 } }

                Text {
                    anchors.centerIn: parent
                    text: "Find"
                    color: "#f4f4f4"
                    font.family: "Segoe UI Semibold"
                    font.pointSize: 9
                }

                MouseArea {
                    id: searchMouse
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: searchPanel.searchOrNext()
                }
            }

            Rectangle {
                id: closeButton
                width: 28
                height: parent.height - 8
                anchors.right: parent.right
                anchors.rightMargin: 4
                anchors.verticalCenter: parent.verticalCenter
                radius: 6
                scale: closeMouse.pressed ? 0.94 : 1.0
                color: closeMouse.pressed
                       ? "#5a2024"
                       : (closeMouse.containsMouse ? "#512024" : "#2b2f34")

                Behavior on color { ColorAnimation { duration: 110 } }
                Behavior on scale { NumberAnimation { duration: 80 } }

                Text {
                    visible: false
                }

                Canvas {
                    anchors.centerIn: parent
                    width: 12
                    height: 12
                    onPaint: {
                        var ctx = getContext("2d")
                        ctx.reset()
                        ctx.strokeStyle = "#ffffff"
                        ctx.lineWidth = 1.8
                        ctx.lineCap = "round"
                        ctx.beginPath()
                        ctx.moveTo(2.5, 2.5)
                        ctx.lineTo(9.5, 9.5)
                        ctx.moveTo(9.5, 2.5)
                        ctx.lineTo(2.5, 9.5)
                        ctx.stroke()
                    }
                }

                MouseArea {
                    id: closeMouse
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: searchPanel.closePanel()
                }
            }
        }

        Item {
            id: resultFrame
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.top: searchDivider.bottom
            anchors.bottom: parent.bottom
            anchors.leftMargin: 14
            anchors.rightMargin: 14
            anchors.topMargin: 0
            clip: true

            ListView {
                id: resultList
                anchors.fill: parent
                anchors.topMargin: 0
                anchors.bottomMargin: 0
                clip: true
                spacing: 10
                model: resultModel
                boundsBehavior: Flickable.StopAtBounds
                cacheBuffer: Math.max(0, height * 2)
                currentIndex: searchPanel.currentIndex

                ScrollBar.vertical: ScrollBar {
                    policy: resultList.contentHeight > resultList.height
                            ? ScrollBar.AsNeeded : ScrollBar.AlwaysOff
                    contentItem: Rectangle {
                        implicitWidth: 4
                        radius: 2
                        color: "#5a5a5a"
                    }
                    background: Rectangle { color: "transparent" }
                }

                delegate: Rectangle {
                    id: resultCard
                    required property int index
                    required property int nodeId
                    required property string title
                    required property string content
                    required property string meta

                    width: resultList.width - 2
                    height: Math.min(224, Math.max(82, contentColumn.implicitHeight + 22))
                    radius: 7
                    clip: true
                    color: "#26282b"
                    border.width: index === searchPanel.currentIndex ? 1.5 : 1.1
                    border.color: index === searchPanel.currentIndex ? "#e6158b" : "#3a3a3a"

                    Column {
                        id: contentColumn
                        x: 12
                        y: 9
                        width: parent.width - 24
                        height: parent.height - 18
                        clip: true
                        spacing: 5

                        Text {
                            id: titleText
                            width: parent.width
                            text: resultCard.title.length > 0 ? resultCard.title : "(untitled)"
                            color: "#e6158b"
                            font.family: "Segoe UI Semibold"
                            font.pointSize: 11
                            elide: Text.ElideRight
                            maximumLineCount: 1
                        }

                        Text {
                            id: bodyText
                            width: parent.width
                            text: resultCard.content
                            color: "#efefef"
                            font.family: "Segoe UI"
                            font.pointSize: 9
                            textFormat: Text.MarkdownText
                            wrapMode: Text.WordWrap
                            elide: Text.ElideRight
                            maximumLineCount: 7
                            clip: true
                        }

                        Text {
                            id: metaText
                            width: parent.width
                            text: resultCard.meta
                            color: "#8d949e"
                            font.family: "Segoe UI"
                            font.pointSize: 8
                            elide: Text.ElideRight
                            maximumLineCount: 1
                            visible: text.length > 0
                        }
                    }

                    MouseArea {
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: searchPanel.activateResult(resultCard.index)
                    }
                }
            }
        }

        Rectangle {
            id: searchDivider
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.top: searchField.bottom
            anchors.topMargin: 14
            height: 1
            color: "#34383d"
        }
    }

    ListModel {
        id: resultModel
    }

    Timer {
        id: hideTimer
        interval: 230
        repeat: false
        onTriggered: {
            if (!searchPanel.open) {
                searchPanel.panelVisible = false
            }
        }
    }

    Behavior on slideOffset { NumberAnimation { duration: 220; easing.type: Easing.OutCubic } }

    function openPanel() {
        open = true
        focusSearchInput()
        publishStatus()
    }

    function closePanel() {
        if (open) {
            requestedCloseCompensation(width)
        }
        open = false
        statusChanged("Ready")
    }

    function focusSearchInput() {
        searchPanel.forceActiveFocus()
        Qt.callLater(function() {
            searchInput.forceActiveFocus()
            searchInput.selectAll()
        })
    }

    function searchOrNext() {
        var query = searchInput.text.trim()
        if (query.length === 0) {
            return
        }
        if (query === lastQuery && resultModel.count > 0) {
            activateResult((currentIndex + 1) % resultModel.count)
            return
        }
        lastQuery = query
        performSearch(query)
    }

    function performSearch(query) {
        resultModel.clear()
        var results = nodeModel.search_nodes(query)
        for (var i = 0; i < results.length; i++) {
            resultModel.append(results[i])
        }
        currentIndex = resultModel.count > 0 ? 0 : -1
        if (currentIndex >= 0) {
            activateResult(currentIndex)
        } else {
            publishStatus()
        }
    }

    function activateResult(index) {
        if (index < 0 || index >= resultModel.count) {
            return
        }
        currentIndex = index
        resultList.positionViewAtIndex(index, ListView.Contain)
        var item = resultModel.get(index)
        requestedCenter(item.nodeId)
        publishStatus()
    }

    function publishStatus() {
        if (!open) {
            return
        }
        if (resultModel.count <= 0) {
            statusChanged("Search: 0 found")
            return
        }
        statusChanged("Search: " + (currentIndex + 1) + "/" + resultModel.count)
    }
}
