from PySide6.QtCore import Qt, QUrl, QTimer
from PySide6.QtGui import QGuiApplication
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput, QMediaMetaData
from PySide6.QtMultimediaWidgets import QVideoWidget
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout
)

from .components.player_controls import PlayerControlsWidget
from ..theme.style_factory import StyleFactory
from ...core.io.stream import BlockEncryptedStream


class SecureVideoPlayer(QDialog):
    def __init__(self, repo, item_id, total_size, chunk_size, title="Secure Video"):
        super().__init__()
        self.setWindowTitle(title)
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowMinMaxButtonsHint)
        self.setStyleSheet(StyleFactory.get_player_qss())
        self.repo = repo
        self._has_resized = False

        self.CTRL_HEIGHT = 60

        screen = QGuiApplication.primaryScreen()
        screen_geom = screen.availableGeometry()

        limit_w = screen_geom.width() * 0.8
        limit_h = screen_geom.height() * 0.8

        aspect_ratio = 16.0 / 9.0
        target_w = limit_w
        target_h = target_w / aspect_ratio

        if target_h + self.CTRL_HEIGHT > limit_h:
            target_h = limit_h - self.CTRL_HEIGHT
            target_w = target_h * aspect_ratio

        x = screen_geom.x() + (screen_geom.width() - target_w) // 2
        y = screen_geom.y() + (screen_geom.height() - (target_h + self.CTRL_HEIGHT)) // 2
        self.setGeometry(int(x), int(y), int(target_w), int(target_h + self.CTRL_HEIGHT))

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.video_widget = QVideoWidget(self)
        self.video_widget.setAspectRatioMode(Qt.AspectRatioMode.KeepAspectRatio)
        layout.addWidget(self.video_widget, stretch=1)

        self.controls_widget = PlayerControlsWidget()
        layout.addWidget(self.controls_widget)

        self.player = QMediaPlayer(self)
        self.audio = QAudioOutput(self)
        self.player.setAudioOutput(self.audio)
        self.player.setVideoOutput(self.video_widget)
        self.audio.setVolume(self.controls_widget.get_current_volume() / 100.0)

        self.controls_widget.playToggled.connect(self.toggle_play)
        self.controls_widget.muteToggled.connect(self.toggle_mute)
        self.controls_widget.seekMoved.connect(self.set_position)
        self.controls_widget.seekPressed.connect(self.pause_on_seek)
        self.controls_widget.seekReleased.connect(self.play_on_seek)
        self.controls_widget.volumeChanged.connect(self.set_volume_from_slider)

        self.player.positionChanged.connect(self.position_changed)
        self.player.durationChanged.connect(self.duration_changed)
        self.player.metaDataChanged.connect(self._on_meta_data_changed)
        self.player.errorOccurred.connect(self.handle_errors)

        self.io_device = BlockEncryptedStream(
            self.repo.conn_manager.db_path,
            self.repo.crypto,
            item_id,
            total_size,
            chunk_size,
        )

        self.player.setSourceDevice(self.io_device, QUrl("secure.mp4"))

        QTimer.singleShot(100, self.start_playback)

    def _on_meta_data_changed(self):
        res = self.player.metaData().value(QMediaMetaData.Key.Resolution)
        if res and res.isValid() and not self._has_resized:
            self._has_resized = True

            screen = QGuiApplication.primaryScreen()
            screen_geom = screen.availableGeometry()

            limit_w = screen_geom.width() * 0.8
            limit_h = screen_geom.height() * 0.8

            img_w = res.width()
            img_h = res.height()

            if img_h == 0:
                return

            aspect_ratio = img_w / img_h

            if abs(aspect_ratio - (16.0 / 9.0)) > 0.01:
                target_w = img_w
                target_h = img_h

                if target_w > limit_w:
                    target_w = limit_w
                    target_h = target_w / aspect_ratio

                if target_h + self.CTRL_HEIGHT > limit_h:
                    target_h = limit_h - self.CTRL_HEIGHT
                    target_w = target_h * aspect_ratio

                x = screen_geom.x() + (screen_geom.width() - target_w) // 2
                y = screen_geom.y() + (screen_geom.height() - (target_h + self.CTRL_HEIGHT)) // 2

                self.setGeometry(int(x), int(y), int(target_w), int(target_h + self.CTRL_HEIGHT))

    def start_playback(self):
        self.player.play()
        self.controls_widget.set_playing_state(True)

    def toggle_play(self):
        if self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.player.pause()
            self.controls_widget.set_playing_state(False)
        else:
            self.player.play()
            self.controls_widget.set_playing_state(True)

    def toggle_mute(self):
        is_muted = not self.controls_widget._is_muted
        if is_muted:
            self.audio.setVolume(0.0)
        else:
            self.audio.setVolume(self.controls_widget.get_current_volume() / 100.0)
        self.controls_widget.set_muted_state(is_muted)

    def set_volume_from_slider(self, value):
        if self.controls_widget._is_muted and value > 0:
            self.controls_widget.set_muted_state(False)

        if value == 0:
            self.controls_widget.set_muted_state(True)
            self.audio.setVolume(0.0)
        else:
            self.audio.setVolume(value / 100.0)

    def position_changed(self, position):
        self.controls_widget.update_position(position)
        self.controls_widget.set_time(position, self.player.duration())

    def duration_changed(self, duration):
        self.controls_widget.update_duration(duration)
        self.controls_widget.set_time(self.player.position(), duration)

    def set_position(self, position):
        self.player.setPosition(position)

    def pause_on_seek(self):
        self.player.pause()

    def play_on_seek(self):
        self.player.play()
        if self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.controls_widget.set_playing_state(True)
        else:
            self.controls_widget.set_playing_state(False)

    def handle_errors(self):
        self.controls_widget.btn_play.setEnabled(False)
        self.controls_widget.lbl_time.setText("Error")
        print(self.player.errorString())

    def closeEvent(self, event):
        self.player.stop()
        self.player.setSource(QUrl())
        self.io_device.close()
        super().closeEvent(event)
