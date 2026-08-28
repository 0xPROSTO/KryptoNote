from PySide6.QtCore import QEasingCurve, QPropertyAnimation, QSize, QTimer, Qt
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QVBoxLayout,
    QWidget,
)

from KryptoNote.gui.theme import Theme
from KryptoNote.gui.widgets.dialog_close_button import DialogCloseButton
from KryptoNote.gui.widgets.dialog_motion import (
    widget_motion_duration,
    widget_spatial_motion_enabled,
)
from KryptoNote.gui.widgets.frameless_window import FramelessWindowDragMixin


class DashboardDialog(FramelessWindowDragMixin, QDialog):
    def __init__(self, stats, parent=None):
        super().__init__(parent)
        self.stats = stats or {}
        self._type_bar_targets = []
        self._type_bar_animations = []
        self._type_bars_started = False

        self.configure_dialog_chrome("Knowledge Dashboard")
        self.setFixedSize(760, 680)
        self.setStyleSheet(self._style())

        self._init_ui()
        self._setup_window_drag(drag_height=72, drag_handles=[self._drag_handle])

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        container = QWidget()
        container.setObjectName("about_container")
        layout = QVBoxLayout(container)
        layout.setContentsMargins(22, 16, 22, 18)
        layout.setSpacing(12)

        header = QWidget()
        self._drag_handle = header
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)

        title = QLabel("Knowledge Dashboard")
        title.setObjectName("dashboard_title")
        header_layout.addWidget(title, 1)

        btn_close = DialogCloseButton()
        btn_close.setIconSize(QSize(18, 18))
        btn_close.setToolTip("Close")
        btn_close.setAccessibleName("Close")
        btn_close.setObjectName("btn_close")
        btn_close.setFixedSize(40, 40)
        btn_close.clicked.connect(self.close)
        header_layout.addWidget(btn_close)
        layout.addWidget(header)

        summary = QWidget()
        summary_layout = QHBoxLayout(summary)
        summary_layout.setContentsMargins(0, 0, 0, 0)
        summary_layout.setSpacing(12)
        summary_layout.addWidget(
            self._metric("Nodes", self.stats.get("node_count", 0))
        )
        summary_layout.addWidget(
            self._metric("Links", self.stats.get("link_count", 0))
        )
        summary_layout.addWidget(
            self._metric("Data Size", self.stats.get("content_size_label", "0 B"))
        )
        layout.addWidget(summary)

        overview = self._section("Project overview")
        overview_layout = overview.layout()
        rows = [
            ("Project created", self.stats.get("project_created_label", "-")),
            ("Last modified", self.stats.get("last_modified_label", "-")),
            ("Text nodes", self.stats.get("text_node_count", 0)),
            ("Media nodes", self.stats.get("media_node_count", 0)),
            ("Text characters", self.stats.get("text_chars_label", "0")),
            ("Text words", self.stats.get("text_words_label", "0")),
            ("Physical DB size", self.stats.get("db_size_label", "0 B")),
            ("Main DB file", self.stats.get("db_main_size_label", "0 B")),
            ("WAL file", self.stats.get("db_wal_size_label", "0 B")),
            ("SHM file", self.stats.get("db_shm_size_label", "0 B")),
            (
                "Reusable inside DB",
                self.stats.get("db_reusable_size_label", "0 B"),
            ),
            ("Media payload", self.stats.get("media_size_label", "0 B")),
            ("Last backup", self.stats.get("last_backup_label", "Never")),
        ]
        overview_columns = QHBoxLayout()
        overview_columns.setContentsMargins(0, 0, 0, 0)
        overview_columns.setSpacing(14)
        overview_columns.addWidget(self._overview_column(rows[::2]), 1)
        overview_columns.addWidget(self._vertical_divider())
        overview_columns.addWidget(self._overview_column(rows[1::2]), 1)
        overview_layout.addLayout(overview_columns)
        layout.addWidget(overview)

        graph = self._section("Graph health")
        graph_layout = graph.layout()
        graph_row = QHBoxLayout()
        graph_row.setContentsMargins(0, 0, 0, 0)
        graph_row.setSpacing(10)
        graph_rows = [
            ("Connected nodes", self.stats.get("connected_node_count", 0)),
            ("Orphan nodes", self.stats.get("orphan_node_count", 0)),
            ("Avg links / node", self.stats.get("avg_links_per_node_label", "0.00")),
        ]
        for index, (label, value) in enumerate(graph_rows):
            metric = QWidget()
            metric_layout = QHBoxLayout(metric)
            metric_layout.setContentsMargins(4, 0, 4, 0)
            metric_layout.setSpacing(8)
            metric_layout.addWidget(self._label(label))
            metric_layout.addStretch()
            metric_layout.addWidget(self._value(str(value)))
            graph_row.addWidget(metric, 1)
            if index < len(graph_rows) - 1:
                graph_row.addWidget(self._vertical_divider())
        graph_layout.addLayout(graph_row)
        layout.addWidget(graph)

        types = self._section("Nodes by type")
        types_layout = types.layout()
        types_layout.setSpacing(6)

        type_stats = self.stats.get("type_stats") or []
        if type_stats:
            for item in type_stats:
                types_layout.addWidget(self._type_row(item))
        else:
            empty = QLabel("No nodes")
            empty.setObjectName("dashboard_empty")
            types_layout.addWidget(empty)
        layout.addWidget(types)

        main_layout.addWidget(container)

    def _metric(self, label, value):
        frame = QFrame()
        frame.setObjectName("dashboard_metric")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(12, 7, 12, 7)
        layout.setSpacing(2)

        value_label = QLabel(str(value))
        value_label.setObjectName("dashboard_metric_value")
        value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(value_label)

        label_widget = QLabel(label)
        label_widget.setObjectName("dashboard_metric_label")
        label_widget.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(label_widget)
        return frame

    def _section(self, title):
        frame = QFrame()
        frame.setObjectName("dashboard_section")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(7)

        heading = QLabel(title)
        heading.setObjectName("dashboard_heading")
        layout.addWidget(heading)
        return frame

    def _overview_column(self, rows):
        column = QWidget()
        grid = QGridLayout(column)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(5)
        for row, (label, value) in enumerate(rows):
            grid.addWidget(self._label(label), row, 0)
            value_label = self._value(str(value))
            value_label.setAlignment(
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            )
            grid.addWidget(value_label, row, 1)
        grid.setColumnStretch(0, 1)
        return column

    @staticmethod
    def _vertical_divider():
        divider = QFrame()
        divider.setObjectName("dashboard_divider")
        divider.setFixedWidth(1)
        return divider

    @staticmethod
    def _label(text):
        label = QLabel(text)
        label.setObjectName("dashboard_label")
        return label

    @staticmethod
    def _value(text):
        value = QLabel(text)
        value.setObjectName("dashboard_value")
        return value

    def _type_row(self, item):
        row = QWidget()
        row.setFixedHeight(22)
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        name = QLabel(str(item.get("type", "Unknown")).capitalize())
        name.setObjectName("dashboard_type_name")
        layout.addWidget(name, 0)

        bar = QProgressBar()
        bar.setObjectName("dashboard_type_bar")
        bar.setRange(0, 1000)
        target = int(round(float(item.get("percent", 0.0)) * 10))
        if widget_spatial_motion_enabled(self):
            bar.setValue(0)
            self._type_bar_targets.append((bar, target))
        else:
            bar.setValue(target)
        bar.setTextVisible(False)
        layout.addWidget(bar, 1)

        percent = QLabel(item.get("percent_label", "0%"))
        percent.setObjectName("dashboard_type_percent")
        percent.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(percent)

        value = QLabel(str(item.get("count", 0)))
        value.setObjectName("dashboard_type_count")
        value.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(value)
        return row

    def showEvent(self, event):
        super().showEvent(event)
        if self._type_bars_started or not self._type_bar_targets:
            return
        self._type_bars_started = True
        QTimer.singleShot(0, self._start_type_bar_animations)

    def _start_type_bar_animations(self):
        if not self.isVisible():
            return
        duration = min(220, widget_motion_duration(self, "panel"))
        for bar, target in self._type_bar_targets:
            animation = QPropertyAnimation(bar, b"value", self)
            animation.setStartValue(0)
            animation.setEndValue(target)
            animation.setDuration(duration)
            animation.setEasingCurve(QEasingCurve.Type.OutCubic)
            animation.start()
            self._type_bar_animations.append(animation)

    @staticmethod
    def _style():
        palette = Theme.Palette
        return Theme.Styles.get_about_dialog_qss() + f"""
            QLabel#dashboard_title {{
                color: {palette.ACCENT_MAIN};
                font-size: 24px;
                font-weight: 900;
            }}
            QFrame#dashboard_metric,
            QFrame#dashboard_section {{
                background: {palette.BG_PANEL};
                border: 1px solid {palette.BORDER_DEFAULT};
                border-radius: 8px;
            }}
            QFrame#dashboard_divider {{
                background: {palette.BORDER_SUBTLE};
                border: none;
            }}
            QLabel#dashboard_metric_value {{
                color: {palette.TEXT_MAIN};
                font-size: 22px;
                font-weight: 900;
            }}
            QLabel#dashboard_metric_label,
            QLabel#dashboard_label,
            QLabel#dashboard_type_name,
            QLabel#dashboard_empty {{
                color: {palette.TEXT_MUTED};
                font-size: 13px;
            }}
            QLabel#dashboard_value,
            QLabel#dashboard_type_count,
            QLabel#dashboard_type_percent {{
                color: {palette.TEXT_MAIN};
                font-size: 13px;
                font-weight: 700;
            }}
            QLabel#dashboard_type_name {{
                min-width: 72px;
            }}
            QLabel#dashboard_type_percent {{
                min-width: 44px;
            }}
            QLabel#dashboard_type_count {{
                min-width: 32px;
            }}
            QLabel#dashboard_heading {{
                color: {palette.ACCENT_MAIN};
                font-size: 16px;
                font-weight: 900;
            }}
            QProgressBar#dashboard_type_bar {{
                background: {palette.BG_NODE};
                border: 1px solid {palette.BORDER_DEFAULT};
                border-radius: 4px;
                height: 8px;
            }}
            QProgressBar#dashboard_type_bar::chunk {{
                background: {palette.ACCENT_MAIN};
                border-radius: 3px;
            }}
        """
