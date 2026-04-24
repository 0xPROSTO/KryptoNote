from PySide6.QtCore import Qt, QUrl, QTimer
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
from PySide6.QtMultimediaWidgets import QVideoWidget
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QSlider,
    QLabel,
    QWidget,
    QSizePolicy,
    QStyle,
)

from ...config import Config
from ...gui.theme import Theme
from ...core.io.stream import BlockEncryptedStream


class ClickableSlider(QSlider):
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            if self.orientation() == Qt.Orientation.Horizontal:
                val = (
                        self.minimum()
                        + ((self.maximum() - self.minimum()) * event.pos().x())
                        / self.width()
                )

            else:
                val = (
                        self.minimum()
                        + (
                                (self.maximum() - self.minimum())
                                * (self.height() - event.pos().y())
                        )
                        / self.height()
                )

            self.setValue(int(val))
            self.sliderMoved.emit(int(val))

        super().mousePressEvent(event)


class SecureVideoPlayer(QDialog):
    def __init__(self, repo, item_id, total_size, chunk_size, title="Secure Video"):
        super().__init__()
        self.setWindowTitle(title)
        self.resize(1000, 700)
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowMinMaxButtonsHint)
        self.setStyleSheet(Theme.Styles.get_player_qss())
        self.repo = repo

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.video_widget = QVideoWidget()
        self.video_widget.setAspectRatioMode(Qt.AspectRatioMode.KeepAspectRatio)
        self.video_widget.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        layout.addWidget(self.video_widget)

        self.controls_container = QWidget()
        self.controls_container.setStyleSheet(
            f"background-color: {Theme.Palette.BG_TITLE_BAR}; border-top: 1px solid {Theme.Palette.BORDER_DEFAULT};"
        )
        self.controls_container.setFixedHeight(50)

        ctrl_layout = QHBoxLayout(self.controls_container)
        ctrl_layout.setContentsMargins(15, 0, 15, 0)
        ctrl_layout.setSpacing(15)
        ctrl_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        self.btn_play = QPushButton()
        self.icon_play = self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay)
        self.icon_pause = self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPause)
        self.btn_play.setIcon(self.icon_play)
        self.btn_play.setFlat(True)
        self.btn_play.setFixedSize(30, 30)
        self.btn_play.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_play.clicked.connect(self.toggle_play)
        ctrl_layout.addWidget(self.btn_play)

        self.seek_slider = ClickableSlider(Qt.Orientation.Horizontal)
        self.seek_slider.setCursor(Qt.CursorShape.PointingHandCursor)
        self.seek_slider.setFixedHeight(20)
        self.seek_slider.sliderMoved.connect(self.set_position)
        self.seek_slider.sliderPressed.connect(self.pause_on_seek)
        self.seek_slider.sliderReleased.connect(self.play_on_seek)
        ctrl_layout.addWidget(self.seek_slider)

        self.lbl_time = QLabel("00:00 / 00:00")
        self.lbl_time.setFixedWidth(100)
        self.lbl_time.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ctrl_layout.addWidget(self.lbl_time)

        vol_layout = QHBoxLayout()
        vol_layout.setSpacing(5)
        vol_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        btn_vol_icon = QPushButton()
        btn_vol_icon.setIcon(
            self.style().standardIcon(QStyle.StandardPixmap.SP_MediaVolume)
        )
        btn_vol_icon.setFlat(True)
        btn_vol_icon.setFixedSize(30, 30)
        btn_vol_icon.setEnabled(False)
        vol_layout.addWidget(btn_vol_icon)

        self.vol_slider = ClickableSlider(Qt.Orientation.Horizontal)
        self.vol_slider.setFixedWidth(80)
        self.vol_slider.setFixedHeight(20)
        self.vol_slider.setRange(0, 100)
        self.vol_slider.setValue(10)
        self.vol_slider.setCursor(Qt.CursorShape.PointingHandCursor)
        self.vol_slider.valueChanged.connect(self.set_volume)
        vol_layout.addWidget(self.vol_slider)

        ctrl_layout.addLayout(vol_layout)
        layout.addWidget(self.controls_container)

        self.player = QMediaPlayer(self)
        self.audio = QAudioOutput(self)
        self.player.setAudioOutput(self.audio)
        self.player.setVideoOutput(self.video_widget)
        self.audio.setVolume(0.1)

        self.player.positionChanged.connect(self.position_changed)
        self.player.durationChanged.connect(self.duration_changed)
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

    def start_playback(self):
        self.player.play()
        self.btn_play.setIcon(self.icon_pause)

    def toggle_play(self):
        if self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.player.pause()
            self.btn_play.setIcon(self.icon_play)

        else:
            self.player.play()
            self.btn_play.setIcon(self.icon_pause)

    def set_volume(self, value):
        self.audio.setVolume(value / 100.0)

    def position_changed(self, position):
        if not self.seek_slider.isSliderDown():
            self.seek_slider.setValue(position)

        self.update_label()

    def duration_changed(self, duration):
        self.seek_slider.setRange(0, duration)
        self.update_label()

    def set_position(self, position):
        self.player.setPosition(position)

    def pause_on_seek(self):
        self.player.pause()

    def play_on_seek(self):
        self.player.play()
        if self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.btn_play.setIcon(self.icon_pause)

        else:
            self.btn_play.setIcon(self.icon_play)

    def update_label(self):
        def fmt(ms):
            seconds = (ms // 1000) % 60
            minutes = ms // 60000
            return f"{minutes:02}:{seconds:02}"

        self.lbl_time.setText(
            f"{fmt(self.player.position())} / {fmt(self.player.duration())}"
        )

    def handle_errors(self):
        self.btn_play.setEnabled(False)
        self.lbl_time.setText("Error")
        print(self.player.errorString())

    def closeEvent(self, event):
        self.player.stop()
        self.player.setSource(QUrl())
        self.io_device.close()
        super().closeEvent(event)
