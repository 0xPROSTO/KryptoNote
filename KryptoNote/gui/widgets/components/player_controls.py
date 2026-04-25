from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QWidget, QHBoxLayout, QPushButton, QSlider, QLabel
from ...theme.icons import VectorIcons
from ...theme.palette import Palette
from ...theme.style_factory import StyleFactory

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


class PlayerControlsWidget(QWidget):
    playToggled = Signal()
    muteToggled = Signal()
    seekMoved = Signal(int)
    seekPressed = Signal()
    seekReleased = Signal()
    volumeChanged = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("ControlsContainer")
        self.setFixedHeight(60)

        self._is_muted = False
        self._last_volume = 10
        self._is_playing = False

        self.icon_play = VectorIcons.get_icon("play")
        self.icon_pause = VectorIcons.get_icon("pause")
        self.icon_volume = VectorIcons.get_icon("volume")
        self.icon_mute = VectorIcons.get_icon("mute")

        self._setup_ui()
        self.setStyleSheet(StyleFactory.get_player_controls_qss())

    def _setup_ui(self):
        ctrl_layout = QHBoxLayout(self)
        ctrl_layout.setContentsMargins(20, 0, 20, 0)
        ctrl_layout.setSpacing(15)
        ctrl_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        self.btn_play = QPushButton()
        self.btn_play.setIcon(self.icon_play)
        self.btn_play.setIconSize(self.btn_play.sizeHint() * 1.2)
        self.btn_play.setFixedSize(36, 36)
        self.btn_play.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_play.clicked.connect(self._on_play_clicked)
        ctrl_layout.addWidget(self.btn_play)

        self.seek_slider = ClickableSlider(Qt.Orientation.Horizontal)
        self.seek_slider.setCursor(Qt.CursorShape.PointingHandCursor)
        self.seek_slider.setFixedHeight(20)
        self.seek_slider.sliderMoved.connect(self.seekMoved.emit)
        self.seek_slider.sliderPressed.connect(self.seekPressed.emit)
        self.seek_slider.sliderReleased.connect(self.seekReleased.emit)
        ctrl_layout.addWidget(self.seek_slider)

        self.lbl_time = QLabel("00:00 / 00:00")
        self.lbl_time.setFixedWidth(100)
        self.lbl_time.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ctrl_layout.addWidget(self.lbl_time)

        vol_layout = QHBoxLayout()
        vol_layout.setSpacing(5)
        vol_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        self.btn_vol_icon = QPushButton()
        self.btn_vol_icon.setIcon(self.icon_volume)
        self.btn_vol_icon.setFixedSize(32, 32)
        self.btn_vol_icon.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_vol_icon.clicked.connect(self._on_mute_clicked)
        vol_layout.addWidget(self.btn_vol_icon)

        self.vol_slider = ClickableSlider(Qt.Orientation.Horizontal)
        self.vol_slider.setFixedWidth(100)
        self.vol_slider.setFixedHeight(20)
        self.vol_slider.setRange(0, 100)
        self.vol_slider.setValue(self._last_volume)
        self.vol_slider.setCursor(Qt.CursorShape.PointingHandCursor)
        self.vol_slider.valueChanged.connect(self._on_volume_changed)
        vol_layout.addWidget(self.vol_slider)

        ctrl_layout.addLayout(vol_layout)

    def _on_play_clicked(self):
        self.playToggled.emit()

    def set_playing_state(self, is_playing: bool):
        self._is_playing = is_playing
        self.btn_play.setIcon(self.icon_pause if is_playing else self.icon_play)

    def _on_mute_clicked(self):
        self.muteToggled.emit()

    def set_muted_state(self, is_muted: bool):
        self._is_muted = is_muted
        self.btn_vol_icon.setIcon(self.icon_mute if is_muted else self.icon_volume)
        if is_muted:
            self.vol_slider.blockSignals(True)
            self.vol_slider.setValue(0)
            self.vol_slider.blockSignals(False)
        else:
            self.vol_slider.blockSignals(True)
            self.vol_slider.setValue(self._last_volume)
            self.vol_slider.blockSignals(False)

    def _on_volume_changed(self, value):
        if value > 0:
            self._last_volume = value
        self.volumeChanged.emit(value)

    def set_time(self, position_ms, duration_ms):
        def fmt(ms):
            seconds = (ms // 1000) % 60
            minutes = ms // 60000
            return f"{minutes:02}:{seconds:02}"
        self.lbl_time.setText(f"{fmt(position_ms)} / {fmt(duration_ms)}")

    def update_position(self, position):
        if not self.seek_slider.isSliderDown():
            self.seek_slider.setValue(position)

    def update_duration(self, duration):
        self.seek_slider.setRange(0, duration)

    def get_current_volume(self) -> int:
        return self._last_volume
