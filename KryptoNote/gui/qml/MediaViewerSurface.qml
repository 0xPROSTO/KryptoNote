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
    readonly property bool descriptionVisible: !surface.expanded
                                               && viewerController.active
                                               && (viewerController.mediaType === "image"
                                                   || viewerController.mediaType === "video"
                                                   || viewerController.mediaType === "audio")
    readonly property bool compactToolbar: width < 720
    readonly property bool ultraCompactToolbar: width < 480
    readonly property real minimumImageZoom: 0.10
    readonly property real maximumImageZoom: 8.0
    readonly property real descriptionSplitRatio: {
        var available = Math.max(1, splitAvailableHeight)
        var requested = Number(viewerController.descriptionSplitRatio) || 0.20
        var minimumEditorRatio = descriptionVisible
                                   ? Math.min(0.90, 70 / available) : 0.10
        var maximumEditorRatio = descriptionVisible
                                  ? Math.max(0.10, 1 - 72 / available) : 0.90
        var lower = Math.max(0.10, minimumEditorRatio)
        var upper = Math.min(0.90, maximumEditorRatio)
        if (upper < lower) upper = lower
        return Math.max(0.10, Math.min(0.90, Math.max(
            lower, Math.min(upper, requested)
        )))
    }
    readonly property real descriptionDividerHeight: descriptionVisible ? 12 : 0
    readonly property real splitAvailableHeight: Math.max(
        0,
        mediaDescriptionRegion.height
        - unifiedActionBar.height
        - descriptionDividerHeight
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

    function fitImageZoom() {
        var baseWidth = mediaImage.implicitWidth
        var baseHeight = mediaImage.implicitHeight
        if (baseWidth <= 0 || baseHeight <= 0) return 1.0
        var quarterTurn = imageRotation % 180 !== 0
        var rotatedWidth = quarterTurn ? baseHeight : baseWidth
        var rotatedHeight = quarterTurn ? baseWidth : baseHeight
        return Math.min(maximumImageZoom, Math.min(
            Math.max(1, imageViewport.width - 28) / rotatedWidth,
            Math.max(1, imageViewport.height - 28) / rotatedHeight
        ))
    }

    function effectiveImageZoom() {
        if (imageFit) return fitImageZoom()
        return Math.max(minimumImageZoom, Math.min(maximumImageZoom, imageZoom))
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

    function maximumImagePanX(zoom) {
        return Math.max(0, (rotatedImageWidth(zoom) - imageViewport.width) / 2)
    }

    function maximumImagePanY(zoom) {
        return Math.max(0, (rotatedImageHeight(zoom) - imageViewport.height) / 2)
    }

    function imageCanPan() {
        var zoom = effectiveImageZoom()
        return maximumImagePanX(zoom) > 0.5 || maximumImagePanY(zoom) > 0.5
    }

    function setImagePanPixels(panPixelsX, panPixelsY, zoom) {
        var normalizedZoom = Math.max(minimumImageZoom, Number(zoom) || 1.0)
        var boundedX = Math.max(
            -maximumImagePanX(normalizedZoom),
            Math.min(maximumImagePanX(normalizedZoom), panPixelsX)
        )
        var boundedY = Math.max(
            -maximumImagePanY(normalizedZoom),
            Math.min(maximumImagePanY(normalizedZoom), panPixelsY)
        )
        imagePanX = boundedX / Math.max(1, rotatedImageWidth(normalizedZoom))
        imagePanY = boundedY / Math.max(1, rotatedImageHeight(normalizedZoom))
    }

    function clampImagePan() {
        var zoom = effectiveImageZoom()
        setImagePanPixels(imagePanPixelsX(), imagePanPixelsY(), zoom)
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
        var nextRotation = Number(state.rotation)
        var nextZoom = Number(state.zoom)
        var nextPanX = Number(state.panX)
        var nextPanY = Number(state.panY)
        imageRotation = isFinite(nextRotation) ? nextRotation : 0
        imageZoom = isFinite(nextZoom) ? nextZoom : 1.0
        imagePanX = isFinite(nextPanX) ? nextPanX : 0.0
        imagePanY = isFinite(nextPanY) ? nextPanY : 0.0
        imageFit = state.fit === undefined ? true : Boolean(state.fit)
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
        var nextZoom = Math.max(
            minimumImageZoom,
            Math.min(maximumImageZoom, oldZoom * factor)
        )
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
        setImagePanPixels(nextPanPixelsX, nextPanPixelsY, nextZoom)
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
            setImagePanPixels(
                oldPanPixelsX,
                oldPanPixelsY,
                effectiveImageZoom()
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
        if (!surface.viewerController) return
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
    Component.onDestruction: {
        if (surface.viewerController)
            surface.viewerController.detach_video_output(videoOutput)
    }
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
        spacing: 6

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

        Item {
            id: mediaDescriptionRegion
            objectName: "mediaDescriptionRegion"
            width: parent.width
            height: Math.max(
                0,
                surfaceColumn.height - header.height - surfaceColumn.spacing
            )

            Rectangle {
                anchors.fill: parent
                radius: 8
                color: surface.appTheme.bgNode
                border.width: 1
                border.color: surface.appTheme.borderDefault
            }

            Rectangle {
                id: imageViewport
                objectName: "mediaViewport"
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.top: parent.top
                anchors.leftMargin: 1
                anchors.rightMargin: 1
                anchors.topMargin: 1
                anchors.bottom: surface.descriptionVisible
                                ? descriptionDivider.top : unifiedActionBar.top
                color: "transparent"
                clip: true

                onWidthChanged: if (!surface.imageFit)
                                    Qt.callLater(surface.clampImagePan)
                onHeightChanged: if (!surface.imageFit)
                                     Qt.callLater(surface.clampImagePan)

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
                playing: surface.playbackForCurrentNode
                         && surface.viewerController.playing
                playbackDuration: surface.viewerController.duration
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
                objectName: "audioWaveformUnavailable"
                visible: surface.viewerController.mediaType === "audio"
                         && (surface.viewerController.audioWaveform.length === 0
                         || surface.viewerController.duration <= 0
                         )
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
                cursorShape: surface.imageCanPan()
                             ? (pressed ? Qt.ClosedHandCursor : Qt.OpenHandCursor)
                             : Qt.ArrowCursor
                preventStealing: true
                property real pressX: 0
                property real pressY: 0
                property real startPanPixelsX: 0
                property real startPanPixelsY: 0

                onPressed: function(mouse) {
                    viewportFocus.forceActiveFocus()
                    pressX = mouse.x
                    pressY = mouse.y
                    startPanPixelsX = surface.imagePanPixelsX()
                    startPanPixelsY = surface.imagePanPixelsY()
                    mouse.accepted = true
                }
                onPositionChanged: function(mouse) {
                    if (!(mouse.buttons & Qt.LeftButton)) return
                    surface.setImagePanPixels(
                        startPanPixelsX + mouse.x - pressX,
                        startPanPixelsY + mouse.y - pressY,
                        surface.effectiveImageZoom()
                    )
                }
                onReleased: surface.publishImageState()
                onCanceled: surface.publishImageState()
                onDoubleClicked: {
                    if (surface.imageFit) surface.setActualSize()
                    else surface.setFit()
                }
            }

            WheelHandler {
                target: null
                enabled: imageGestures.enabled
                orientation: Qt.Vertical
                acceptedDevices: PointerDevice.Mouse | PointerDevice.TouchPad
                onWheel: function(event) {
                    var delta = event.angleDelta.y
                    if (delta === 0) delta = event.pixelDelta.y
                    if (delta === 0) return
                    var factor = Math.pow(1.25, delta / 120)
                    factor = Math.max(0.64, Math.min(1.5625, factor))
                    surface.zoomAt(event.x, event.y, factor)
                    event.accepted = true
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
                id: descriptionDivider
                objectName: "mediaDescriptionDivider"
                width: parent.width
                height: surface.descriptionDividerHeight
                visible: surface.descriptionVisible
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.bottom: descriptionSplit.top
                z: 4
                focus: true

                Rectangle {
                    id: dividerLine
                    objectName: "mediaDescriptionDividerLine"
                    anchors.centerIn: parent
                    width: parent.width
                    height: 1
                    color: dividerMouse.pressed || dividerMouse.containsMouse
                           ? surface.appTheme.accentMain
                           : surface.appTheme.borderDefault
                    opacity: dividerMouse.pressed || dividerMouse.containsMouse
                             ? 0.95 : 0.7
                }

                MouseArea {
                    id: dividerMouse
                    anchors.fill: parent
                    hoverEnabled: true
                    preventStealing: true
                    acceptedButtons: Qt.LeftButton
                    cursorShape: Qt.SizeVerCursor

                    onPressed: function(mouse) {
                        mouse.accepted = true
                        descriptionDivider.forceActiveFocus()
                    }

                    onPositionChanged: function(mouse) {
                        mouse.accepted = true
                        if (!pressed) return
                        var regionY = dividerMouse.mapToItem(
                            mediaDescriptionRegion, mouse.x, mouse.y
                        ).y
                        var availableHeight = surface.splitAvailableHeight
                        if (availableHeight <= 0) return
                        // Moving the divider down gives the editor less room.
                        var nextRatio = (
                            unifiedActionBar.y - regionY
                            - descriptionDivider.height / 2
                        ) / availableHeight
                        surface.viewerController.set_description_split_ratio(
                            nextRatio
                        )
                    }

                    onReleased: function(mouse) { mouse.accepted = true }
                    onCanceled: { }
                }
            }

            Item {
                id: descriptionSplit
                objectName: "mediaDescriptionEditor"
                width: parent.width
                visible: surface.descriptionVisible
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.bottom: unifiedActionBar.top
                height: visible
                        ? Math.max(0, surface.splitAvailableHeight
                                   * surface.descriptionSplitRatio)
                        : 0

                Item {
                    id: descriptionToolbar
                    objectName: "mediaDescriptionToolbar"
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.top: parent.top
                    anchors.leftMargin: 8
                    anchors.rightMargin: 8
                    anchors.topMargin: 3
                    height: 30

                    Text {
                        anchors.left: parent.left
                        anchors.verticalCenter: parent.verticalCenter
                        visible: parent.width > 360
                        text: "Description"
                        color: surface.appTheme.textDim
                        font.family: "Segoe UI Semibold"
                        font.pointSize: 8
                    }

                    EditorFontSizeCombo {
                        id: descriptionSizeCombo
                        objectName: "mediaDescriptionFontSize"
                        anchors.right: parent.right
                        anchors.verticalCenter: parent.verticalCenter
                        appTheme: surface.appTheme
                        fontSizes: surface.descriptionFontSizes
                        reveal: true
                        currentIndex: surface.descriptionSizeIndex(
                            surface.viewerController.descriptionTextSize
                        )
                        Accessible.name: "Description text size"
                        onActivated: surface.viewerController.set_description_draft(
                            descriptionEditor.text, Number(currentText)
                        )
                    }
                }

                ScrollView {
                    id: descriptionScroll
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.top: descriptionToolbar.bottom
                    anchors.bottom: parent.bottom
                    anchors.leftMargin: 8
                    anchors.rightMargin: 8
                    anchors.topMargin: 1
                    anchors.bottomMargin: 6
                    clip: true
                    ScrollBar.horizontal.policy: ScrollBar.AlwaysOff
                    ScrollBar.vertical.policy:
                            descriptionEditor.contentHeight > descriptionScroll.height
                            ? ScrollBar.AsNeeded : ScrollBar.AlwaysOff
                    ScrollBar.vertical.contentItem: Rectangle {
                        implicitWidth: 4
                        radius: 2
                        color: surface.appTheme.borderHover
                    }
                    ScrollBar.vertical.background: Rectangle {
                        color: "transparent"
                    }

                    TextArea {
                        id: descriptionEditor
                        objectName: "mediaDescriptionTextEditor"
                        width: descriptionScroll.availableWidth
                        implicitHeight: contentHeight + topPadding + bottomPadding
                        text: ""
                        placeholderText: "Add a description..."
                        color: surface.appTheme.textMain
                        placeholderTextColor: surface.appTheme.textDim
                        selectionColor: surface.appTheme.accentMain
                        selectedTextColor: surface.appTheme.bgPanel
                        font.family: surface.appTheme.textFontFamily
                        font.pointSize: Math.max(
                            8, Number(surface.viewerController.descriptionTextSize) || 10
                        )
                        wrapMode: TextEdit.WrapAtWordBoundaryOrAnywhere
                        textFormat: TextEdit.PlainText
                        background: Item {}
                        selectByMouse: true
                        focusPolicy: Qt.TabFocus
                        Accessible.name: "Media description"
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
                }
            }

            Rectangle {
                id: unifiedActionBar
                objectName: "mediaUnifiedActionBar"
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.bottom: parent.bottom
                anchors.leftMargin: 1
                anchors.rightMargin: 1
                anchors.bottomMargin: 1
                height: 40
                radius: 7
                color: surface.appTheme.bgPanel

                // Rectangle has a single radius value. Cover only its top
                // corners so the footer stays square at the divider while its
                // bottom corners follow the enclosing panel.
                Rectangle {
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.top: parent.top
                    height: parent.radius
                    color: parent.color
                }

                Rectangle {
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.top: parent.top
                    height: 1
                    color: surface.appTheme.borderDefault
                }

                Item {
                    id: descriptionActions
                    objectName: "mediaDescriptionActions"
                    anchors.left: parent.left
                    anchors.leftMargin: 5
                    anchors.verticalCenter: parent.verticalCenter
                    width: surface.viewerController.descriptionDirty
                           ? descriptionActionRow.implicitWidth : 0
                    height: 30
                    opacity: surface.viewerController.descriptionDirty ? 1 : 0
                    enabled: surface.viewerController.descriptionDirty
                    clip: true

                    Behavior on width {
                        NumberAnimation {
                            duration: 170
                            easing.type: Easing.OutCubic
                        }
                    }
                    Behavior on opacity {
                        NumberAnimation {
                            duration: 120
                            easing.type: Easing.OutCubic
                        }
                    }

                    Row {
                        id: descriptionActionRow
                        anchors.fill: parent
                        spacing: 4

                        EditorActionButton {
                            width: surface.compactToolbar ? 34 : 78
                            height: 30
                            compact: surface.compactToolbar
                            appTheme: surface.appTheme
                            iconSource: "../assets/icons/save.svg"
                            text: "Save"
                            confirm: true
                            toolTipText: "Save description: Ctrl+S"
                            onClicked: surface.viewerController.save_description()
                        }

                        EditorActionButton {
                            width: surface.compactToolbar ? 34 : 78
                            height: 30
                            compact: surface.compactToolbar
                            appTheme: surface.appTheme
                            iconSource: "../assets/icons/close.svg"
                            text: "Cancel"
                            toolTipText: "Discard description changes"
                            onClicked: surface.viewerController.discard_description()
                        }
                    }
                }

                Item {
                    id: centerControls
                    anchors.left: descriptionActions.right
                    anchors.right: tagButton.left
                    anchors.top: parent.top
                    anchors.bottom: parent.bottom
                    anchors.leftMargin: 6
                    anchors.rightMargin: 6

                    Row {
                        id: imageControlRow
                        width: implicitWidth
                        height: implicitHeight
                        x: (unifiedActionBar.width - width) / 2
                           - centerControls.x
                        y: (centerControls.height - height) / 2
                        spacing: 2
                        visible: surface.viewerController.mediaType === "image"

                        MediaIconButton {
                            objectName: "rotateImageLeft"
                            appTheme: surface.appTheme
                            iconSource: "../assets/icons/rotate-left.svg"
                            accessibleName: "Rotate 90 degrees counterclockwise"
                            enabled: mediaImage.status === Image.Ready
                            onClicked: surface.rotateImage(-90)
                        }
                        MediaIconButton {
                            objectName: "rotateImageRight"
                            appTheme: surface.appTheme
                            iconSource: "../assets/icons/rotate-right.svg"
                            accessibleName: "Rotate 90 degrees clockwise"
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
                                1 / 1.25
                            )
                        }
                        Text {
                            width: surface.ultraCompactToolbar ? 38 : 44
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
                                1.25
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
                            accessibleName: "Preview at 100 percent"
                            enabled: mediaImage.status === Image.Ready
                            visible: !surface.ultraCompactToolbar
                            onClicked: surface.setActualSize()
                        }
                    }

                    RowLayout {
                        anchors.fill: parent
                        spacing: 5
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
                            Layout.minimumWidth: 48
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
                                x: audioSeekSlider.leftPadding
                                   + audioSeekSlider.visualPosition
                                   * (audioSeekSlider.availableWidth - width)
                                y: audioSeekSlider.topPadding
                                   + audioSeekSlider.availableHeight / 2 - height / 2
                                width: 12
                                height: 12
                                radius: 6
                                color: audioSeekSlider.visualFocus
                                       ? surface.appTheme.accentMain
                                       : surface.appTheme.sliderHandle
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
                            visible: centerControls.width > 270
                            text: surface.formatTime(surface.playbackForCurrentNode
                                                     ? surface.viewerController.position : 0)
                                  + " / " + surface.formatTime(
                                      surface.playbackForCurrentNode
                                      ? surface.viewerController.duration : 0
                                  )
                            color: surface.appTheme.textMuted
                            horizontalAlignment: Text.AlignRight
                            font.family: "Segoe UI"
                            font.pointSize: 8
                        }
                    }

                    RowLayout {
                        anchors.fill: parent
                        spacing: 5
                        visible: surface.viewerController.mediaType === "video"

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
                            Layout.minimumWidth: 48
                            Layout.preferredHeight: 30
                            from: 0
                            to: Math.max(1, surface.viewerController.duration)
                            stepSize: 5000
                            focusPolicy: Qt.TabFocus
                            Accessible.name: "Video position"
                            onPressedChanged: {
                                if (pressed) surface.viewerController.begin_seek()
                                else {
                                    surface.viewerController.seek(value)
                                    surface.viewerController.end_seek()
                                }
                            }
                            onMoved: surface.viewerController.seek(value)
                            background: Rectangle {
                                x: seekSlider.leftPadding
                                y: seekSlider.topPadding
                                   + seekSlider.availableHeight / 2 - height / 2
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
                                y: seekSlider.topPadding
                                   + seekSlider.availableHeight / 2 - height / 2
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
                            Layout.preferredWidth: 88
                            visible: centerControls.width > 310
                            text: surface.formatTime(surface.playbackForCurrentNode
                                                     ? surface.viewerController.position : 0)
                                  + " / " + surface.formatTime(
                                      surface.playbackForCurrentNode
                                      ? surface.viewerController.duration : 0
                                  )
                            color: surface.appTheme.textMuted
                            horizontalAlignment: Text.AlignRight
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
                            visible: centerControls.width > 220
                            onClicked: surface.viewerController.toggle_mute()
                        }

                        Slider {
                            id: wideVolumeSlider
                            Layout.preferredWidth: 74
                            Layout.preferredHeight: 30
                            visible: centerControls.width > 500
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
                                x: wideVolumeSlider.leftPadding
                                   + wideVolumeSlider.visualPosition
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
                }

                EditorActionButton {
                    id: tagButton
                    anchors.right: parent.right
                    anchors.rightMargin: 5
                    anchors.verticalCenter: parent.verticalCenter
                    width: surface.compactToolbar ? 34 : 88
                    height: 30
                    compact: surface.compactToolbar
                    appTheme: surface.appTheme
                    iconSource: "../assets/icons/tag.svg"
                    text: surface.viewerController.tags.length > 0
                          ? "Tags · " + surface.viewerController.tags.length : "Tags"
                    toolTipText: surface.viewerController.tags.length > 0
                                 ? "Manage " + surface.viewerController.tags.length + " tags"
                                 : "Add tags"
                    enabled: surface.viewerController.active
                    onClicked: mediaTagPicker.openForNodeAt(
                        surface.viewerController.nodeId,
                        tagButton
                    )
                }
            }

        }

    }

    Popup {
        id: descriptionGuard
        parent: surface
        anchors.centerIn: parent
        modal: true
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
                id: descriptionGuardActions
                width: parent.width
                spacing: 6
                EditorActionButton {
                    width: Math.max(72, (descriptionGuardActions.width
                                          - descriptionGuardActions.spacing * 2) / 3)
                    height: 30
                    appTheme: surface.appTheme
                    iconSource: "../assets/icons/save.svg"
                    text: "Save"
                    confirm: true
                    toolTipText: "Save description"
                    onClicked: surface.saveDescriptionAndContinue()
                }
                EditorActionButton {
                    width: Math.max(72, (descriptionGuardActions.width
                                          - descriptionGuardActions.spacing * 2) / 3)
                    height: 30
                    appTheme: surface.appTheme
                    iconSource: "../assets/icons/close.svg"
                    text: "Discard"
                    destructive: true
                    toolTipText: "Discard description changes"
                    onClicked: surface.discardDescriptionAndContinue()
                }
                EditorActionButton {
                    width: Math.max(72, (descriptionGuardActions.width
                                          - descriptionGuardActions.spacing * 2) / 3)
                    height: 30
                    appTheme: surface.appTheme
                    iconSource: "../assets/icons/close.svg"
                    text: "Continue"
                    Accessible.name: "Continue editing"
                    toolTipText: "Continue editing"
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
