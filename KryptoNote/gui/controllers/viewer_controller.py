import concurrent.futures
import logging
import re
import threading

from PySide6.QtCore import QObject, Property, QUrl, Signal, Slot
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer

from ...core.database.connection import DatabaseConnection
from ...core.database.repository import NodeRepository
from ...core.constants import MEDIA_NODE_TYPES, PLAYABLE_NODE_TYPES
from ...services.node_service import NodeService


logger = logging.getLogger(__name__)


def _decode_image_preview(db_path, crypto, node_id):
    """Decode through a thread-local read-only repository."""
    database = DatabaseConnection(
        db_path,
        initialize=False,
        must_exist=True,
        writable=False,
        configure_wal=False,
    )
    repository = None
    try:
        repository = NodeRepository(database, crypto)
        return NodeService(repository).read_image_preview(node_id, (4096, 4096))
    finally:
        if repository is not None:
            repository.close(wait=False)
        database.close()


class ViewerController(QObject):
    """Own the active image/video session shared by every QML surface."""

    activeChanged = Signal()
    detachedChanged = Signal()
    sessionChanged = Signal()
    titleChanged = Signal()
    tagsChanged = Signal()
    playbackChanged = Signal()
    imageStateChanged = Signal()

    sessionOpened = Signal(int)
    sessionClosed = Signal()
    detachRequested = Signal()
    attachRequested = Signal()
    tagsEdited = Signal(int)
    _previewCompleted = Signal(int, object, str)

    def __init__(
        self,
        node_model,
        canvas_controller,
        service,
        preview_provider,
        parent=None,
        *,
        player=None,
        audio=None,
        executor=None,
    ):
        super().__init__(parent)
        self._node_model = node_model
        self._canvas_controller = canvas_controller
        self._service = service
        self._preview_provider = preview_provider

        self._active = False
        self._detached = False
        self._node_id = 0
        self._media_type = ""
        self._title = ""
        self._tags = []
        self._metadata = {}
        self._audio_waveform = []
        self._media_aspect_ratio = 1.0
        self._loading = False
        self._error_text = ""
        self._image_revision = preview_provider.revision
        self._image_state = {
            "rotation": 0,
            "zoom": 1.0,
            "panX": 0.0,
            "panY": 0.0,
            "fit": True,
        }

        self._playing = False
        self._position = 0
        self._duration = 0
        self._volume = 10
        self._muted = False
        self._resume_after_seek = False
        self._stream = None
        self._playback_node_id = 0
        self._playback_media_type = ""
        self._playback_generation = 0
        self._playback_sequence = 0
        self._video_output = None
        self._generation = 0
        self._shutting_down = False
        self._resetting_player = False
        self._player_signal_connections = []
        self._preview_futures = set()
        self._preview_futures_lock = threading.Lock()
        self._description_saved = ""
        self._description_draft = ""
        self._description_dirty = False
        self._description_text_size = 10
        self._description_saved_text_size = 10
        self._description_split_ratio = 0.20
        self._description_split_manual = False

        self._player = player or QMediaPlayer(self)
        self._audio = audio or QAudioOutput(self)
        self._owns_executor = executor is None
        self._executor = executor or concurrent.futures.ThreadPoolExecutor(
            max_workers=2,
            thread_name_prefix="media-preview",
        )

        self._configure_player()
        self._previewCompleted.connect(self._on_preview_completed)
        self._node_model.dataChanged.connect(self._on_model_data_changed)
        self._node_model.rowsRemoved.connect(self._ensure_active_node_exists)
        self._node_model.modelReset.connect(self._ensure_active_node_exists)

    def _configure_player(self):
        self._audio.setVolume(self._volume / 100.0)
        self._audio.setMuted(False)
        self._player.setAudioOutput(self._audio)

    def _connect_player_signals(self, generation):
        self._disconnect_player_signals()
        connections = (
            (
                self._player.positionChanged,
                lambda position, current=generation: self._on_position_changed(
                    current, position
                ),
            ),
            (
                self._player.durationChanged,
                lambda duration, current=generation: self._on_duration_changed(
                    current, duration
                ),
            ),
            (
                self._player.playbackStateChanged,
                lambda state, current=generation: self._on_playback_state_changed(
                    current, state
                ),
            ),
            (
                self._player.mediaStatusChanged,
                lambda status, current=generation: self._on_media_status_changed(
                    current, status
                ),
            ),
            (
                self._player.errorOccurred,
                lambda error, error_string="", current=generation: self._on_player_error(
                    current, error, error_string
                ),
            ),
        )
        for signal, callback in connections:
            signal.connect(callback)
        self._player_signal_connections = list(connections)

    def _disconnect_player_signals(self):
        for signal, callback in self._player_signal_connections:
            try:
                signal.disconnect(callback)
            except (RuntimeError, TypeError):
                pass
        self._player_signal_connections = []

    active = Property(bool, lambda self: self._active, notify=activeChanged)
    detached = Property(bool, lambda self: self._detached, notify=detachedChanged)
    nodeId = Property(int, lambda self: self._node_id, notify=sessionChanged)
    mediaType = Property(str, lambda self: self._media_type, notify=sessionChanged)
    mediaAspectRatio = Property(
        float,
        lambda self: self._media_aspect_ratio,
        notify=sessionChanged,
    )
    title = Property(str, lambda self: self._title, notify=titleChanged)
    tags = Property(object, lambda self: list(self._tags), notify=tagsChanged)
    metadata = Property(object, lambda self: dict(self._metadata), notify=sessionChanged)
    loading = Property(bool, lambda self: self._loading, notify=sessionChanged)
    errorText = Property(str, lambda self: self._error_text, notify=sessionChanged)
    imageRevision = Property(int, lambda self: self._image_revision, notify=sessionChanged)
    imageSource = Property(
        str,
        lambda self: (
            f"image://media-preview/current?revision={self._image_revision}"
            if self._active and self._media_type == "image" and not self._loading
            else ""
        ),
        notify=sessionChanged,
    )
    imageState = Property(object, lambda self: dict(self._image_state), notify=imageStateChanged)
    playing = Property(bool, lambda self: self._playing, notify=playbackChanged)
    position = Property(float, lambda self: float(self._position), notify=playbackChanged)
    duration = Property(float, lambda self: float(self._duration), notify=playbackChanged)
    volume = Property(int, lambda self: self._volume, notify=playbackChanged)
    muted = Property(bool, lambda self: self._muted, notify=playbackChanged)
    playbackNodeId = Property(int, lambda self: self._playback_node_id, notify=playbackChanged)
    audioWaveform = Property(
        "QVariantList",
        lambda self: list(self._audio_waveform),
        notify=sessionChanged,
    )
    descriptionDraft = Property(str, lambda self: self._description_draft, notify=sessionChanged)
    descriptionDirty = Property(bool, lambda self: self._description_dirty, notify=sessionChanged)
    descriptionTextSize = Property(int, lambda self: self._description_text_size, notify=sessionChanged)
    descriptionSplitRatio = Property(float, lambda self: self._description_split_ratio, notify=sessionChanged)

    @Slot(int)
    def open_media_viewer(self, node_id):
        self._open_media_viewer(node_id, announce=True)

    def _open_media_viewer(self, node_id, *, announce):
        node = self._node_model.get_node_data(node_id)
        if not node or node.get("type") not in MEDIA_NODE_TYPES:
            return

        if self._active and self._node_id == node_id and not self._error_text:
            return

        self._generation += 1
        generation = self._generation
        self._cancel_preview_requests()
        target_type = str(node.get("type"))
        same_audio_playback = (
            target_type == "audio"
            and self._playback_node_id == int(node_id)
            and self._playback_media_type == "audio"
        )
        preserve_audio_playback = (
            target_type == "image"
            and self._playback_node_id > 0
            and self._playback_media_type == "audio"
        )
        if same_audio_playback or preserve_audio_playback:
            self._image_revision = self._preview_provider.clear()
        else:
            self._dispose_backend(clear_preview=True)
        self._node_id = int(node_id)
        self._media_type = target_type
        self._loading = not same_audio_playback
        self._error_text = ""
        if not (same_audio_playback or preserve_audio_playback):
            self._position = 0
            self._duration = 0
            self._playing = False
        self._image_state = {
            "rotation": 0,
            "zoom": 1.0,
            "panX": 0.0,
            "panY": 0.0,
            "fit": True,
        }
        self._refresh_node_snapshot(node, force=True)
        if not self._active:
            self._active = True
            self.activeChanged.emit()
        self.sessionChanged.emit()
        self.playbackChanged.emit()
        self.imageStateChanged.emit()
        if announce:
            self.sessionOpened.emit(self._node_id)

        if self._media_type == "image":
            self._start_image_preview(generation)
        elif not same_audio_playback:
            self._start_media_stream(autoplay=self._media_type == "video")

    def _start_image_preview(self, generation):
        db_path = self._service.get_db_path()
        if not db_path or db_path == ":memory:":
            try:
                image = self._service.read_image_preview(self._node_id, (4096, 4096))
                self._previewCompleted.emit(generation, image, "")
            except Exception as exc:
                self._previewCompleted.emit(generation, None, str(exc))
            return

        try:
            crypto = self._service.create_crypto_clone()
            future = self._executor.submit(
                _decode_image_preview,
                db_path,
                crypto,
                self._node_id,
            )
        except Exception as exc:
            self._previewCompleted.emit(generation, None, str(exc))
            return

        def completed(result_future):
            try:
                if result_future.cancelled():
                    return
                image = result_future.result()
                error = ""
            except Exception as exc:  # pragma: no cover - exercised via signal result
                image = None
                error = str(exc)
            finally:
                with self._preview_futures_lock:
                    self._preview_futures.discard(result_future)
            if not self._shutting_down:
                self._previewCompleted.emit(generation, image, error)

        with self._preview_futures_lock:
            self._preview_futures.add(future)
        future.add_done_callback(completed)

    def _cancel_preview_requests(self):
        with self._preview_futures_lock:
            futures = tuple(self._preview_futures)
        for future in futures:
            future.cancel()

    @Slot(int, object, str)
    def _on_preview_completed(self, generation, image, error):
        if (
            self._shutting_down
            or generation != self._generation
            or not self._active
            or self._media_type != "image"
        ):
            return
        self._loading = False
        self._error_text = error.strip()
        if not self._error_text and image is not None and not image.isNull():
            if image.width() > 0 and image.height() > 0:
                self._media_aspect_ratio = image.width() / image.height()
                if not self._description_split_manual:
                    ratio = max(
                        0.0,
                        min(
                            1.0,
                            (self._media_aspect_ratio - 1.0)
                            / (16.0 / 9.0 - 1.0),
                        ),
                    )
                    self._description_split_ratio = 0.20 + 0.15 * ratio
                self._image_revision = self._preview_provider.set_image(image)
        elif not self._error_text:
            self._error_text = "Unable to decode this image."
        self.sessionChanged.emit()

    def _next_playback_generation(self):
        self._playback_sequence += 1
        return self._playback_sequence

    def _playback_belongs_to_viewer(self):
        return bool(
            self._active
            and self._playback_node_id == self._node_id
            and self._playback_media_type == self._media_type
        )

    def _start_media_stream(self, *, autoplay=False):
        try:
            node = self._node_model.get_node_data(self._node_id) or {}
            info = self._service.get_item_info(self._node_id)
            if not info or not info.is_chunked:
                raise ValueError("Unable to open this media.")
            self._stream = self._service.open_item_stream(self._node_id)
            self._playback_node_id = self._node_id
            self._playback_media_type = self._media_type
            playback_generation = self._next_playback_generation()
            self._playback_generation = playback_generation
            self._connect_player_signals(playback_generation)
            suffix = self._safe_source_suffix(
                getattr(info, "original_filename", ""),
                self._media_type
            )
            self._player.setSourceDevice(self._stream, QUrl("secure" + suffix))
            if self._video_output is not None and self._media_type == "video":
                self._player.setVideoOutput(self._video_output)
            self.playbackChanged.emit()
            if autoplay:
                self._player.play()
        except Exception as exc:
            self._set_session_error(
                str(exc) or "Unable to open this media.",
                dispose_backend=True,
            )

    @staticmethod
    def _safe_source_suffix(filename, media_type):
        suffix = ""
        if filename:
            match = re.search(r"(\.[A-Za-z0-9]{1,10})$", str(filename))
            if match:
                suffix = match.group(1).lower()
        if not suffix:
            suffix = ".mp4" if media_type == "video" else ".ogg"
        return suffix

    def _start_playback_for_node(self, node_id, *, autoplay=True):
        node = self._node_model.get_node_data(int(node_id))
        if not node or node.get("type") not in PLAYABLE_NODE_TYPES:
            return False
        self._dispose_playback()
        playback_generation = self._next_playback_generation()
        try:
            info = self._service.get_item_info(int(node_id))
            if not info or not info.is_chunked:
                raise ValueError("Unable to open this media.")
            stream = self._service.open_item_stream(int(node_id))
            self._stream = stream
            self._playback_node_id = int(node_id)
            self._playback_media_type = str(node.get("type"))
            self._playback_generation = playback_generation
            self._position = 0
            self._duration = int(float(node.get("media_duration") or 0) * 1000)
            self._playing = False
            self._connect_player_signals(playback_generation)
            suffix = self._safe_source_suffix(
                getattr(info, "original_filename", ""),
                self._playback_media_type
            )
            self._player.setSourceDevice(stream, QUrl("secure" + suffix))
            if (
                self._video_output is not None
                and self._playback_media_type == "video"
                and self._active
                and self._node_id == int(node_id)
            ):
                self._player.setVideoOutput(self._video_output)
            if autoplay:
                self._player.play()
            self.playbackChanged.emit()
            return True
        except Exception as exc:
            viewer_playback = self._playback_belongs_to_viewer()
            self._dispose_playback()
            message = str(exc) or "Unable to open this media."
            if viewer_playback:
                self._set_session_error(message, dispose_backend=False)
            else:
                self._canvas_controller.status_message.emit(
                    f"Playback failed: {message}", "error"
                )
            self.playbackChanged.emit()
            return False

    def _set_session_error(self, message, *, dispose_backend=False):
        if dispose_backend:
            self._dispose_backend(clear_preview=False)
        self._loading = False
        self._error_text = str(message).strip() or "Unable to open this media."
        self._playing = False
        self.sessionChanged.emit()
        self.playbackChanged.emit()

    @Slot()
    def close_viewer(self):
        if not self._active:
            return
        keep_audio_playback = (
            self._playback_node_id > 0
            and self._playback_media_type == "audio"
        )
        self._generation += 1
        self._cancel_preview_requests()
        if not keep_audio_playback:
            self._dispose_backend(clear_preview=True)
        else:
            self._video_output = None
        self._active = False
        self._node_id = 0
        self._media_type = ""
        self._title = ""
        self._tags = []
        self._metadata = {}
        self._audio_waveform = []
        self._description_saved = ""
        self._description_draft = ""
        self._description_dirty = False
        self._description_text_size = 10
        self._description_saved_text_size = 10
        self._loading = False
        self._error_text = ""
        if self._detached:
            self._detached = False
            self.detachedChanged.emit()
        self.activeChanged.emit()
        self.titleChanged.emit()
        self.tagsChanged.emit()
        self.sessionChanged.emit()
        self.playbackChanged.emit()
        self.sessionClosed.emit()

    @Slot()
    def retry(self):
        if not self._active or self._node_id <= 0:
            return
        self._open_media_viewer(self._node_id, announce=False)

    @Slot(str)
    @Slot(str, int)
    def set_description_draft(self, text, text_size=None):
        if not self._active or self._node_id <= 0:
            return
        self._description_draft = str(text or "")
        if text_size is not None:
            try:
                self._description_text_size = max(1, int(text_size))
            except (TypeError, ValueError):
                pass
        self._description_dirty = (
            self._description_draft != self._description_saved
            or self._description_text_size != self._description_saved_text_size
        )
        self.sessionChanged.emit()

    @Slot(result=bool)
    def save_description(self):
        if not self._active or self._node_id <= 0:
            return False
        try:
            self._service.update_media_description(
                self._node_id,
                self._description_draft,
                self._description_text_size,
            )
            self._node_model.update_media_description(
                self._node_id,
                self._description_draft,
                self._description_text_size,
            )
        except Exception as exc:
            self._canvas_controller.status_message.emit(
                f"Description save failed: {exc}", "error"
            )
            return False
        self._description_saved = self._description_draft
        self._description_saved_text_size = self._description_text_size
        self._description_dirty = False
        self.sessionChanged.emit()
        return True

    @Slot()
    def discard_description(self):
        self._description_draft = self._description_saved
        self._description_text_size = self._description_saved_text_size
        self._description_dirty = False
        self.sessionChanged.emit()

    @Slot(float)
    def set_description_split_ratio(self, ratio):
        try:
            value = float(ratio)
        except (TypeError, ValueError):
            return
        value = max(0.10, min(0.90, value))
        if abs(value - self._description_split_ratio) < 0.0001 and self._description_split_manual:
            return
        self._description_split_ratio = value
        self._description_split_manual = True
        self.sessionChanged.emit()

    @Slot(str, result=bool)
    def rename_current(self, title):
        if not self._active or self._node_id <= 0:
            return False
        normalized = str(title).strip()
        if normalized == self._title:
            return True
        try:
            self._service.update_item_title(self._node_id, normalized)
            self._node_model.update_title(self._node_id, normalized)
        except Exception as exc:
            self._canvas_controller.status_message.emit(
                f"Rename failed: {exc}", "error"
            )
            return False
        self._title = normalized
        self._refresh_node_snapshot(force=True)
        self.titleChanged.emit()
        self.sessionChanged.emit()
        return True

    @Slot()
    def export_current(self):
        if self._active and self._node_id > 0:
            self._canvas_controller.export_node_to_disk(self._node_id)

    @Slot()
    def notify_tags_changed(self):
        if not self._active:
            return
        self.notify_tags_changed_for(self._node_id)

    @Slot(int)
    def notify_tags_changed_for(self, node_id):
        node_id = int(node_id)
        if node_id <= 0:
            return
        if self._active and self._node_id == node_id:
            self._refresh_node_snapshot(force=True)
        self.tagsEdited.emit(node_id)

    @Slot(QObject)
    def attach_video_output(self, output):
        self._video_output = output
        if (
            self._active
            and self._media_type == "video"
            and self._playback_media_type == "video"
            and self._playback_node_id == self._node_id
        ):
            self._player.setVideoOutput(output)

    @Slot(QObject)
    def detach_video_output(self, output):
        if output is not self._video_output:
            return
        self._player.setVideoOutput(None)
        self._video_output = None

    @Slot()
    def toggle_playback(self):
        if not self._active or self._media_type not in PLAYABLE_NODE_TYPES or self._error_text:
            return
        self.toggle_playback_for(self._node_id)

    @Slot(int)
    def toggle_playback_for(self, node_id):
        node_id = int(node_id)
        if node_id <= 0:
            return
        if self._playback_node_id != node_id:
            self._start_playback_for_node(node_id, autoplay=True)
            return
        if self._playing:
            self._player.pause()
        else:
            self._player.play()

    @Slot(float)
    def seek(self, position):
        if self._active and self._media_type in PLAYABLE_NODE_TYPES:
            self.seek_for(self._node_id, position)

    @Slot(int, float)
    def seek_for(self, node_id, position):
        if int(node_id) != self._playback_node_id:
            return
        self._player.setPosition(max(0, min(int(position), self._duration or int(position))))

    @Slot()
    def begin_seek(self):
        self._resume_after_seek = self._playing
        if self._playing:
            self._player.pause()

    @Slot()
    def end_seek(self):
        should_resume = self._resume_after_seek
        self._resume_after_seek = False
        if should_resume and self._playback_node_id > 0 and not self._error_text:
            self._player.play()

    @Slot(int)
    def set_volume(self, value):
        value = max(0, min(100, int(value)))
        changed = value != self._volume
        self._volume = value
        self._audio.setVolume(value / 100.0)
        if value > 0 and self._muted:
            self._muted = False
            self._audio.setMuted(False)
            changed = True
        if changed:
            self.playbackChanged.emit()

    @Slot()
    def toggle_mute(self):
        self._muted = not self._muted
        self._audio.setMuted(self._muted)
        self.playbackChanged.emit()

    @Slot(int, float, float, float, bool)
    def set_image_view_state(self, rotation, zoom, pan_x, pan_y, fit):
        next_state = {
            "rotation": int(rotation) % 360,
            "zoom": max(0.1, min(8.0, float(zoom))),
            "panX": max(-8.0, min(8.0, float(pan_x))),
            "panY": max(-8.0, min(8.0, float(pan_y))),
            "fit": bool(fit),
        }
        if next_state != self._image_state:
            self._image_state = next_state
            self.imageStateChanged.emit()

    @Slot()
    def request_detach(self):
        if self._active and not self._detached:
            self.detachRequested.emit()

    @Slot()
    def request_attach(self):
        if self._active and self._detached:
            self.attachRequested.emit()

    @Slot(bool)
    def set_detached(self, detached):
        detached = bool(detached)
        if detached == self._detached:
            return
        self._detached = detached
        self.detachedChanged.emit()

    def _dispose_playback(self):
        self._disconnect_player_signals()
        self._resetting_player = True
        try:
            for description, reset in (
                ("stop media player", self._player.stop),
                ("detach video output", lambda: self._player.setVideoOutput(None)),
                ("clear media source", lambda: self._player.setSource(QUrl())),
            ):
                try:
                    reset()
                except Exception:
                    logger.exception("Unable to %s", description)
        finally:
            self._resetting_player = False
        self._video_output = None
        stream, self._stream = self._stream, None
        if stream is not None:
            try:
                stream.close()
            except Exception:
                logger.exception("Unable to close encrypted media stream")
        self._playing = False
        self._position = 0
        self._duration = 0
        self._resume_after_seek = False
        self._playback_node_id = 0
        self._playback_media_type = ""
        self._playback_generation = 0

    def _dispose_backend(self, clear_preview):
        self._dispose_playback()
        if clear_preview:
            self._image_revision = self._preview_provider.clear()

    def _refresh_node_snapshot(self, node=None, force=False):
        node = node or self._node_model.get_node_data(self._node_id)
        if not node:
            return
        title = node.get("title", "") or ""
        tags = [dict(tag) for tag in node.get("tags", [])]
        description = node.get("content", "") or ""
        node_text_size = max(1, int(node.get("text_size") or 10))
        waveform = list(node.get("audio_waveform", []) or [])
        media_width = int(node.get("media_width") or 0)
        media_height = int(node.get("media_height") or 0)
        self._media_aspect_ratio = (
            media_width / media_height
            if media_width > 0 and media_height > 0
            else (16.0 / 9.0 if node.get("type") == "video" else 1.0)
        )
        metadata = {
            "type": str(node.get("type", "")).upper(),
            "size": self._format_size(node.get("total_size", 0)),
            "resolution": (
                f"{media_width} × {media_height}"
                if media_width > 0 and media_height > 0
                else ""
            ),
            "duration": self._format_duration(node.get("media_duration", 0)),
            "created": node.get("created_at_display", "-") or "-",
            "updated": node.get("updated_at_display", "-") or "-",
        }
        title_changed = force or title != self._title
        tags_changed = force or tags != self._tags
        metadata_changed = force or metadata != self._metadata
        description_changed = force or description != self._description_saved
        text_size_changed = force or node_text_size != self._description_saved_text_size
        waveform_changed = force or waveform != self._audio_waveform
        self._title = title
        self._tags = tags
        self._metadata = metadata
        if not self._description_dirty:
            self._description_saved = description
            self._description_draft = description
            self._description_saved_text_size = node_text_size
            self._description_text_size = node_text_size
            self._description_dirty = False
        self._audio_waveform = waveform
        if not self._description_split_manual:
            if node.get("type") == "audio":
                self._description_split_ratio = 0.35
            else:
                ratio = max(0.0, min(1.0, (self._media_aspect_ratio - 1.0) / (16.0 / 9.0 - 1.0)))
                self._description_split_ratio = 0.20 + 0.15 * ratio
        if title_changed:
            self.titleChanged.emit()
        if tags_changed:
            self.tagsChanged.emit()
        if metadata_changed:
            self.sessionChanged.emit()
        if description_changed or text_size_changed or waveform_changed:
            self.sessionChanged.emit()

    def _on_model_data_changed(self, *_args):
        if self._active:
            self._refresh_node_snapshot()

    def _ensure_active_node_exists(self, *_args):
        if self._active and not self._node_model.get_node_data(self._node_id):
            self.close_viewer()
        if self._playback_node_id and not self._node_model.get_node_data(self._playback_node_id):
            self._dispose_backend(clear_preview=False)
            self.playbackChanged.emit()

    def _is_current_playback_session(self, generation):
        return (
            not self._shutting_down
            and generation == self._playback_generation
            and self._playback_node_id > 0
        )

    def _on_position_changed(self, generation, position):
        if not self._is_current_playback_session(generation):
            return
        self._position = int(position)
        self.playbackChanged.emit()

    def _on_duration_changed(self, generation, duration):
        if not self._is_current_playback_session(generation):
            return
        self._duration = max(0, int(duration))
        self.playbackChanged.emit()

    def _on_playback_state_changed(self, generation, state):
        if not self._is_current_playback_session(generation):
            return
        playing_state = getattr(QMediaPlayer.PlaybackState, "PlayingState", None)
        self._playing = state == playing_state
        self.playbackChanged.emit()

    def _on_media_status_changed(self, generation, status):
        if not self._is_current_playback_session(generation):
            return
        ready_statuses = {
            QMediaPlayer.MediaStatus.LoadedMedia,
            QMediaPlayer.MediaStatus.BufferedMedia,
            QMediaPlayer.MediaStatus.EndOfMedia,
        }
        if status in ready_statuses and self._active and self._loading:
            self._loading = False
            self.sessionChanged.emit()

    def _on_player_error(self, generation, error, error_string=""):
        if (
            self._resetting_player
            or error == QMediaPlayer.Error.NoError
            or not self._is_current_playback_session(generation)
        ):
            return
        message = error_string or self._player.errorString() or "Unable to play media."
        if self._playback_belongs_to_viewer():
            self._set_session_error(message, dispose_backend=True)
        else:
            self._dispose_playback()
            self._canvas_controller.status_message.emit(
                f"Playback failed: {message}", "error"
            )
            self.playbackChanged.emit()

    def shutdown(self):
        if self._shutting_down:
            return
        if self._active:
            self.close_viewer()
        self._shutting_down = True
        self._generation += 1
        self._cancel_preview_requests()
        if self._stream is not None or self._video_output is not None:
            self._dispose_backend(clear_preview=True)
        else:
            self._disconnect_player_signals()
        try:
            self._player.setAudioOutput(None)
        except Exception:
            pass
        if self._owns_executor:
            self._executor.shutdown(wait=True, cancel_futures=True)

    @staticmethod
    def _format_size(size):
        value = float(size or 0)
        if value <= 0:
            return ""
        units = ("B", "KB", "MB", "GB", "TB")
        unit = units[0]
        for unit in units:
            if value < 1024 or unit == units[-1]:
                break
            value /= 1024
        precision = 0 if unit == "B" else 1
        return f"{value:.{precision}f} {unit}"

    @staticmethod
    def _format_duration(seconds):
        total = max(0, int(float(seconds or 0)))
        if total <= 0:
            return ""
        hours, remainder = divmod(total, 3600)
        minutes, secs = divmod(remainder, 60)
        if hours:
            return f"{hours}:{minutes:02}:{secs:02}"
        return f"{minutes}:{secs:02}"
