pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls.Basic

Popup {
    id: picker
    required property var canvasController
    required property var appTheme
    parent: Overlay.overlay
    readonly property int popupLayer: 40
    readonly property int dragLayer: popupLayer + 1
    z: popupLayer
    width: Math.min(340, parent && parent.width > 0 ? parent.width - 16 : 340)
    height: Math.min(
        500,
        parent && parent.height > 0 ? parent.height - 16 : 500,
        contentColumn.implicitHeight + topPadding + bottomPadding
    )
    margins: 8
    padding: 12
    modal: true
    dim: false
    focus: true
    closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside

    property int nodeId: 0
    property int editingTagId: 0
    property color pendingColor: picker.appTheme.tagDefault
    property bool draggingTag: false
    property int draggingTagId: 0
    signal tagsChanged()

    onAboutToHide: cancelPreparedDrag()

    function openForNodeAt(nextNodeId, anchorItem) {
        if (visible && nodeId === nextNodeId) {
            close()
            return
        }
        nodeId = nextNodeId
        editingTagId = 0
        tagNameInput.clear()
        pendingColor = picker.appTheme.tagDefault
        refresh()

        if (!anchorItem || typeof anchorItem.mapToItem !== "function") {
            x = Math.max(8, (parent.width - width) / 2)
            y = Math.max(8, (parent.height - height) / 2)
            open()
            return
        }
        var point = anchorItem.mapToItem(parent, 0, anchorItem.height + 6)
        x = Math.max(8, Math.min(point.x, parent.width - width - 8))
        var above = anchorItem.mapToItem(parent, 0, -height - 6).y
        y = point.y + height <= parent.height - 8 ? point.y : Math.max(8, above)
        open()
    }

    function prepareDrag(sourceRow, localX, localY) {
        if (!sourceRow || !parent) return
        if (draggingTag) cancelPreparedDrag()

        dragAvatar.assigned = sourceRow.assigned
        dragAvatar.sourceIndex = sourceRow.sourceIndex
        dragAvatar.modelTagId = sourceRow.modelTagId
        dragAvatar.tagName = sourceRow.name
        dragAvatar.swatchColor = sourceRow.swatchColor
        draggingTagId = sourceRow.modelTagId

        var point = sourceRow.mapToItem(parent, localX, localY)
        var maxX = Math.max(8, parent.width - dragAvatar.width - 8)
        var maxY = Math.max(8, parent.height - dragAvatar.height - 8)
        dragAvatar.x = Math.max(8, Math.min(point.x - dragAvatar.width / 2, maxX))
        dragAvatar.y = Math.max(8, Math.min(point.y - dragAvatar.height / 2, maxY))
    }

    function beginPreparedDrag() {
        if (dragAvatar.modelTagId <= 0) return false
        draggingTag = true
        return true
    }

    function clearPreparedDrag() {
        draggingTag = false
        draggingTagId = 0
        dragAvatar.assigned = false
        dragAvatar.sourceIndex = -1
        dragAvatar.modelTagId = 0
        dragAvatar.tagName = ""
    }

    function dropPreparedDrag() {
        if (draggingTag) dragAvatar.Drag.drop()
        clearPreparedDrag()
    }

    function cancelPreparedDrag() {
        if (draggingTag) dragAvatar.Drag.cancel()
        clearPreparedDrag()
    }

    function refresh() {
        assignedModel.clear()
        availableModel.clear()
        var assigned = picker.canvasController.get_node_tags(nodeId)
        var assignedIds = {}
        for (var i = 0; i < assigned.length; i++) {
            assignedIds[assigned[i].id] = true
            assignedModel.append({
                "tagId": assigned[i].id,
                "tagName": assigned[i].name,
                "tagColor": assigned[i].color
            })
        }
        var allTags = picker.canvasController.get_all_tags()
        for (var j = 0; j < allTags.length; j++) {
            if (!assignedIds[allTags[j].id]) {
                availableModel.append({
                    "tagId": allTags[j].id,
                    "tagName": allTags[j].name,
                    "tagColor": allTags[j].color
                })
            }
        }
    }

    function editTag(tagId, tagName, tagColor) {
        editingTagId = tagId
        tagNameInput.text = tagName
        pendingColor = tagColor
        tagNameInput.forceActiveFocus()
        tagNameInput.selectAll()
    }

    function saveTag() {
        var name = tagNameInput.text.trim()
        if (name.length === 0) return
        if (editingTagId > 0) {
            if (!picker.canvasController.update_tag(editingTagId, name, pendingColor.toString())) return
        } else {
            var createdId = picker.canvasController.create_tag(name, pendingColor.toString())
            if (createdId <= 0) return
            picker.canvasController.set_node_tag(nodeId, createdId, true)
        }
        editingTagId = 0
        tagNameInput.clear()
        pendingColor = picker.appTheme.tagDefault
        refresh()
        tagsChanged()
    }

    function persistOrder() {
        var ids = []
        for (var i = 0; i < assignedModel.count; i++) ids.push(assignedModel.get(i).tagId)
        picker.canvasController.set_node_tag_order(nodeId, ids)
        tagsChanged()
    }

    function addTag(tagId) {
        addDroppedTag(tagId)
    }

    function removeTag(tagId) {
        removeDroppedTag(tagId)
    }

    function moveAssignedTag(sourceIndex, offset) {
        var targetIndex = sourceIndex + offset
        if (sourceIndex < 0 || sourceIndex >= assignedModel.count
                || targetIndex < 0 || targetIndex >= assignedModel.count) return
        assignedModel.move(sourceIndex, targetIndex, 1)
        persistOrder()
    }

    function addDroppedTag(tagId) {
        picker.canvasController.set_node_tag(nodeId, tagId, true)
        refresh()
        tagsChanged()
    }

    function removeDroppedTag(tagId) {
        picker.canvasController.set_node_tag(nodeId, tagId, false)
        refresh()
        tagsChanged()
    }

    enter: Transition {
        ParallelAnimation {
            NumberAnimation { property: "opacity"; from: 0; to: 1; duration: 150; easing.type: Easing.OutCubic }
            NumberAnimation { property: "scale"; from: 0.98; to: 1; duration: 150; easing.type: Easing.OutCubic }
        }
    }
    exit: Transition {
        NumberAnimation { property: "opacity"; from: 1; to: 0; duration: 100; easing.type: Easing.OutCubic }
    }

    background: Rectangle {
        color: picker.appTheme.bgPopover
        radius: 10
        border.width: 1
        border.color: picker.appTheme.borderDefault
    }

    TagDragAvatar {
        id: dragAvatar
        parent: picker.visible ? picker.parent : null
        z: picker.dragLayer
        visible: picker.visible && picker.draggingTag
        width: Math.max(64, Math.min(
            220,
            dragLabel.implicitWidth + 56,
            parent && parent.width > 0 ? parent.width - 16 : 220
        ))
        height: 32
        radius: 6
        color: picker.appTheme.bgNode
        border.width: 1
        border.color: picker.appTheme.accentMain
        opacity: 0.98

        Drag.active: picker.draggingTag
        Drag.source: dragAvatar
        Drag.keys: ["application/x-kryptonote-tag"]
        Drag.supportedActions: Qt.MoveAction
        Drag.hotSpot.x: width / 2
        Drag.hotSpot.y: height / 2

        Rectangle {
            width: 10
            height: 10
            radius: 5
            anchors.left: parent.left
            anchors.leftMargin: 9
            anchors.verticalCenter: parent.verticalCenter
            color: dragAvatar.swatchColor
        }

        Text {
            id: dragLabel
            anchors.left: parent.left
            anchors.leftMargin: 26
            anchors.right: dragGrip.left
            anchors.rightMargin: 6
            anchors.verticalCenter: parent.verticalCenter
            text: "@" + dragAvatar.tagName
            color: picker.appTheme.textMain
            elide: Text.ElideRight
            font.family: "Segoe UI"
            font.pointSize: 9
        }

        ToolButton {
            id: dragGrip
            anchors.right: parent.right
            anchors.rightMargin: 5
            anchors.verticalCenter: parent.verticalCenter
            width: 24
            height: 24
            hoverEnabled: false
            focusPolicy: Qt.NoFocus
            display: AbstractButton.IconOnly
            icon.source: "../assets/icons/grip.svg"
            icon.width: 15
            icon.height: 15
            icon.color: picker.appTheme.textDim
            background: Item {}
            Accessible.ignored: true
        }
    }

    contentItem: Column {
        id: contentColumn
        spacing: 8

        Item {
            width: parent.width
            height: 28

            Text {
                anchors.left: parent.left
                anchors.verticalCenter: parent.verticalCenter
                text: "Tags"
                color: picker.appTheme.textMain
                verticalAlignment: Text.AlignVCenter
                font.family: "Segoe UI Semibold"
                font.pointSize: 10
            }

            ToolButton {
                id: closePickerButton
                anchors.right: parent.right
                anchors.verticalCenter: parent.verticalCenter
                width: 28
                height: 28
                hoverEnabled: true
                focusPolicy: Qt.TabFocus
                display: AbstractButton.IconOnly
                icon.source: "../assets/icons/close.svg"
                icon.width: 14
                icon.height: 14
                icon.color: hovered || visualFocus
                            ? picker.appTheme.btnCancelText : picker.appTheme.textDim
                background: Rectangle {
                    radius: 6
                    color: closePickerButton.down ? picker.appTheme.whiteAlpha15
                         : closePickerButton.hovered ? picker.appTheme.whiteAlpha10
                         : "transparent"
                    border.width: closePickerButton.visualFocus ? 1 : 0
                    border.color: picker.appTheme.accentMain
                }
                Accessible.name: "Close tags"
                ToolTip.visible: hovered
                ToolTip.text: Accessible.name
                ToolTip.delay: 500
                onClicked: picker.close()
            }
        }

        SectionLabel {
            text: picker.draggingTag ? "Drop to assign or reorder" : "On this node"
        }

        Rectangle {
            id: assignedZone
            width: parent.width
            height: Math.max(34, Math.min(140, assignedList.contentHeight))
            radius: 6
            color: assignedDrop.containsDrag ? picker.appTheme.accentLow : "transparent"
            border.width: assignedDrop.containsDrag ? 1 : 0
            border.color: picker.appTheme.accentMain

            Text {
                anchors.fill: parent
                anchors.leftMargin: 8
                visible: assignedModel.count === 0
                text: picker.draggingTag ? "Drop tag here" : "No tags assigned"
                color: picker.appTheme.textDim
                verticalAlignment: Text.AlignVCenter
                font.family: "Segoe UI"
                font.pointSize: 9
            }

            ListView {
                id: assignedList
                anchors.fill: parent
                visible: assignedModel.count > 0
                model: ListModel { id: assignedModel }
                spacing: 3
                clip: true
                boundsBehavior: Flickable.StopAtBounds
                interactive: contentHeight > height && !picker.draggingTag

                delegate: DraggableTagRow {
                    required property int index
                    required property int tagId
                    required property string tagName
                    required property string tagColor
                    width: assignedList.width
                    assigned: true
                    sourceIndex: index
                    modelTagId: tagId
                    name: tagName
                    swatchColor: tagColor
                    canMoveUp: index > 0
                    canMoveDown: index < assignedModel.count - 1
                    onAssignmentToggleRequested: picker.removeTag(tagId)
                    onMoveRequested: function(offset) {
                        picker.moveAssignedTag(index, offset)
                    }
                    onEditRequested: picker.editTag(tagId, tagName, tagColor)
                }
            }

            DropArea {
                id: assignedDrop
                anchors.fill: parent
                keys: ["application/x-kryptonote-tag"]
                onDropped: function(drop) {
                    var sourceRow = drop.source as TagDragAvatar
                    if (!sourceRow) return
                    var wasAssigned = sourceRow.assigned
                    var tagId = sourceRow.modelTagId
                    var sourceIndex = sourceRow.sourceIndex
                    var targetIndex = Math.max(0, Math.min(
                        assignedModel.count - 1,
                        Math.floor(drop.y / 37)
                    ))
                    drop.acceptProposedAction()
                    Qt.callLater(function() {
                        if (!wasAssigned) {
                            picker.addDroppedTag(tagId)
                        } else if (assignedModel.count > 1 && sourceIndex !== targetIndex) {
                            assignedModel.move(sourceIndex, targetIndex, 1)
                            picker.persistOrder()
                        }
                    })
                }
            }
        }

        Rectangle { width: parent.width; height: 1; color: picker.appTheme.borderDefault }

        SectionLabel {
            text: picker.draggingTag ? "Drop to remove from node" : "Available tags"
        }

        Rectangle {
            id: availableZone
            width: parent.width
            height: Math.max(34, Math.min(120, availableList.contentHeight))
            radius: 6
            color: availableDrop.containsDrag ? picker.appTheme.whiteAlpha05 : "transparent"
            border.width: availableDrop.containsDrag ? 1 : 0
            border.color: picker.appTheme.borderHover

            Text {
                anchors.fill: parent
                anchors.leftMargin: 8
                visible: availableModel.count === 0
                text: picker.draggingTag ? "Drop here to remove" : "All tags are already assigned"
                color: picker.appTheme.textDim
                verticalAlignment: Text.AlignVCenter
                font.family: "Segoe UI"
                font.pointSize: 9
            }

            ListView {
                id: availableList
                anchors.fill: parent
                visible: availableModel.count > 0
                model: ListModel { id: availableModel }
                spacing: 3
                clip: true
                boundsBehavior: Flickable.StopAtBounds
                interactive: contentHeight > height && !picker.draggingTag

                delegate: DraggableTagRow {
                    required property int index
                    required property int tagId
                    required property string tagName
                    required property string tagColor
                    width: availableList.width
                    assigned: false
                    sourceIndex: index
                    modelTagId: tagId
                    name: tagName
                    swatchColor: tagColor
                    onAssignmentToggleRequested: picker.addTag(tagId)
                    onEditRequested: picker.editTag(tagId, tagName, tagColor)
                }
            }

            DropArea {
                id: availableDrop
                anchors.fill: parent
                keys: ["application/x-kryptonote-tag"]
                onDropped: function(drop) {
                    var sourceRow = drop.source as TagDragAvatar
                    if (!sourceRow || !sourceRow.assigned) return
                    var tagId = sourceRow.modelTagId
                    drop.acceptProposedAction()
                    Qt.callLater(function() { picker.removeDroppedTag(tagId) })
                }
            }
        }

        Text {
            width: parent.width
            height: 16
            text: "Hover a tag for actions · drag to assign or reorder"
            color: picker.appTheme.textDim
            elide: Text.ElideRight
            font.family: "Segoe UI"
            font.pointSize: 7
        }

        Rectangle { width: parent.width; height: 1; color: picker.appTheme.borderDefault }

        Row {
            width: parent.width
            height: 32
            spacing: 6

            ToolButton {
                id: tagColorButton
                objectName: "tagColorButton"
                width: 32
                height: 32
                hoverEnabled: true
                focusPolicy: Qt.TabFocus
                background: Rectangle {
                    radius: 6
                    color: picker.pendingColor
                    border.width: tagColorButton.visualFocus ? 2 : 1
                    border.color: tagColorButton.visualFocus
                                  ? picker.appTheme.accentMain : picker.appTheme.borderHover
                }
                Accessible.name: "Choose tag color"
                ToolTip.visible: hovered
                ToolTip.text: Accessible.name
                ToolTip.delay: 500
                onClicked: colorPopup.openForColor(picker.pendingColor)
            }

            Rectangle {
                width: parent.width - 82
                height: 32
                radius: 6
                color: picker.appTheme.bgInput
                border.width: tagNameInput.activeFocus ? 1 : 0
                border.color: picker.appTheme.accentMain
                TextField {
                    id: tagNameInput
                    anchors.fill: parent
                    anchors.leftMargin: 9
                    anchors.rightMargin: 9
                    placeholderText: picker.editingTagId > 0 ? "Rename tag" : "New tag"
                    color: picker.appTheme.textMain
                    placeholderTextColor: picker.appTheme.textDim
                    font.family: "Segoe UI"
                    font.pointSize: 9
                    background: Item {}
                    ContextMenu.menu: null
                    onAccepted: picker.saveTag()
                }
            }

            ToolButton {
                id: saveTagButton
                width: 38
                height: 32
                enabled: tagNameInput.text.trim().length > 0
                opacity: enabled ? 1 : 0.45
                hoverEnabled: true
                focusPolicy: Qt.TabFocus
                display: AbstractButton.IconOnly
                icon.source: picker.editingTagId > 0
                             ? "../assets/icons/check.svg" : "../assets/icons/add.svg"
                icon.width: 15
                icon.height: 15
                icon.color: picker.appTheme.textMain
                background: Rectangle {
                    radius: 6
                    color: saveTagButton.down ? picker.appTheme.accentHover
                         : saveTagButton.hovered ? picker.appTheme.accentHover
                         : picker.appTheme.accentMain
                    border.width: saveTagButton.visualFocus ? 1.5 : 0
                    border.color: picker.appTheme.textMain
                }
                Accessible.name: picker.editingTagId > 0 ? "Save tag" : "Create tag"
                ToolTip.visible: hovered
                ToolTip.text: Accessible.name
                ToolTip.delay: 500
                onClicked: picker.saveTag()
            }
        }
    }

    component TagDragAvatar: Rectangle {
        property bool assigned: false
        property int sourceIndex: -1
        property int modelTagId: 0
        property string tagName: ""
        property color swatchColor: picker.appTheme.tagDefault
    }

    component SectionLabel: Text {
        width: parent ? parent.width : 0
        height: 18
        color: picker.appTheme.textDim
        font.family: "Segoe UI Semibold"
        font.pointSize: 8
        verticalAlignment: Text.AlignVCenter
    }

    component DraggableTagRow: Item {
        id: tagRow
        property string name: ""
        property color swatchColor: picker.appTheme.tagDefault
        property bool assigned: false
        property int sourceIndex: -1
        property int modelTagId: 0
        property bool dragStarted: false
        property bool canMoveUp: false
        property bool canMoveDown: false
        readonly property bool actionsFocused: assignmentButton.activeFocus
                                               || editButton.activeFocus
                                               || moveUpButton.activeFocus
                                               || moveDownButton.activeFocus
        readonly property bool actionsShown: (rowHover.hovered || actionsFocused)
                                             && !picker.draggingTag
        signal assignmentToggleRequested()
        signal moveRequested(int offset)
        signal editRequested()
        height: 34
        opacity: picker.draggingTag && picker.draggingTagId === modelTagId ? 0.22 : 1

        Behavior on opacity {
            NumberAnimation { duration: 80; easing.type: Easing.OutCubic }
        }

        Rectangle {
            id: dragSurface
            anchors.fill: parent
            radius: 6
            color: tagRow.actionsShown ? picker.appTheme.bgNode : "transparent"

            Rectangle {
                width: 10
                height: 10
                radius: 5
                anchors.left: parent.left
                anchors.leftMargin: 8
                anchors.verticalCenter: parent.verticalCenter
                color: tagRow.swatchColor
            }

            Text {
                anchors.left: parent.left
                anchors.leftMargin: 26
                anchors.right: grip.left
                anchors.rightMargin: 6
                anchors.verticalCenter: parent.verticalCenter
                text: "@" + tagRow.name
                color: picker.appTheme.textMain
                elide: Text.ElideRight
                font.family: "Segoe UI"
                font.pointSize: 9
            }

            ToolButton {
                id: grip
                anchors.right: parent.right
                anchors.rightMargin: 5
                anchors.verticalCenter: parent.verticalCenter
                width: 24
                height: 24
                hoverEnabled: false
                focusPolicy: Qt.NoFocus
                display: AbstractButton.IconOnly
                icon.source: "../assets/icons/grip.svg"
                icon.width: 15
                icon.height: 15
                icon.color: picker.appTheme.textDim
                background: Item {}
                Accessible.ignored: true
            }

            Rectangle {
                id: actionRail
                z: 2
                anchors.right: parent.right
                anchors.rightMargin: 3
                anchors.verticalCenter: parent.verticalCenter
                width: actionButtons.implicitWidth + 4
                height: 28
                radius: 6
                color: picker.appTheme.bgNode
                opacity: tagRow.actionsShown ? 1 : 0
                enabled: !picker.draggingTag

                Row {
                    id: actionButtons
                    anchors.centerIn: parent
                    spacing: 2

                    TagActionButton {
                        id: assignmentButton
                        objectName: tagRow.assigned ? "removeTagButton" : "addTagButton"
                        iconSource: tagRow.assigned
                                    ? "../assets/icons/remove.svg"
                                    : "../assets/icons/add.svg"
                        toolTip: tagRow.assigned
                                 ? "Remove @" + tagRow.name + " from node"
                                 : "Add @" + tagRow.name + " to node"
                        onClicked: tagRow.assignmentToggleRequested()
                    }

                    TagActionButton {
                        id: editButton
                        objectName: "editTagButton"
                        iconSource: "../assets/icons/edit.svg"
                        toolTip: "Edit @" + tagRow.name
                        onClicked: tagRow.editRequested()
                    }

                    TagActionButton {
                        id: moveUpButton
                        objectName: "moveTagUpButton"
                        visible: tagRow.assigned
                        enabled: tagRow.canMoveUp
                        iconSource: "../assets/icons/move-up.svg"
                        toolTip: "Move @" + tagRow.name + " up"
                        onClicked: tagRow.moveRequested(-1)
                    }

                    TagActionButton {
                        id: moveDownButton
                        objectName: "moveTagDownButton"
                        visible: tagRow.assigned
                        enabled: tagRow.canMoveDown
                        iconSource: "../assets/icons/move-down.svg"
                        toolTip: "Move @" + tagRow.name + " down"
                        onClicked: tagRow.moveRequested(1)
                    }
                }
            }

            MouseArea {
                id: dragMouse
                anchors.fill: parent
                hoverEnabled: true
                preventStealing: true
                cursorShape: drag.active ? Qt.ClosedHandCursor : Qt.OpenHandCursor
                drag.target: dragAvatar
                drag.axis: Drag.XAndYAxis
                drag.smoothed: false
                drag.minimumX: 8
                drag.maximumX: picker.parent
                    ? Math.max(8, picker.parent.width - dragAvatar.width - 8)
                    : 8
                drag.minimumY: 8
                drag.maximumY: picker.parent
                    ? Math.max(8, picker.parent.height - dragAvatar.height - 8)
                    : 8

                onPressed: function(mouse) {
                    picker.prepareDrag(tagRow, mouse.x, mouse.y)
                }
                onPositionChanged: {
                    if (drag.active && !tagRow.dragStarted) {
                        tagRow.dragStarted = picker.beginPreparedDrag()
                    }
                }
                onReleased: {
                    var shouldDrop = tagRow.dragStarted
                    tagRow.dragStarted = false
                    if (shouldDrop) picker.dropPreparedDrag()
                    else picker.cancelPreparedDrag()
                }
                onCanceled: {
                    tagRow.dragStarted = false
                    picker.cancelPreparedDrag()
                }
                onDoubleClicked: tagRow.editRequested()
            }

            HoverHandler {
                id: rowHover
                acceptedDevices: PointerDevice.Mouse | PointerDevice.TouchPad
            }
        }
    }

    component TagActionButton: ToolButton {
        id: actionButton
        required property url iconSource
        required property string toolTip
        width: 24
        height: 24
        hoverEnabled: true
        focusPolicy: Qt.TabFocus
        display: AbstractButton.IconOnly
        opacity: enabled ? 1 : 0.35
        icon.source: iconSource
        icon.width: 14
        icon.height: 14
        icon.color: enabled && (hovered || visualFocus)
                    ? picker.appTheme.textMain : picker.appTheme.textDim
        background: Rectangle {
            radius: 5
            color: actionButton.down ? picker.appTheme.whiteAlpha15
                 : actionButton.hovered ? picker.appTheme.whiteAlpha10
                 : actionButton.visualFocus ? picker.appTheme.whiteAlpha05
                 : "transparent"
            border.width: actionButton.visualFocus ? 1 : 0
            border.color: picker.appTheme.accentMain
        }
        Accessible.name: toolTip
        ToolTip.visible: hovered && toolTip.length > 0
        ToolTip.text: toolTip
        ToolTip.delay: 500
    }

    TagColorPopup {
        appTheme: picker.appTheme
        id: colorPopup
        onColorAccepted: function(selectedColor) {
            picker.pendingColor = selectedColor
        }
    }
}