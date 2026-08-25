pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls.Basic

Item {
    id: control

    required property var appTheme
    required property var viewerController
    required property real availableWidth
    property string mediaName: "Media"
    property real muteReveal: responsiveReveal(availableWidth, 140, 180)
    property real sliderReveal: responsiveReveal(availableWidth, 260, 340)
    property real wheelDeltaRemainder: 0

    implicitWidth: 34 * muteReveal + 5 * sliderReveal + 74 * sliderReveal
    implicitHeight: 34
    visible: muteReveal > 0.01 || sliderReveal > 0.01
    clip: true

    function responsiveReveal(width, hiddenAt, shownAt) {
        return Math.max(0.0, Math.min(
            1.0,
            (width - hiddenAt) / Math.max(1, shownAt - hiddenAt)
        ))
    }

    function adjustVolumeByWheel(event) {
        var delta = Number(event.angleDelta.y) || 0
        if (delta === 0) return false
        wheelDeltaRemainder += delta
        var detents = wheelDeltaRemainder > 0
                ? Math.floor(wheelDeltaRemainder / 120)
                : Math.ceil(wheelDeltaRemainder / 120)
        if (detents !== 0) {
            wheelDeltaRemainder -= detents * 120
            viewerController.set_volume(
                viewerController.volume + detents * 4
            )
        }
        return true
    }

    Behavior on muteReveal {
        NumberAnimation {
            duration: control.appTheme.motionEnabled ? 130 : 0
            easing.type: Easing.OutCubic
        }
    }
    Behavior on sliderReveal {
        NumberAnimation {
            duration: control.appTheme.motionEnabled ? 130 : 0
            easing.type: Easing.OutCubic
        }
    }

    Item {
        id: muteSlot
        width: 34 * control.muteReveal
        height: 34
        anchors.left: parent.left
        anchors.verticalCenter: parent.verticalCenter
        opacity: control.muteReveal
        enabled: control.muteReveal > 0.5
        clip: true

        MediaIconButton {
            anchors.left: parent.left
            anchors.verticalCenter: parent.verticalCenter
            appTheme: control.appTheme
            iconSource: control.viewerController.muted
                        ? "../assets/icons/mute.svg"
                        : "../assets/icons/volume.svg"
            accessibleName: control.viewerController.muted
                            ? "Unmute " + control.mediaName.toLowerCase() + " (M)"
                            : "Mute " + control.mediaName.toLowerCase() + " (M)"
            onClicked: control.viewerController.toggle_mute()
        }
    }

    Slider {
        id: volumeSlider
        objectName: control.mediaName.toLowerCase() + "VolumeSlider"
        x: muteSlot.width + 5 * control.sliderReveal
        anchors.verticalCenter: parent.verticalCenter
        width: 74 * control.sliderReveal
        height: 30
        visible: control.sliderReveal > 0.01
        opacity: control.sliderReveal
        enabled: control.sliderReveal > 0.5
        clip: true
        from: 0
        to: 100
        stepSize: 2
        focusPolicy: Qt.TabFocus
        Accessible.name: control.mediaName + " volume"
        onMoved: control.viewerController.set_volume(value)

        background: Rectangle {
            x: volumeSlider.leftPadding
            y: volumeSlider.topPadding
               + volumeSlider.availableHeight / 2 - height / 2
            width: volumeSlider.availableWidth
            height: 4
            radius: 2
            color: control.appTheme.sliderTrack

            Rectangle {
                width: volumeSlider.visualPosition * parent.width
                height: parent.height
                radius: parent.radius
                color: control.appTheme.textDim
            }
        }

        handle: Rectangle {
            x: volumeSlider.leftPadding
               + volumeSlider.visualPosition
               * (volumeSlider.availableWidth - width)
            y: volumeSlider.topPadding
               + volumeSlider.availableHeight / 2 - height / 2
            width: 11
            height: 11
            radius: 6
            color: volumeSlider.visualFocus
                   ? control.appTheme.accentMain
                   : control.appTheme.sliderHandle
        }

        Binding {
            target: volumeSlider
            property: "value"
            value: control.viewerController.volume
            when: !volumeSlider.pressed
        }

        WheelHandler {
            target: null
            enabled: volumeSlider.enabled
            acceptedModifiers: Qt.NoModifier
            acceptedDevices: PointerDevice.Mouse
            onWheel: function(event) {
                event.accepted = control.adjustVolumeByWheel(event)
            }
        }
    }
}
