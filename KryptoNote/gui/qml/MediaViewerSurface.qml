pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import QtMultimedia

FocusScope {
    id: surface
    objectName: "mediaViewerSurface"

    required property var appTheme
    required property var canvasController
    required property var viewerController
    property bool expanded: false
    property bool showExpand: true
    property bool surfaceActive: false

    readonly property bool tagPickerOpen: mediaTagPicker.visible
    readonly property bool renameEditing: titleInput.activeFocus
                                          || _renameNodeId > 0
    readonly property bool videoNarrow: width < 520
    property bool _applyingImageState: false
    property bool _cancelingRename: false
    property string _renameOriginal: ""
    property int _renameNodeId: 0
    property int imageRotation: 0
    property real imageZoom: 1.0
    property real imagePanX: 0.0
    property real imagePanY: 0.0
    property bool imageFit: true
    property bool _syncingDescription: false
    property string _pendingMediaAction: ""
    // Keep media descriptions on the same size scale as the text editor.
    // In particular, 11pt must remain selectable after a save/reload.
    property var descriptionFontSizes: [
        8, 9, 10, 11, 12, 14, 16, 18, 20, 24, 28, 32, 36, 48, 64
    ]
    readonly property bool descriptionVisible: viewerController.active
                                               && (viewerController.mediaType === "image"
                                                   || viewerController.mediaType === "video"
                                                   || viewerController.mediaType === "audio")
    readonly property real descriptionSplitRatio: Math.max(
        0.10,
        Math.min(0.90, Number(viewerController.descriptionSplitRatio) || 0.20)
    )
    readonly property real splitAvailableHeight: Math.max(
        0,
        surfaceColumn.height
        - header.height
        - mediaControls.height
        - tagBar.height
        - metadataBlock.height
        - surfaceColumn.spacing * 5
    )
    readonly property bool playbackForCurrentNode: viewerController.active
                                                   && viewerController.playbackNodeId
                                                      === viewerController.nodeId

    signal closeRequested()
    signal detachRequested()
    signal expandRequested()
    signal applicationCloseRequested()
    signal descriptionGuardCanceled(string action)

    focus: true
    clip: true

    function formatTime(milliseconds) {
        var total = Math.max(0, Math.floor(milliseconds / 1000))
        var hours = Math.floor(total / 3600)
        var minutes = Math.floor((total % 3600) / 60)
        var seconds = total % 60
        if (hours > 0) {
            return hours + ":" + String(minutes).padStart(2, "0")
                    + ":" + String(seconds).padStart(2, "0")
        }
        return minutes + ":" + String(seconds).padStart(2, "0")
    }

    function effectiveImageZoom() {
        if (!imageFit) return imageZoom
        var baseWidth = mediaImage.implicitWidth
        var baseHeight = mediaImage.implicitHeight
        if (baseWidth <= 0 || baseHeight <= 0) return 1.0
        var quarterTurn = imageRotation % 180 !== 0
        var rotatedWidth = quarterTurn ? baseHeight : baseWidth
        var rotatedHeight = quarterTurn ? baseWidth : baseHeight
        return Math.min(8.0, Math.min(
            Math.max(1, imageViewport.width - 28) / rotatedWidth,
            Math.max(1, imageViewport.height - 28) / rotatedHeight
        ))
    }

    function rotatedImageWidth(zoom) {
        var baseWidth = Math.max(1, mediaImage.implicitWidth) * zoom
        var baseHeight = Math.max(1, mediaImage.implicitHeight) * zoom
        return imageRotation % 180 !== 0 ? baseHeight : baseWidth
    }

    function rotatedImageHeight(zoom) {
        var baseWidth = Math.max(1, mediaImage.implicitWidth) * zoom
        var baseHeight = Math.max(1, mediaImage.implicitHeight) * zoom
        return imageRotation % 180 !== 0 ? baseWidth : baseHeight
    }

    function imagePanPixelsX() {
        return imagePanX * rotatedImageWidth(effectiveImageZoom())
    }

    function imagePanPixelsY() {
        return imagePanY * rotatedImageHeight(effectiveImageZoom())
    }

    function publishImageState() {
        if (_applyingImageState || !viewerController.active
                || viewerController.mediaType !== "image") return
        viewerController.set_image_view_state(
            imageRotation,
            imageZoom,
            imagePanX,
            imagePanY,
            imageFit
        )
    }

    function syncImageState() {
        var state = viewerController.imageState
        if (!state) return
        _applyingImageState = true
        imageRotation = Number(state.rotation || 0)
        imageZoom = Number(state.zoom || 1.0)
        imagePanX = Number(state.panX || 0.0)
        imagePanY = Number(state.panY || 0.0)
        imageFit = state.fit !== false
        _applyingImageState = false
    }

    function setFit() {
        imageFit = true
        imagePanX = 0
        imagePanY = 0
        publishImageState()
    }

    function setActualSize() {
        imageFit = false
        imageZoom = 1.0
        imagePanX = 0
        imagePanY = 0
        publishImageState()
    }

    function zoomAt(pointX, pointY, factor) {
        if (mediaImage.status !== Image.Ready) return
        var oldZoom = Math.max(0.0001, effectiveImageZoom())
        var nextZoom = Math.max(0.1, Math.min(8.0, oldZoom * factor))
        if (Math.abs(nextZoom - oldZoom) < 0.0001) return
        var cursorX = pointX - imageViewport.width / 2
        var cursorY = pointY - imageViewport.height / 2
        var oldPanPixelsX = imagePanPixelsX()
        var oldPanPixelsY = imagePanPixelsY()
        var zoomRatio = nextZoom / oldZoom
        var nextPanPixelsX = cursorX - (cursorX - oldPanPixelsX) * zoomRatio
        var nextPanPixelsY = cursorY - (cursorY - oldPanPixelsY) * zoomRatio
        imageFit = false
        imageZoom = nextZoom
        imagePanX = nextPanPixelsX / Math.max(1, rotatedImageWidth(nextZoom))
        imagePanY = nextPanPixelsY / Math.max(1, rotatedImageHeight(nextZoom))
        publishImageState()
    }

    function rotateImage(delta) {
        var oldPanPixelsX = imagePanPixelsX()
        var oldPanPixelsY = imagePanPixelsY()
        imageRotation = (imageRotation + delta + 360) % 360
        if (imageFit) {
            imagePanX = 0
            imagePanY = 0
        } else {
            imagePanX = oldPanPixelsX / Math.max(
                1,
                rotatedImageWidth(effectiveImageZoom())
            )
            imagePanY = oldPanPixelsY / Math.max(
                1,
                rotatedImageHeight(effectiveImageZoom())
            )
        }
        publishImageState()
    }

    function commitRename() {
        if (_cancelingRename || _renameNodeId <= 0) return true
        if (!viewerController.active || viewerController.nodeId !== _renameNodeId) {
            _cancelingRename = true
            titleInput.text = viewerController.active ? viewerController.title : ""
            _renameOriginal = titleInput.text
            _renameNodeId = viewerController.active && titleInput.activeFocus
                            ? viewerController.nodeId : 0
            Qt.callLater(function() { surface._cancelingRename = false })
            return false
        }
        var normalized = titleInput.text.trim()
        if (normalized === viewerController.title) {
            titleInput.text = viewerController.title
            _renameOriginal = viewerController.title
            return true
        }
        if (!viewerController.rename_current(normalized)) return false
        titleInput.text = viewerController.title
        _renameOriginal = viewerController.title
        return true
    }

    function syncTitleForSession() {
        var currentNodeId = viewerController.active ? viewerController.nodeId : 0
        if (titleInput.activeFocus && _renameNodeId === currentNodeId) return
        _cancelingRename = true
        titleInput.text = viewerController.title
        _renameOriginal = viewerController.title
        _renameNodeId = titleInput.activeFocus ? currentNodeId : 0
        if (mediaTagPicker.visible && mediaTagPicker.nodeId !== currentNodeId)
            mediaTagPicker.close()
        Qt.callLater(function() { surface._cancelingRename = false })
    }

    function commitPendingEdits() {
        var wasRenaming = titleInput.activeFocus || _renameNodeId > 0
        if (!commitRename()) return false
        if (viewerController.descriptionDirty) return false
        _renameNodeId = 0
        if (mediaTagPicker.visible) mediaTagPicker.close()
        if (wasRenaming) viewportFocus.forceActiveFocus()
        return true
    }

    function requestExport() {
        if (commitRename()) viewerController.export_current()
    }

    function requestDetachOrAttach() {
        if (!commitPendingEdits()) {
            if (viewerController.descriptionDirty)
                openDescriptionGuard(viewerController.detached ? "attach" : "detach")
            return
        }
        if (viewerController.detached)
            viewerController.request_attach()
        else
            detachRequested()
    }

    function requestClose() {
        if (!commitPendingEdits()) {
            if (viewerController.descriptionDirty)
                openDescriptionGuard("close")
            return
        }
        closeRequested()
    }

    function syncDescriptionForSession() {
        if (_syncingDescription || (descriptionEditor.activeFocus
                                   && viewerController.descriptionDirty)) return
        _syncingDescription = true
        descriptionEditor.text = viewerController.descriptionDraft || ""
        descriptionSizeCombo.currentIndex = descriptionSizeIndex(
            viewerController.descriptionTextSize
        )
        _syncingDescription = false
    }

    function descriptionSizeIndex(size) {
        var normalized = Number(size) || 10
        var index = descriptionFontSizes.indexOf(normalized)
        if (index >= 0) return index
        var fallback = descriptionFontSizes.indexOf(10)
        return fallback >= 0 ? fallback : 0
    }

    function saveDescriptionAndContinue() {
        if (!viewerController.save_description()) return false
        descriptionGuard.close()
        var action = _pendingMediaAction
        _pendingMediaAction = ""
        if (action === "close") closeRequested()
        else if (action === "detach") detachRequested()
        else if (action === "attach") viewerController.request_attach()
        else if (action === "application-close") applicationCloseRequested()
        else if (action.indexOf("switch:") === 0)
            viewerController.open_media_viewer(Number(action.substring(7)))
        return true
    }

    function discardDescriptionAndContinue() {
        viewerController.discard_description()
        descriptionGuard.close()
        var action = _pendingMediaAction
        _pendingMediaAction = ""
        if (action === "close") closeRequested()
        else if (action === "detach") detachRequested()
        else if (action === "attach") viewerController.request_attach()
        else if (action === "application-close") applicationCloseRequested()
        else if (action.indexOf("switch:") === 0)
            viewerController.open_media_viewer(Number(action.substring(7)))
    }

    function openDescriptionGuard(action) {
        _pendingMediaAction = action
        descriptionGuard.open()
    }

    function cancelDescriptionGuard() {
        var action = _pendingMediaAction
        _pendingMediaAction = ""
        descriptionGuard.close()
        descriptionGuardCanceled(action)
    }

    function cancelRename() {
        if (!titleInput.activeFocus && _renameNodeId <= 0) return false
        _cancelingRename = true
        titleInput.text = _renameOriginal
        _renameNodeId = 0
        viewportFocus.forceActiveFocus()
        Qt.callLater(function() { surface._cancelingRename = false })
        return true
    }

    function closeTagPicker() {
        if (!mediaTagPicker.visible) return false
        mediaTagPicker.close()
        return true
    }

    function handleEscape() {
        if (closeTagPicker()) return true
        if (cancelRename()) return true
        if (descriptionEditor.activeFocus) {
            if (viewerController.descriptionDirty)
                openDescriptionGuard("close")
            else
                viewportFocus.forceActiveFocus()
            return true
        }
        if (showExpand && expanded) {
            expandRequested()
            return true
        }
        if (viewerController.descriptionDirty) {
            openDescriptionGuard("close")
            return true
        }
        closeRequested()
        return true
    }

    function syncVideoOutput() {
        if (surfaceActive && viewerController.active
                && viewerController.mediaType === "video"
                && viewerController.playbackNodeId === viewerController.nodeId
                && viewerController.errorText.length === 0) {
            viewerController.attach_video_output(videoOutput)
        } else {
            viewerController.detach_video_output(videoOutput)
        }
    }

    Component.onCompleted: {
        syncTitleForSession()
        syncDescriptionForSession()
        syncImageState()
        syncVideoOutput()
    }
    Component.onDestruction: viewerController.detach_video_output(videoOutput)
    onSurfaceActiveChanged: syncVideoOutput()

    Keys.onPressed: function(event) {
        if (event.key === Qt.Key_Escape) {
            surface.handleEscape()
            event.accepted = true
            return
        }
        if (descriptionEditor.activeFocus || renameEditing || tagPickerOpen
                || (viewerController.mediaType !== "video"
                    && viewerController.mediaType !== "audio")
                || event.modifiers !== Qt.NoModifier) return
        if (event.key === Qt.Key_Space) {
            viewerController.toggle_playback()
            event.accepted = true
        } else if (event.key === Qt.Key_Left) {
            viewerController.seek(viewerController.position - 5000)
            event.accepted = true
        } else if (event.key === Qt.Key_Right) {
            viewerController.seek(viewerController.position + 5000)
            event.accepted = true
        } else if (event.key === Qt.Key_M) {
            viewerController.toggle_mute()
            event.accepted = true
        }
    }

    Rectangle {
        anchors.fill: parent
        color: surface.appTheme.bgPanel
    }

    Rectangle {
        width: 1
        anchors.left: parent.left
        anchors.top: parent.top
        anchors.bottom: parent.bottom
        color: surface.appTheme.borderDefault
    }

    Column {
        id: surfaceColumn
        anchors.fill: parent
        anchors.leftMargin: 12
        anchors.rightMargin: 10
        anchors.topMargin: 10
        anchors.bottomMargin: 10
        spacing: 8

        Item {
            id: header
            width: parent.width
            height: 40

            Rectangle {
                id: titleField
                anchors.left: parent.left
                anchors.right: headerActions.left
                anchors.rightMargin: 8
                anchors.verticalCenter: parent.verticalCenter
                height: 34
                radius: 7
                color: surface.appTheme.bgNode
                border.width: titleInput.activeFocus ? 1 : 0
                border.color: surface.appTheme.accentMain

                TextField {
                    id: titleInput
                    objectName: "mediaViewerTitleInput"
                    anchors.fill: parent
                    leftPadding: 10
                    rightPadding: 10
                    topPadding: 0
                    bottomPadding: 0
                    verticalAlignment: TextInput.AlignVCenter
                    selectByMouse: true
                    placeholderText: "Untitled media"
                    color: surface.appTheme.textMain
                    placeholderTextColor: surface.appTheme.textDim
                    font.family: "Segoe UI Semibold"
                    font.pointSize: 10
                    background: Item {}
                    ContextMenu.menu: null
                    Accessible.name: "Media title"

                    onActiveFocusChanged: {
                        if (activeFocus) {
                            surface._renameNodeId = surface.viewerController.active
                                                    ? surface.viewerController.nodeId : 0
                            surface._renameOriginal = surface.viewerController.title
                            selectAll()
                        } else {
                            if (surface.commitRename()) {
                                surface._renameNodeId = 0
                            } else {
                                Qt.callLater(function() {
                                    if (surface.viewerController.active
                                            && surface.viewerController.nodeId
                                               === surface._renameNodeId) {
                                        titleInput.forceActiveFocus()
                                    }
                                })
                            }
                        }
                    }
                    onEditingFinished: surface.commitRename()
                    Keys.onPressed: function(event) {
                        if (event.key === Qt.Key_Escape) {
                            surface.cancelRename()
                            event.accepted = true
                        } else if ((event.key === Qt.Key_Return
                                    || event.key === Qt.Key_Enter)
                                   && event.modifiers === Qt.NoModifier) {
                            if (surface.commitRename())
                                viewportFocus.forceActiveFocus()
                            event.accepted = true
                        }
                    }
                }
            }

            Row {
                id: headerActions
                anchors.right: parent.right
                anchors.verticalCenter: parent.verticalCenter
                spacing: 2

                MediaIconButton {
                    appTheme: surface.appTheme
                    iconSource: "../assets/icons/export.svg"
                    accessibleName: "Export original"
                    enabled: surface.viewerController.active
                    onClicked: surface.requestExport()
                }

                MediaIconButton {
                    appTheme: surface.appTheme
                    iconSource: surface.viewerController.detached
                                ? "../assets/icons/dock.svg"
                                : "../assets/icons/open.svg"
                    accessibleName: surface.viewerController.detached
                                    ? "Attach back"
                                    : "Open in separate window"
                    enabled: surface.viewerController.active
                    onClicked: surface.requestDetachOrAttach()
                }

                MediaIconButton {
                    appTheme: surface.appTheme
                    iconSource: surface.expanded
                                ? "../assets/icons/collapse.svg"
                                : "../assets/icons/expand.svg"
                    accessibleName: surface.expanded
                                    ? "Collapse viewer"
                                    : "Expand viewer"
                    visible: surface.showExpand
                    onClicked: surface.expandRequested()
                }

                MediaIconButton {
                    appTheme: surface.appTheme
                    iconSource: "../assets/icons/close.svg"
                    accessibleName: "Close viewer"
                    destructive: true
                    onClicked: surface.requestClose()
                }
            }
        }

        Rectangle {
            id: imageViewport
            objectName: "mediaViewport"
            width: parent.width
            height: Math.max(
                0,
                surface.splitAvailableHeight
                * (surface.descriptionVisible
                   ? 1 - surface.descriptionSplitRatio : 1)
            )
            radius: 8
            color: surface.appTheme.bgNode
            border.width: 1
            border.color: surface.appTheme.borderSubtle
            clip: true

            FocusScope {
                id: viewportFocus
                anchors.fill: parent
                focus: true
            }

            TapHandler {
                enabled: surface.viewerController.mediaType === "video"
                acceptedButtons: Qt.LeftButton
                onTapped: viewportFocus.forceActiveFocus()
            }

            Image {
                id: mediaImage
                objectName: "mediaPreviewImage"
                visible: surface.viewerController.mediaType === "image"
                         && !surface.viewerController.loading
                         && surface.viewerController.errorText.length === 0
                source: surface.surfaceActive
                        ? surface.viewerController.imageSource : ""
                cache: false
                asynchronous: false
                smooth: true
                mipmap: true
                width: Math.max(1, implicitWidth) * surface.effectiveImageZoom()
                height: Math.max(1, implicitHeight) * surface.effectiveImageZoom()
                x: (imageViewport.width - width) / 2
                   + surface.imagePanPixelsX()
                y: (imageViewport.height - height) / 2
                   + surface.imagePanPixelsY()
                transform: Rotation {
                    origin.x: mediaImage.width / 2
                    origin.y: mediaImage.height / 2
                    angle: surface.imageRotation
                }
            }

            VideoOutput {
                id: videoOutput
                objectName: "mediaVideoOutput"
                anchors.fill: parent
                anchors.margins: 1
                visible: surface.viewerController.mediaType === "video"
                         && surface.viewerController.errorText.length === 0
                fillMode: VideoOutput.PreserveAspectFit
            }

            AudioWaveform {
                id: viewerAudioWaveform
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.verticalCenter: parent.verticalCenter
                anchors.leftMargin: 24
                anchors.rightMargin: 24
                height: Math.min(86, Math.max(42, parent.height * 0.28))
                visible: surface.viewerController.mediaType === "audio"
                appTheme: surface.appTheme
                waveform: surface.viewerController.audioWaveform
                enabled: !surface.viewerController.loading
                         && surface.viewerController.errorText.length === 0
                progress: surface.viewerController.playbackNodeId
                          === surface.viewerController.nodeId
                          && surface.viewerController.duration > 0
                          ? surface.viewerController.position
                            / surface.viewerController.duration : 0
                onSeekRequested: function(fraction) {
                    surface.viewerController.seek_for(
                        surface.viewerController.nodeId,
                        fraction * Math.max(1, surface.viewerController.duration)
                    )
                }
            }

            Text {
                anchors.centerIn: viewerAudioWaveform
                visible: surface.viewerController.audioWaveform.length === 0
                         || surface.viewerController.duration <= 0
                text: "Waveform unavailable"
                color: surface.appTheme.textDim
                font.family: surface.appTheme.textFontFamily
                font.pointSize: 9
            }

            MouseArea {
                id: imageGestures
                anchors.fill: parent
                enabled: surface.viewerController.mediaType === "image"
                         && mediaImage.status === Image.Ready
                         && !surface.viewerController.loading
                         && surface.viewerController.errorText.length === 0
                acceptedButtons: Qt.LeftButton
                hoverEnabled: true
                cursorShape: pressed ? Qt.ClosedHandCursor : Qt.OpenHandCursor
                preventStealing: true
                property real pressX: 0
                property real pressY: 0
                property real startPanX: 0
                property real startPanY: 0
                property real panScaleX: 1
                property real panScaleY: 1

                onPressed: function(mouse) {
                    viewportFocus.forceActiveFocus()
                    pressX = mouse.x
                    pressY = mouse.y
                    startPanX = surface.imagePanX
                    startPanY = surface.imagePanY
                    panScaleX = Math.max(
                        1,
                        surface.rotatedImageWidth(surface.effectiveImageZoom())
                    )
                    panScaleY = Math.max(
                        1,
                        surface.rotatedImageHeight(surface.effectiveImageZoom())
                    )
                    mouse.accepted = true
                }
                onPositionChanged: function(mouse) {
                    if (!(mouse.buttons & Qt.LeftButton)) return
                    surface.imagePanX = startPanX
                        + (mouse.x - pressX) / panScaleX
                    surface.imagePanY = startPanY
                        + (mouse.y - pressY) / panScaleY
                }
                onReleased: surface.publishImageState()
                onCanceled: surface.publishImageState()
                onDoubleClicked: surface.setActualSize()
                onWheel: function(wheel) {
                    var delta = wheel.angleDelta.y
                    if (delta === 0) delta = wheel.pixelDelta.y
                    if (delta === 0) {
                        wheel.accepted = true
                        return
                    }
                    var factor = Math.pow(1.0015, delta)
                    factor = Math.max(0.75, Math.min(1.33, factor))
                    surface.zoomAt(
                        wheel.x,
                        wheel.y,
                        factor
                    )
                    wheel.accepted = true
                }
            }

            Column {
                anchors.centerIn: parent
                width: Math.min(parent.width - 36, 360)
                spacing: 12
                visible: surface.viewerController.loading

                BusyIndicator {
                    anchors.horizontalCenter: parent.horizontalCenter
                    width: 30
                    height: 30
                    running: visible
                    palette.dark: surface.appTheme.accentMain
                }

                Text {
                    width: parent.width
                    text: "Decrypting media..."
                    horizontalAlignment: Text.AlignHCenter
                    color: surface.appTheme.textDim
                    font.family: "Segoe UI"
                    font.pointSize: 9
                }
            }

            Column {
                anchors.centerIn: parent
                width: Math.min(parent.width - 36, 380)
                spacing: 12
                visible: surface.viewerController.errorText.length > 0

                Text {
                    width: parent.width
                    text: surface.viewerController.errorText
                    horizontalAlignment: Text.AlignHCenter
                    wrapMode: Text.Wrap
                    color: surface.appTheme.textDim
                    font.family: "Segoe UI"
                    font.pointSize: 9
                }

                Button {
                    id: retryButton
                    anchors.horizontalCenter: parent.horizontalCenter
                    width: 104
                    height: 32
                    text: "Retry"
                    hoverEnabled: true
                    focusPolicy: Qt.TabFocus
                    display: AbstractButton.TextBesideIcon
                    spacing: 6
                    icon.source: "../assets/icons/reset.svg"
                    icon.width: 14
                    icon.height: 14
                    icon.color: surface.appTheme.textMain
                    palette.buttonText: surface.appTheme.textMain
                    font.family: "Segoe UI Semibold"
                    font.pointSize: 9
                    background: Rectangle {
                        radius: 7
                        color: retryButton.down ? surface.appTheme.whiteAlpha15
                             : retryButton.hovered ? surface.appTheme.whiteAlpha10
                             : surface.appTheme.whiteAlpha05
                        border.width: retryButton.visualFocus ? 1.5 : 1
                        border.color: retryButton.visualFocus
                                      ? surface.appTheme.accentMain
                                      : surface.appTheme.borderDefault
                    }
                    Accessible.name: "Retry media loading"
                    ToolTip.visible: hovered
                    ToolTip.text: Accessible.name
                    ToolTip.delay: 450
                    onClicked: surface.viewerController.retry()
                }
            }
        }

        Item {
            id: descriptionSplit
            width: parent.width
            visible: surface.descriptionVisible
            height: visible
                    ? Math.max(0, surface.splitAvailableHeight
                                  * surface.descriptionSplitRatio)
                    : 0

            Rectangle {
                id: descriptionDivider
                width: parent.width
                height: 5
                anchors.top: parent.top
                color: dividerMouse.pressed || dividerMouse.containsMouse
                       ? surface.appTheme.accentMain
                       : surface.appTheme.borderDefault
                opacity: dividerMouse.pressed || dividerMouse.containsMouse ? 0.8 : 0.45

                MouseArea {
                    id: dividerMouse
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.SizeVerCursor
                    property real pressY: 0
                    property real startHeight: 0
                    onPressed: function(mouse) {
                        pressY = mouse.y
                        startHeight = descriptionSplit.height
                        forceActiveFocus()
                    }
                    onPositionChanged: function(mouse) {
                        if (!pressed) return
                        var availableHeight = surface.splitAvailableHeight
                        if (availableHeight <= 0) return
                        var nextHeight = startHeight + (mouse.y - pressY)
                        var ratio = nextHeight / availableHeight
                        surface.viewerController.set_description_split_ratio(ratio)
                    }
                }
            }

            Rectangle {
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.top: descriptionDivider.bottom
                anchors.bottom: parent.bottom
                color: surface.appTheme.bgNode
                border.width: 1
                border.color: surface.appTheme.borderSubtle
                radius: 7

                TextArea {
                    id: descriptionEditor
                    anchors.left: parent.left
                    anchors.right: descriptionActions.left
                    anchors.top: parent.top
                    anchors.bottom: parent.bottom
                    anchors.margins: 8
                    anchors.rightMargin: 4
                    text: ""
                    placeholderText: "Markdown description"
                    color: surface.appTheme.textMain
                    placeholderTextColor: surface.appTheme.textDim
                    selectionColor: surface.appTheme.accentMain
                    selectedTextColor: surface.appTheme.bgPanel
                    font.family: surface.appTheme.textFontFamily
                    font.pointSize: Math.max(8, Number(surface.viewerController.descriptionTextSize) || 10)
                    wrapMode: TextEdit.WrapAtWordBoundaryOrAnywhere
                    textFormat: TextEdit.PlainText
                    background: Item {}
                    selectByMouse: true
                    focusPolicy: Qt.TabFocus
                    Accessible.name: "Media Markdown description"
                    onTextChanged: {
                        if (!surface._syncingDescription)
                            surface.viewerController.set_description_draft(
                                text, surface.viewerController.descriptionTextSize
                            )
                    }
                    Keys.onPressed: function(event) {
                        if (event.key === Qt.Key_S
                                && (event.modifiers & Qt.ControlModifier)) {
                            surface.viewerController.save_description()
                            event.accepted = true
                        } else if (event.key === Qt.Key_Escape) {
                            surface.handleEscape()
                            event.accepted = true
                        }
                    }
                }

                Column {
                    id: descriptionActions
                    width: 86
                    anchors.right: parent.right
                    anchors.top: parent.top
                    anchors.bottom: parent.bottom
                    anchors.margins: 8
                    spacing: 4

                    Button {
                        width: parent.width
                        height: 28
                        text: "Save"
                        enabled: surface.viewerController.descriptionDirty
                        focusPolicy: Qt.TabFocus
                        Accessible.name: "Save description"
                        onClicked: surface.viewerController.save_description()
                    }
                    Button {
                        width: parent.width
                        height: 28
                        text: "Cancel"
                        enabled: surface.viewerController.descriptionDirty
                        focusPolicy: Qt.TabFocus
                        Accessible.name: "Discard description changes"
                        onClicked: surface.viewerController.discard_description()
                    }
                    ComboBox {
                        id: descriptionSizeCombo
                        width: parent.width
                        height: 28
                        model: surface.descriptionFontSizes
                        currentIndex: surface.descriptionSizeIndex(
                            surface.viewerController.descriptionTextSize
                        )
                        Accessible.name: "Description text size"
                        onActivated: surface.viewerController.set_description_draft(
                            descriptionEditor.text, Number(currentText)
                        )
                    }
                    Text {
                        width: parent.width
                        text: surface.viewerController.descriptionDirty ? "Unsaved" : "Saved"
                        color: surface.viewerController.descriptionDirty
                               ? surface.appTheme.accentMain : surface.appTheme.textDim
                        font.family: surface.appTheme.textFontFamily
                        font.pointSize: 8
                        horizontalAlignment: Text.AlignHCenter
                    }
                }
            }
        }

        Item {
            id: mediaControls
            width: parent.width
            height: surface.viewerController.mediaType === "video"
                    && surface.videoNarrow ? 74 : 38

            Row {
                id: imageControlRow
                anchors.centerIn: parent
                spacing: 3
                visible: surface.viewerController.mediaType === "image"

                MediaIconButton {
                    appTheme: surface.appTheme
                    iconSource: "../assets/icons/rotate-left.svg"
                    accessibleName: "Rotate left"
                    enabled: mediaImage.status === Image.Ready
                    onClicked: surface.rotateImage(-90)
                }
                MediaIconButton {
                    appTheme: surface.appTheme
                    iconSource: "../assets/icons/rotate-right.svg"
                    accessibleName: "Rotate right"
                    enabled: mediaImage.status === Image.Ready
                    onClicked: surface.rotateImage(90)
                }
                MediaIconButton {
                    appTheme: surface.appTheme
                    iconSource: "../assets/icons/zoom-out.svg"
                    accessibleName: "Zoom out"
                    enabled: mediaImage.status === Image.Ready
                    onClicked: surface.zoomAt(
                        imageViewport.width / 2,
                        imageViewport.height / 2,
                        1 / 1.2
                    )
                }
                Text {
                    width: 46
                    height: 34
                    text: Math.round(surface.effectiveImageZoom() * 100) + "%"
                    color: surface.appTheme.textMuted
                    horizontalAlignment: Text.AlignHCenter
                    verticalAlignment: Text.AlignVCenter
                    font.family: "Segoe UI Semibold"
                    font.pointSize: 8
                }
                MediaIconButton {
                    appTheme: surface.appTheme
                    iconSource: "../assets/icons/zoom-in.svg"
                    accessibleName: "Zoom in"
                    enabled: mediaImage.status === Image.Ready
                    onClicked: surface.zoomAt(
                        imageViewport.width / 2,
                        imageViewport.height / 2,
                        1.2
                    )
                }
                MediaIconButton {
                    appTheme: surface.appTheme
                    iconSource: "../assets/icons/fit.svg"
                    accessibleName: "Fit image"
                    emphasized: surface.imageFit
                    enabled: mediaImage.status === Image.Ready
                    onClicked: surface.setFit()
                }
                MediaIconButton {
                    appTheme: surface.appTheme
                    iconSource: "../assets/icons/actual-size.svg"
                    accessibleName: "Actual preview size (1:1)"
                    enabled: mediaImage.status === Image.Ready
                    onClicked: surface.setActualSize()
                }
            }

            RowLayout {
                anchors.fill: parent
                spacing: 6
                visible: surface.viewerController.mediaType === "audio"

                MediaIconButton {
                    appTheme: surface.appTheme
                    iconSource: surface.playbackForCurrentNode
                                && surface.viewerController.playing
                                ? "../assets/icons/pause.svg"
                                : "../assets/icons/play.svg"
                    accessibleName: surface.playbackForCurrentNode
                                    && surface.viewerController.playing
                                    ? "Pause audio" : "Play audio"
                    onClicked: surface.viewerController.toggle_playback()
                }

                Slider {
                    id: audioSeekSlider
                    Layout.fillWidth: true
                    Layout.preferredHeight: 30
                    from: 0
                    to: Math.max(1, surface.viewerController.duration)
                    focusPolicy: Qt.TabFocus
                    Accessible.name: "Audio position"
                    onMoved: surface.viewerController.seek(value)
                    background: Rectangle {
                        x: audioSeekSlider.leftPadding
                        y: audioSeekSlider.topPadding
                           + audioSeekSlider.availableHeight / 2 - height / 2
                        width: audioSeekSlider.availableWidth
                        height: 4
                        radius: 2
                        color: surface.appTheme.sliderTrack
                        Rectangle {
                            width: audioSeekSlider.visualPosition * parent.width
                            height: parent.height
                            radius: parent.radius
                            color: surface.appTheme.accentMain
                        }
                    }
                    handle: Rectangle {
                        x: audioSeekSlider.leftPadding + audioSeekSlider.visualPosition
                           * (audioSeekSlider.availableWidth - width)
                        y: audioSeekSlider.topPadding
                           + audioSeekSlider.availableHeight / 2 - height / 2
                        width: 12
                        height: 12
                        radius: 6
                        color: audioSeekSlider.visualFocus
                               ? surface.appTheme.accentMain : surface.appTheme.sliderHandle
                    }
                    Binding {
                        target: audioSeekSlider
                        property: "value"
                        value: surface.playbackForCurrentNode
                               ? surface.viewerController.position : 0
                        when: !audioSeekSlider.pressed
                    }
                }

                Text {
                    Layout.preferredWidth: 88
                    text: surface.formatTime(surface.playbackForCurrentNode
                                             ? surface.viewerController.position : 0)
                          + " / " + surface.formatTime(surface.playbackForCurrentNode
                                                       ? surface.viewerController.duration : 0)
                    color: surface.appTheme.textMuted
                    horizontalAlignment: Text.AlignRight
                    font.family: "Segoe UI"
                    font.pointSize: 8
                }
            }

            Column {
                anchors.fill: parent
                spacing: 2
                visible: surface.viewerController.mediaType === "video"

                RowLayout {
                    width: parent.width
                    height: 36
                    spacing: 6

                    MediaIconButton {
                        appTheme: surface.appTheme
                        iconSource: surface.playbackForCurrentNode
                                    && surface.viewerController.playing
                                    ? "../assets/icons/pause.svg"
                                    : "../assets/icons/play.svg"
                        accessibleName: surface.playbackForCurrentNode
                                        && surface.viewerController.playing
                                        ? "Pause video (Space)"
                                        : "Play video (Space)"
                        enabled: !surface.viewerController.loading
                                 && surface.viewerController.errorText.length === 0
                        onClicked: surface.viewerController.toggle_playback()
                    }

                    Slider {
                        id: seekSlider
                        Layout.fillWidth: true
                        Layout.minimumWidth: 70
                        Layout.preferredHeight: 30
                        from: 0
                        to: Math.max(1, surface.viewerController.duration)
                        stepSize: 5000
                        focusPolicy: Qt.TabFocus
                        Accessible.name: "Video position"
                        onPressedChanged: {
                            if (pressed) {
                                surface.viewerController.begin_seek()
                            } else {
                                surface.viewerController.seek(value)
                                surface.viewerController.end_seek()
                            }
                        }
                        onMoved: surface.viewerController.seek(value)

                        background: Rectangle {
                            x: seekSlider.leftPadding
                            y: seekSlider.topPadding + seekSlider.availableHeight / 2 - height / 2
                            width: seekSlider.availableWidth
                            height: 4
                            radius: 2
                            color: surface.appTheme.sliderTrack

                            Rectangle {
                                width: seekSlider.visualPosition * parent.width
                                height: parent.height
                                radius: parent.radius
                                color: surface.appTheme.accentMain
                            }
                        }
                        handle: Rectangle {
                            x: seekSlider.leftPadding + seekSlider.visualPosition
                               * (seekSlider.availableWidth - width)
                            y: seekSlider.topPadding + seekSlider.availableHeight / 2 - height / 2
                            width: 12
                            height: 12
                            radius: 6
                            color: seekSlider.visualFocus
                                   ? surface.appTheme.accentMain
                                   : surface.appTheme.sliderHandle
                            border.width: 1
                            border.color: surface.appTheme.bgPanel
                        }

                        Binding {
                            target: seekSlider
                            property: "value"
                            value: surface.playbackForCurrentNode
                                   ? surface.viewerController.position : 0
                            when: !seekSlider.pressed
                        }
                    }

                    Text {
                        Layout.preferredWidth: (surface.playbackForCurrentNode
                                               ? surface.viewerController.duration : 0)
                                               >= 3600000 ? 112 : 88
                        text: surface.formatTime(surface.playbackForCurrentNode
                                                 ? surface.viewerController.position : 0)
                              + " / " + surface.formatTime(surface.playbackForCurrentNode
                                                           ? surface.viewerController.duration : 0)
                        color: surface.appTheme.textMuted
                        horizontalAlignment: Text.AlignRight
                        verticalAlignment: Text.AlignVCenter
                        font.family: "Segoe UI"
                        font.pointSize: 8
                    }

                    MediaIconButton {
                        appTheme: surface.appTheme
                        iconSource: surface.viewerController.muted
                                    ? "../assets/icons/mute.svg"
                                    : "../assets/icons/volume.svg"
                        accessibleName: surface.viewerController.muted
                                        ? "Unmute video (M)"
                                        : "Mute video (M)"
                        visible: !surface.videoNarrow
                        onClicked: surface.viewerController.toggle_mute()
                    }

                    Slider {
                        id: wideVolumeSlider
                        Layout.preferredWidth: 82
                        Layout.preferredHeight: 30
                        visible: !surface.videoNarrow
                        from: 0
                        to: 100
                        stepSize: 2
                        focusPolicy: Qt.TabFocus
                        Accessible.name: "Video volume"
                        onMoved: surface.viewerController.set_volume(value)
                        background: Rectangle {
                            x: wideVolumeSlider.leftPadding
                            y: wideVolumeSlider.topPadding
                               + wideVolumeSlider.availableHeight / 2 - height / 2
                            width: wideVolumeSlider.availableWidth
                            height: 4
                            radius: 2
                            color: surface.appTheme.sliderTrack
                            Rectangle {
                                width: wideVolumeSlider.visualPosition * parent.width
                                height: parent.height
                                radius: parent.radius
                                color: surface.appTheme.textDim
                            }
                        }
                        handle: Rectangle {
                            x: wideVolumeSlider.leftPadding + wideVolumeSlider.visualPosition
                               * (wideVolumeSlider.availableWidth - width)
                            y: wideVolumeSlider.topPadding
                               + wideVolumeSlider.availableHeight / 2 - height / 2
                            width: 11
                            height: 11
                            radius: 6
                            color: wideVolumeSlider.visualFocus
                                   ? surface.appTheme.accentMain
                                   : surface.appTheme.sliderHandle
                        }
                        Binding {
                            target: wideVolumeSlider
                            property: "value"
                            value: surface.viewerController.volume
                            when: !wideVolumeSlider.pressed
                        }
                    }
                }

                RowLayout {
                    width: parent.width
                    height: 34
                    spacing: 6
                    visible: surface.videoNarrow

                    MediaIconButton {
                        appTheme: surface.appTheme
                        iconSource: surface.viewerController.muted
                                    ? "../assets/icons/mute.svg"
                                    : "../assets/icons/volume.svg"
                        accessibleName: surface.viewerController.muted
                                        ? "Unmute video (M)"
                                        : "Mute video (M)"
                        onClicked: surface.viewerController.toggle_mute()
                    }

                    Slider {
                        id: narrowVolumeSlider
                        Layout.fillWidth: true
                        Layout.preferredHeight: 30
                        from: 0
                        to: 100
                        stepSize: 2
                        focusPolicy: Qt.TabFocus
                        Accessible.name: "Video volume"
                        onMoved: surface.viewerController.set_volume(value)
                        background: Rectangle {
                            x: narrowVolumeSlider.leftPadding
                            y: narrowVolumeSlider.topPadding
                               + narrowVolumeSlider.availableHeight / 2 - height / 2
                            width: narrowVolumeSlider.availableWidth
                            height: 4
                            radius: 2
                            color: surface.appTheme.sliderTrack
                            Rectangle {
                                width: narrowVolumeSlider.visualPosition * parent.width
                                height: parent.height
                                radius: parent.radius
                                color: surface.appTheme.textDim
                            }
                        }
                        handle: Rectangle {
                            x: narrowVolumeSlider.leftPadding + narrowVolumeSlider.visualPosition
                               * (narrowVolumeSlider.availableWidth - width)
                            y: narrowVolumeSlider.topPadding
                               + narrowVolumeSlider.availableHeight / 2 - height / 2
                            width: 11
                            height: 11
                            radius: 6
                            color: narrowVolumeSlider.visualFocus
                                   ? surface.appTheme.accentMain
                                   : surface.appTheme.sliderHandle
                        }
                        Binding {
                            target: narrowVolumeSlider
                            property: "value"
                            value: surface.viewerController.volume
                            when: !narrowVolumeSlider.pressed
                        }
                    }

                    Text {
                        Layout.preferredWidth: 38
                        text: surface.viewerController.muted
                              ? "Muted" : surface.viewerController.volume + "%"
                        color: surface.appTheme.textMuted
                        horizontalAlignment: Text.AlignRight
                        font.family: "Segoe UI"
                        font.pointSize: 8
                    }
                }
            }
        }

        Rectangle {
            id: tagBar
            width: parent.width
            height: 34
            radius: 7
            color: surface.appTheme.bgNode
            border.width: 1
            border.color: surface.appTheme.borderDefault
            clip: true

            Flickable {
                anchors.left: parent.left
                anchors.right: tagButton.left
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

                    Text {
                        anchors.verticalCenter: parent.verticalCenter
                        visible: surface.viewerController.tags.length === 0
                        text: "No tags"
                        color: surface.appTheme.textDim
                        font.family: "Segoe UI"
                        font.pointSize: 8
                    }

                    Repeater {
                        model: surface.viewerController.tags

                        Rectangle {
                            id: tagChip
                            required property var modelData
                            anchors.verticalCenter: parent.verticalCenter
                            width: Math.min(190, Math.max(46, chipLabel.implicitWidth + 28))
                            height: 22
                            radius: 6
                            color: surface.appTheme.whiteAlpha05
                            border.width: 1
                            border.color: tagChip.modelData.color

                            Rectangle {
                                width: 7
                                height: 7
                                radius: 4
                                anchors.left: parent.left
                                anchors.leftMargin: 7
                                anchors.verticalCenter: parent.verticalCenter
                                color: tagChip.modelData.color
                            }
                            Text {
                                id: chipLabel
                                anchors.left: parent.left
                                anchors.leftMargin: 18
                                anchors.right: parent.right
                                anchors.rightMargin: 6
                                anchors.verticalCenter: parent.verticalCenter
                                text: "@" + tagChip.modelData.name
                                color: surface.appTheme.textMain
                                elide: Text.ElideRight
                                font.family: "Segoe UI"
                                font.pointSize: 8
                            }
                        }
                    }
                }
            }

            MediaIconButton {
                id: tagButton
                width: 36
                height: 28
                anchors.right: parent.right
                anchors.rightMargin: 3
                anchors.verticalCenter: parent.verticalCenter
                appTheme: surface.appTheme
                iconSource: "../assets/icons/tag.svg"
                accessibleName: "Manage tags"
                onClicked: mediaTagPicker.openForNodeAt(
                    surface.viewerController.nodeId,
                    tagButton
                )
            }
        }

        Item {
            id: metadataBlock
            width: parent.width
            height: 34

            Text {
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.top: parent.top
                height: 16
                text: {
                    var meta = surface.viewerController.metadata
                    if (!meta) return ""
                    var values = []
                    if (meta.type) values.push(meta.type)
                    if (meta.size) values.push(meta.size)
                    if (meta.resolution) values.push(meta.resolution)
                    if (meta.duration) values.push(meta.duration)
                    return values.join("   |   ")
                }
                color: surface.appTheme.textMuted
                elide: Text.ElideRight
                verticalAlignment: Text.AlignVCenter
                font.family: "Segoe UI Semibold"
                font.pointSize: 8
            }

            Text {
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.bottom: parent.bottom
                height: 16
                text: {
                    var meta = surface.viewerController.metadata
                    if (!meta) return ""
                    return "Added: " + (meta.created || "-")
                           + "   |   Edited: " + (meta.updated || "-")
                }
                color: surface.appTheme.textMuted
                elide: Text.ElideRight
                verticalAlignment: Text.AlignVCenter
                font.family: "Segoe UI"
                font.pointSize: 8
            }
        }
    }

    Popup {
        id: descriptionGuard
        parent: surface
        anchors.centerIn: parent
        modal: false
        padding: 12
        focus: true
        closePolicy: Popup.NoAutoClose

        background: Rectangle {
            color: surface.appTheme.bgPanel
            border.width: 1
            border.color: surface.appTheme.borderDefault
            radius: 8
        }

        Column {
            width: Math.min(300, surface.width - 36)
            spacing: 9

            Text {
                width: parent.width
                text: "Save media description changes?"
                color: surface.appTheme.textMain
                font.family: surface.appTheme.textFontFamily
                font.pointSize: 10
                wrapMode: Text.WordWrap
            }

            Row {
                width: parent.width
                spacing: 6
                Button {
                    text: "Save"
                    focusPolicy: Qt.TabFocus
                    onClicked: surface.saveDescriptionAndContinue()
                }
                Button {
                    text: "Discard"
                    focusPolicy: Qt.TabFocus
                    onClicked: surface.discardDescriptionAndContinue()
                }
                Button {
                    text: "Continue editing"
                    focusPolicy: Qt.TabFocus
                    onClicked: surface.cancelDescriptionGuard()
                }
            }
        }
    }

    TagPicker {
        id: mediaTagPicker
        canvasController: surface.canvasController
        appTheme: surface.appTheme
        onTagsChanged: surface.viewerController.notify_tags_changed_for(
            mediaTagPicker.nodeId
        )
    }

    Connections {
        target: surface.viewerController

        function onSessionChanged() {
            surface.syncTitleForSession()
            surface.syncDescriptionForSession()
            surface.syncVideoOutput()
        }

        function onTitleChanged() {
            surface.syncTitleForSession()
        }

        function onImageStateChanged() {
            surface.syncImageState()
        }

        function onPlaybackChanged() {
            surface.syncVideoOutput()
        }

        function onActiveChanged() {
            surface.syncTitleForSession()
            surface.syncVideoOutput()
        }

        function onTagsEdited(nodeId) {
            if (nodeId > 0 && mediaTagPicker.visible)
                mediaTagPicker.refresh()
        }
    }
}
