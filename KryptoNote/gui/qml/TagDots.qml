pragma ComponentBehavior: Bound

import QtQuick

Item {
    id: summary

    required property var appTheme
    property var tags: []
    property real trailingInset: 0
    readonly property color chipBaseColor: summary.appTheme.bgNode
    readonly property real layoutWidth: Math.max(0, width - trailingInset)
    readonly property int chipGap: 4
    readonly property int displayCount: calculateDisplayCount()
    readonly property int remainingCount: Math.max(0, (tags ? tags.length : 0) - displayCount)

    height: 20
    visible: tags && tags.length > 0
    clip: true

    FontMetrics {
        id: chipMetrics
        font.family: "Segoe UI Semibold"
        font.pointSize: 7
    }

    function desiredChipWidth(tag) {
        var name = tag && tag.name !== undefined ? String(tag.name) : ""
        return Math.min(112, Math.max(30, Math.ceil(chipMetrics.advanceWidth(name)) + 24))
    }

    function moreChipWidth(count) {
        return Math.max(26, Math.ceil(chipMetrics.advanceWidth("+" + count)) + 12)
    }

    function calculateDisplayCount() {
        if (!tags || tags.length === 0 || layoutWidth <= 0) return 0

        var used = 0
        var count = 0
        for (var i = 0; i < tags.length; i++) {
            var next = desiredChipWidth(tags[i]) + (count > 0 ? chipGap : 0)
            var remaining = tags.length - i - 1
            var total = used + next
            if (remaining > 0) total += chipGap + moreChipWidth(remaining)
            if (total > layoutWidth) break
            used += next
            count++
        }

        if (count > 0) return count
        if (tags.length === 1) return 1

        var compactReserve = chipGap + moreChipWidth(tags.length - 1)
        return layoutWidth >= compactReserve + 18 ? 1 : 0
    }

    function chipWidth(index) {
        var available = layoutWidth
        if (displayCount === 1 && remainingCount > 0) {
            available -= chipGap + moreChipWidth(remainingCount)
        }
        return Math.max(0, Math.min(desiredChipWidth(tags[index]), available))
    }

    function blendedColor(baseColor, tintColor, amount) {
        var inverse = 1.0 - amount
        return Qt.rgba(
            baseColor.r * inverse + tintColor.r * amount,
            baseColor.g * inverse + tintColor.g * amount,
            baseColor.b * inverse + tintColor.b * amount,
            1.0
        )
    }

    Row {
        width: summary.layoutWidth
        height: parent.height
        spacing: summary.chipGap

        Repeater {
            model: summary.displayCount

            Rectangle {
                id: chip
                required property int index
                property color chipColor: summary.tags[index].color

                width: summary.chipWidth(index)
                height: summary.height
                radius: 7
                color: summary.blendedColor(summary.chipBaseColor, chipColor, 0.2)
                border.width: 1
                border.color: chipColor

                Rectangle {
                    width: 7
                    height: 7
                    radius: 4
                    anchors.left: parent.left
                    anchors.leftMargin: 7
                    anchors.verticalCenter: parent.verticalCenter
                    color: chip.chipColor
                }

                Text {
                    anchors.left: parent.left
                    anchors.leftMargin: 18
                    anchors.right: parent.right
                    anchors.rightMargin: 6
                    anchors.verticalCenter: parent.verticalCenter
                    text: summary.tags[chip.index].name
                    color: summary.appTheme.textMain
                    elide: Text.ElideRight
                    font.family: "Segoe UI Semibold"
                    font.pointSize: 7
                }
            }
        }

        Rectangle {
            visible: summary.remainingCount > 0
            width: Math.min(summary.layoutWidth, summary.moreChipWidth(summary.remainingCount))
            height: summary.height
            radius: 7
            color: summary.appTheme.bgNode
            border.width: 1
            border.color: summary.appTheme.borderHover

            Text {
                anchors.centerIn: parent
                text: "+" + summary.remainingCount
                color: summary.appTheme.textDim
                font.family: "Segoe UI Semibold"
                font.pointSize: 7
            }
        }
    }
}
