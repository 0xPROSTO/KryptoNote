pragma ComponentBehavior: Bound

import QtQuick
import QtQuick as Quick
import QtQuick.Controls
import QtQuick.Shapes


Popup {
    id: propertiesPopup
    required property var appTheme
    required property var nodeModel
    required property Item contentLayer
    required property real contentScale

    parent: Overlay.overlay
    width: parent ? parent.width : 0
    height: parent ? parent.height : 0
    padding: 0
    modal: true
    dim: false
    focus: true
    closePolicy: Popup.CloseOnEscape

    property int nodeId: 0
    property var metadataLines: []
    property var nodeBounds: []
    readonly property string nodeType: metadataValue("Type")
    readonly property string nodeTypeLabel: {
        switch (nodeType) {
        case "text":
            return "Text node"
        case "image":
            return "Image node"
        case "video":
            return "Video node"
        case "audio":
            return "Audio node"
        case "frame":
            return "Frame"
        default:
            return "Node"
        }
    }
    readonly property string nodeIdLabel: {
        var nodeNumber = metadataValue("ID")
        return nodeNumber ? "#" + nodeNumber : "#—"
    }
    readonly property string nodeTitleLine: {
        var title = metadataValue("Title")
        return title && title !== "(untitled)" ? title : "Untitled"
    }
    readonly property var displayRows: buildDisplayRows()
    readonly property rect sourceRect: {
        // Explicit transform reads keep the mapping reactive while the canvas
        // is moving or zooming.
        var transformRevision = propertiesPopup.contentLayer.x
                + propertiesPopup.contentLayer.y
                + propertiesPopup.contentLayer.scale
                + propertiesPopup.contentScale
        if (transformRevision < -Number.MAX_VALUE
                || propertiesPopup.nodeBounds.length < 4) {
            return Qt.rect(0, 0, 0, 0)
        }
        return propertiesPopup.contentLayer.mapToItem(
            overlayBody,
            propertiesPopup.nodeBounds[0],
            propertiesPopup.nodeBounds[1],
            propertiesPopup.nodeBounds[2],
            propertiesPopup.nodeBounds[3]
        )
    }
    onSourceRectChanged: {
        dimmer.requestPaint()
        if (visible) {
            Qt.callLater(overlayBody.updateCardPosition)
        }
    }

    function metadataValue(key) {
        var prefix = key + ":"
        for (var index = 0; index < metadataLines.length; ++index) {
            var line = String(metadataLines[index])
            if (line.indexOf(prefix) === 0) {
                return line.slice(prefix.length).trim()
            }
        }
        return ""
    }

    function buildDisplayRows() {
        var rows = []
        var created = metadataValue("Created")
        var updated = metadataValue("Updated")
        var position = metadataValue("Position")
        var size = metadataValue("Node size")
        var geometry = []

        if (created && created !== "-") {
            rows.push({"label": "Created", "value": created})
        }
        if (updated && updated !== "-" && updated !== created) {
            rows.push({"label": "Updated", "value": updated})
        }
        if (position) {
            geometry.push(position)
        }
        if (size) {
            geometry.push(size)
        }
        if (geometry.length > 0) {
            rows.push({
                "label": "Geometry",
                "value": geometry.join("  ·  ")
            })
        }

        var fileSize = metadataValue("File size")
        var originalFile = metadataValue("Original file")
        var resolution = metadataValue("Resolution")
        var duration = metadataValue("Duration")
        var tags = metadataValue("Tags")
        var characters = metadataValue("Characters")
        var words = metadataValue("Words")
        var lineCount = metadataValue("Lines")
        var typography = metadataValue("Typography")
        if (fileSize) {
            rows.push({"label": "File size", "value": fileSize})
        }
        if (originalFile) {
            rows.push({"label": "Original file", "value": originalFile})
        }
        if (resolution) {
            rows.push({"label": "Resolution", "value": resolution})
        }
        if (duration) {
            rows.push({"label": "Duration", "value": duration})
        }
        if (tags) {
            rows.push({"label": "Tags", "value": tags})
        }
        var contentDetails = []
        if (characters) {
            contentDetails.push(
                characters
                    + (characters === "1" ? " character" : " characters")
            )
        }
        if (words) {
            contentDetails.push(words + (words === "1" ? " word" : " words"))
        }
        if (lineCount) {
            contentDetails.push(
                lineCount + (lineCount === "1" ? " line" : " lines")
            )
        }
        if (contentDetails.length > 0) {
            rows.push({
                "label": "Content",
                "value": contentDetails.join("  ·  ")
            })
        }
        if (typography) {
            rows.push({"label": "Typography", "value": typography})
        }

        var lockState = metadataValue("Lock")
        var background = metadataValue("Background")
        var opacity = metadataValue("Opacity")
        if (lockState) {
            rows.push({"label": "State", "value": lockState})
        }
        if (background || opacity) {
            var appearance = []
            if (background) {
                appearance.push(background)
            }
            if (opacity) {
                appearance.push(opacity)
            }
            rows.push({
                "label": "Appearance",
                "value": appearance.join("  ·  ")
            })
        }
        var consumed = {
            "ID": true,
            "Type": true,
            "Title": true,
            "Created": true,
            "Updated": true,
            "Position": true,
            "Node size": true,
            "File size": true,
            "Original file": true,
            "Resolution": true,
            "Duration": true,
            "Tags": true,
            "Characters": true,
            "Words": true,
            "Lines": true,
            "Typography": true,
            "Lock": true,
            "Background": true,
            "Opacity": true
        }
        for (var index = 0; index < metadataLines.length; ++index) {
            var line = String(metadataLines[index])
            var separator = line.indexOf(":")
            if (separator <= 0) continue
            var label = line.slice(0, separator).trim()
            var value = line.slice(separator + 1).trim()
            if (!consumed[label] && value) {
                rows.push({"label": label, "value": value})
            }
        }
        return rows
    }

    function openForNode(targetNodeId) {
        var lines = propertiesPopup.nodeModel.get_node_metadata_lines(
            targetNodeId
        )
        var bounds = propertiesPopup.nodeModel.get_node_bounds(targetNodeId)
        if (!lines || lines.length === 0 || !bounds || bounds.length < 4) {
            return
        }
        propertiesPopup.nodeId = targetNodeId
        propertiesPopup.metadataLines = lines
        propertiesPopup.nodeBounds = bounds
        propertiesCard.userPositioned = false
        propertiesPopup.open()
    }

    function closeOverlay() {
        propertiesPopup.close()
    }

    onOpened: Qt.callLater(function() {
        propertiesCard.x = overlayBody.cardX()
        propertiesCard.y = overlayBody.cardY()
        dimmer.requestPaint()
        closeButton.forceActiveFocus()
    })

    background: Item {}

    contentItem: Item {
        id: overlayBody

        function cardX() {
            var margin = 18
            var gap = 48
            var sourceLeft = propertiesPopup.sourceRect.x
            var sourceRight = sourceLeft + propertiesPopup.sourceRect.width
            var rightCandidate = sourceRight + gap
            var leftCandidate = sourceLeft - propertiesCard.width - gap

            if (rightCandidate + propertiesCard.width <= width - margin) {
                return rightCandidate
            }
            if (leftCandidate >= margin) {
                return leftCandidate
            }
            return Math.max(
                margin,
                Math.min(
                    sourceLeft
                        + propertiesPopup.sourceRect.width / 2
                        - propertiesCard.width / 2,
                    width - propertiesCard.width - margin
                )
            )
        }

        function cardY() {
            var margin = 18
            var sourceTop = propertiesPopup.sourceRect.y
            var sourceBottom = sourceTop + propertiesPopup.sourceRect.height
            var centered = sourceTop
                    + propertiesPopup.sourceRect.height / 2
                    - propertiesCard.height / 2

            if (centered >= margin
                    && centered + propertiesCard.height <= height - margin) {
                return centered
            }
            if (sourceBottom + 32 + propertiesCard.height <= height - margin) {
                return sourceBottom + 32
            }
            if (sourceTop - 32 - propertiesCard.height >= margin) {
                return sourceTop - 32 - propertiesCard.height
            }
            return Math.max(
                margin,
                Math.min(centered, height - propertiesCard.height - margin)
            )
        }

        function clampCardPosition() {
            if (!propertiesPopup.visible) {
                return
            }
            propertiesCard.x = Math.max(
                propertiesCard.edgeMargin,
                Math.min(
                    propertiesCard.x,
                    Math.max(
                        propertiesCard.edgeMargin,
                        width - propertiesCard.width
                            - propertiesCard.edgeMargin
                    )
                )
            )
            propertiesCard.y = Math.max(
                propertiesCard.edgeMargin,
                Math.min(
                    propertiesCard.y,
                    Math.max(
                        propertiesCard.edgeMargin,
                        height - propertiesCard.height
                            - propertiesCard.edgeMargin
                    )
                )
            )
        }

        function updateCardPosition() {
            if (!propertiesPopup.visible) {
                return
            }
            if (propertiesCard.userPositioned) {
                clampCardPosition()
                return
            }
            propertiesCard.x = cardX()
            propertiesCard.y = cardY()
        }

        onWidthChanged: Qt.callLater(updateCardPosition)
        onHeightChanged: Qt.callLater(updateCardPosition)

        function edgePoint(rect, targetX, targetY) {
            var centerX = rect.x + rect.width / 2
            var centerY = rect.y + rect.height / 2
            var dx = targetX - centerX
            var dy = targetY - centerY
            if (Math.abs(dx) < 0.001 && Math.abs(dy) < 0.001) {
                return Qt.point(centerX, centerY)
            }
            var xScale = Math.abs(dx) < 0.001
                    ? Number.MAX_VALUE
                    : rect.width / 2 / Math.abs(dx)
            var yScale = Math.abs(dy) < 0.001
                    ? Number.MAX_VALUE
                    : rect.height / 2 / Math.abs(dy)
            var scale = Math.min(xScale, yScale)
            return Qt.point(centerX + dx * scale, centerY + dy * scale)
        }

        readonly property rect cardRect: Qt.rect(
            propertiesCard.x,
            propertiesCard.y,
            propertiesCard.width,
            propertiesCard.height
        )
        readonly property point sourceAnchor: edgePoint(
            propertiesPopup.sourceRect,
            cardRect.x + cardRect.width / 2,
            cardRect.y + cardRect.height / 2
        )
        readonly property point cardAnchor: edgePoint(
            cardRect,
            propertiesPopup.sourceRect.x
                + propertiesPopup.sourceRect.width / 2,
            propertiesPopup.sourceRect.y
                + propertiesPopup.sourceRect.height / 2
        )
        readonly property real connectorDx: cardAnchor.x - sourceAnchor.x
        readonly property real connectorDy: cardAnchor.y - sourceAnchor.y
        readonly property bool horizontalConnector:
                Math.abs(connectorDx) >= Math.abs(connectorDy)

        TextMetrics {
            id: frameTitleMetrics
            text: propertiesPopup.metadataValue("Title")
            font.family: "Segoe UI"
            font.pointSize: 9
        }

        Keys.onEscapePressed: function(event) {
            propertiesPopup.closeOverlay()
            event.accepted = true
        }

        MouseArea {
            anchors.fill: parent
            onClicked: function(mouse) {
                var insideCard = mouse.x >= propertiesCard.x
                        && mouse.x <= propertiesCard.x + propertiesCard.width
                        && mouse.y >= propertiesCard.y
                        && mouse.y <= propertiesCard.y + propertiesCard.height
                if (!insideCard) {
                    propertiesPopup.closeOverlay()
                }
            }
        }

        Quick.Canvas {
            id: dimmer
            anchors.fill: parent

            function roundedRectPath(context, rect, radius) {
                var safeRadius = Math.max(
                    0,
                    Math.min(radius, rect.width / 2, rect.height / 2)
                )
                context.beginPath()
                context.moveTo(rect.x + safeRadius, rect.y)
                context.lineTo(rect.x + rect.width - safeRadius, rect.y)
                context.quadraticCurveTo(
                    rect.x + rect.width,
                    rect.y,
                    rect.x + rect.width,
                    rect.y + safeRadius
                )
                context.lineTo(
                    rect.x + rect.width,
                    rect.y + rect.height - safeRadius
                )
                context.quadraticCurveTo(
                    rect.x + rect.width,
                    rect.y + rect.height,
                    rect.x + rect.width - safeRadius,
                    rect.y + rect.height
                )
                context.lineTo(
                    rect.x + safeRadius,
                    rect.y + rect.height
                )
                context.quadraticCurveTo(
                    rect.x,
                    rect.y + rect.height,
                    rect.x,
                    rect.y + rect.height - safeRadius
                )
                context.lineTo(rect.x, rect.y + safeRadius)
                context.quadraticCurveTo(
                    rect.x,
                    rect.y,
                    rect.x + safeRadius,
                    rect.y
                )
                context.closePath()
            }

            function cutNodeShape(context) {
                var source = propertiesPopup.sourceRect
                if (source.width <= 0 || source.height <= 0) {
                    return
                }

                var scale = Math.max(propertiesPopup.contentScale, 0.12)
                context.save()
                context.globalCompositeOperation = "destination-out"
                context.fillStyle = "#ffffffff"

                if (propertiesPopup.metadataValue("Type") === "frame") {
                    roundedRectPath(context, source, 8 * scale)
                    context.fill()

                    var titleWidth = Math.max(
                        88 * scale,
                        Math.min(
                            source.width - 24 * scale,
                            (frameTitleMetrics.advanceWidth + 72) * scale
                        )
                    )
                    var titleRect = Qt.rect(
                        source.x + (source.width - titleWidth) / 2,
                        source.y - 14 * scale,
                        titleWidth,
                        30 * scale
                    )
                    roundedRectPath(context, titleRect, 15 * scale)
                    context.fill()
                } else {
                    roundedRectPath(context, source, 4 * scale)
                    context.fill()
                }
                context.restore()
            }

            onWidthChanged: requestPaint()
            onHeightChanged: requestPaint()
            onPaint: {
                var context = getContext("2d")
                context.clearRect(0, 0, width, height)
                context.fillStyle = propertiesPopup.appTheme.overlayDim
                context.fillRect(0, 0, width, height)
                cutNodeShape(context)
            }
        }

        Connections {
            target: propertiesPopup.appTheme
            function onPaletteChanged() {
                dimmer.requestPaint()
            }
        }

        Shape {
            id: connector
            anchors.fill: parent
            visible: propertiesPopup.sourceRect.width > 0
                     && propertiesPopup.sourceRect.height > 0
            preferredRendererType: Shape.CurveRenderer

            ShapePath {
                strokeColor: propertiesPopup.appTheme.accentMain
                strokeWidth: 1.65
                capStyle: ShapePath.FlatCap
                fillColor: "transparent"
                startX: overlayBody.sourceAnchor.x
                startY: overlayBody.sourceAnchor.y

                PathCubic {
                    control1X: overlayBody.horizontalConnector
                            ? overlayBody.sourceAnchor.x
                                + overlayBody.connectorDx * 0.42
                            : overlayBody.sourceAnchor.x
                    control1Y: overlayBody.horizontalConnector
                            ? overlayBody.sourceAnchor.y
                            : overlayBody.sourceAnchor.y
                                + overlayBody.connectorDy * 0.42
                    control2X: overlayBody.horizontalConnector
                            ? overlayBody.cardAnchor.x
                                - overlayBody.connectorDx * 0.42
                            : overlayBody.cardAnchor.x
                    control2Y: overlayBody.horizontalConnector
                            ? overlayBody.cardAnchor.y
                            : overlayBody.cardAnchor.y
                                - overlayBody.connectorDy * 0.42
                    x: overlayBody.cardAnchor.x
                    y: overlayBody.cardAnchor.y
                }
            }
        }

        Rectangle {
            id: propertiesCard
            objectName: "nodePropertiesCard"
            property bool userPositioned: false
            readonly property real edgeMargin: 12

            x: 0
            y: 0
            width: Math.min(372, Math.max(280, overlayBody.width - 36))
            height: Math.min(
                Math.max(218, metadataRows.implicitHeight + 124),
                Math.max(120, overlayBody.height - 36)
            )
            color: propertiesPopup.appTheme.bgNode
            radius: 4
            border.width: 1.65
            border.color: propertiesPopup.appTheme.borderSelected

            MouseArea {
                id: cardInteraction
                anchors.fill: parent
                acceptedButtons: Qt.LeftButton
                hoverEnabled: true
                preventStealing: true
                cursorShape: pressed ? Qt.ClosedHandCursor : Qt.SizeAllCursor
                drag.target: propertiesCard
                drag.axis: Drag.XAndYAxis
                drag.minimumX: propertiesCard.edgeMargin
                drag.maximumX: Math.max(
                    propertiesCard.edgeMargin,
                    overlayBody.width - propertiesCard.width
                        - propertiesCard.edgeMargin
                )
                drag.minimumY: propertiesCard.edgeMargin
                drag.maximumY: Math.max(
                    propertiesCard.edgeMargin,
                    overlayBody.height - propertiesCard.height
                        - propertiesCard.edgeMargin
                )
                drag.filterChildren: true
                drag.smoothed: false
                onPressed: propertiesCard.userPositioned = true

                Column {
                    anchors.fill: parent
                    anchors.margins: 14
                    spacing: 10

                    Item {
                        width: parent.width
                        height: 42

                        Rectangle {
                            id: idBadge
                            width: Math.max(40, idBadgeText.implicitWidth + 16)
                            height: 30
                            anchors.left: parent.left
                            anchors.verticalCenter: parent.verticalCenter
                            radius: 4
                            color: propertiesPopup.appTheme.accentLow
                            border.width: 1
                            border.color: propertiesPopup.appTheme.accentMain

                            Text {
                                id: idBadgeText
                                anchors.centerIn: parent
                                text: propertiesPopup.nodeIdLabel
                                color: propertiesPopup.appTheme.textMain
                                font.family: "Consolas"
                                font.pointSize: 9
                                font.bold: true
                            }
                        }

                        Column {
                            anchors.left: idBadge.right
                            anchors.leftMargin: 10
                            anchors.right: closeButtonSlot.left
                            anchors.rightMargin: 8
                            anchors.verticalCenter: parent.verticalCenter
                            spacing: 2

                            Text {
                                width: parent.width
                                text: propertiesPopup.nodeTypeLabel
                                color: propertiesPopup.appTheme.textMain
                                font.family: "Segoe UI Semibold"
                                font.pointSize: 11
                                font.bold: true
                                elide: Text.ElideRight
                            }

                            Text {
                                width: parent.width
                                text: propertiesPopup.nodeTitleLine
                                color: propertiesPopup.appTheme.textMuted
                                font.family: "Segoe UI"
                                font.pointSize: 8.5
                                elide: Text.ElideRight
                            }
                        }

                        Item {
                            id: closeButtonSlot
                            width: 32
                            height: 32
                            anchors.right: parent.right
                            anchors.verticalCenter: parent.verticalCenter
                        }
                    }

                    Rectangle {
                        width: parent.width
                        height: 1
                        color: propertiesPopup.appTheme.borderSubtle
                    }

                    Flickable {
                        id: metadataFlickable
                        width: parent.width
                        height: Math.max(
                            70,
                            Math.min(
                                metadataRows.implicitHeight,
                                propertiesCard.height - 100
                            )
                        )
                        contentWidth: width
                        contentHeight: metadataRows.implicitHeight
                        clip: true
                        boundsBehavior: Flickable.StopAtBounds

                        ScrollBar.vertical: ScrollBar {
                            policy: metadataFlickable.contentHeight
                                    > metadataFlickable.height
                                    ? ScrollBar.AsNeeded
                                    : ScrollBar.AlwaysOff
                        }

                        Column {
                            id: metadataRows
                            width: parent.width
                            spacing: 0

                            Repeater {
                                model: propertiesPopup.displayRows

                                delegate: Item {
                                    id: metadataRow
                                    required property int index
                                    required property var modelData
                                    width: metadataRows.width
                                    implicitHeight: Math.max(
                                        propertyName.implicitHeight,
                                        propertyValue.implicitHeight
                                    ) + 12
                                    Text {
                                        id: propertyName
                                        x: 0
                                        y: 5
                                        width: Math.min(112, metadataRow.width * 0.35)
                                        text: metadataRow.modelData.label
                                        color: propertiesPopup.appTheme.textMuted
                                        font.family: "Segoe UI Semibold"
                                        font.pointSize: 8.5
                                        font.bold: true
                                        wrapMode: Text.Wrap
                                    }

                                    Text {
                                        id: propertyValue
                                        x: propertyName.width + 12
                                        y: 5
                                        width: metadataRow.width - x - 8
                                        text: metadataRow.modelData.value
                                        color: propertiesPopup.appTheme.textMain
                                        font.family: "Segoe UI"
                                        font.pointSize: 9
                                        wrapMode: Text.Wrap
                                        textFormat: Text.PlainText
                                    }

                                    Rectangle {
                                        visible: metadataRow.index
                                                 < propertiesPopup.displayRows.length - 1
                                        x: propertyValue.x
                                        width: propertyValue.width
                                        height: 1
                                        anchors.bottom: parent.bottom
                                        color: propertiesPopup.appTheme.borderSubtle
                                        opacity: 0.55
                                    }
                                }
                            }
                        }
                    }
                }
            }

            Button {
                id: closeButton
                objectName: "nodePropertiesCloseButton"
                z: 2
                width: 32
                height: 32
                anchors.top: parent.top
                anchors.right: parent.right
                anchors.topMargin: 19
                anchors.rightMargin: 14
                padding: 0
                hoverEnabled: true
                focusPolicy: Qt.TabFocus
                onClicked: propertiesPopup.closeOverlay()

                background: Rectangle {
                    radius: 4
                    color: closeButton.down
                           ? propertiesPopup.appTheme.bgControl
                           : closeButton.hovered
                             ? propertiesPopup.appTheme.bgControlHover
                             : "transparent"
                    border.width: closeButton.visualFocus ? 1 : 0
                    border.color: propertiesPopup.appTheme.accentMain
                }

                contentItem: Text {
                    text: "×"
                    color: propertiesPopup.appTheme.textDim
                    font.family: "Segoe UI"
                    font.pointSize: 13
                    horizontalAlignment: Text.AlignHCenter
                    verticalAlignment: Text.AlignVCenter
                }

                Accessible.name: "Close node properties"
            }
        }

    }
}
