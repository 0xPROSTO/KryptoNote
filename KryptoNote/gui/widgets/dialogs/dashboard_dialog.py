from PySide6.QtCore import QPoint, Qt
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from KryptoNote.gui.theme import Theme


class DashboardDialog(QDialog):
    def __init__(self, stats, parent=None):
        super().__init__(parent)
        self.stats = stats or {}

        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(700, 650)
        self.setStyleSheet(self._style())

        self._dragging = False
        self._drag_start_pos = QPoint()
        self._init_ui()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        container = QWidget()
        container.setObjectName("about_container")
        layout = QVBoxLayout(container)
        layout.setContentsMargins(24, 20, 24, 24)
        layout.setSpacing(16)

        header = QWidget()
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)

        title = QLabel("Knowledge Dashboard")
        title.setObjectName("dashboard_title")
        header_layout.addWidget(title, 1)

        btn_close = QPushButton("×")
        btn_close.setObjectName("btn_close")
        btn_close.setFixedSize(40, 40)
        btn_close.setCursor(Qt.CursorShape.PointingHandCursor)
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
            self._metric("DB Size", self.stats.get("db_size_label", "0 B"))
        )
        layout.addWidget(summary)

        overview = self._section("Project overview")
        overview_layout = overview.layout()
        overview_grid = QGridLayout()
        overview_grid.setContentsMargins(0, 0, 0, 0)
        overview_grid.setHorizontalSpacing(20)
        overview_grid.setVerticalSpacing(9)

        rows = [
            ("Project created", self.stats.get("project_created_label", "-")),
            ("Last modified", self.stats.get("last_modified_label", "-")),
            ("Text nodes", self.stats.get("text_node_count", 0)),
            ("Media nodes", self.stats.get("media_node_count", 0)),
            ("Text characters", self.stats.get("text_chars_label", "0")),
            ("Text words", self.stats.get("text_words_label", "0")),
            ("Media payload", self.stats.get("media_size_label", "0 B")),
            ("Last backup", self.stats.get("last_backup_label", "Never")),
        ]
        for index, (label, value) in enumerate(rows):
            row = index // 2
            col = (index % 2) * 2
            overview_grid.addWidget(self._label(label), row, col)
            overview_grid.addWidget(self._value(str(value)), row, col + 1)
        overview_layout.addLayout(overview_grid)
        layout.addWidget(overview)

        graph = self._section("Graph health")
        graph_layout = graph.layout()
        graph_grid = QGridLayout()
        graph_grid.setContentsMargins(0, 0, 0, 0)
        graph_grid.setHorizontalSpacing(20)
        graph_grid.setVerticalSpacing(9)
        graph_rows = [
            ("Connected nodes", self.stats.get("connected_node_count", 0)),
            ("Orphan nodes", self.stats.get("orphan_node_count", 0)),
            ("Avg links / node", self.stats.get("avg_links_per_node_label", "0.00")),
        ]
        for row, (label, value) in enumerate(graph_rows):
            graph_grid.addWidget(self._label(label), row, 0)
            graph_grid.addWidget(self._value(str(value)), row, 1)
        graph_layout.addLayout(graph_grid)
        layout.addWidget(graph)

        types = self._section("Nodes by type")
        types_layout = types.layout()

        scroll = QScrollArea()
        scroll.setObjectName("dashboard_scroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        type_content = QWidget()
        type_content.setObjectName("dashboard_scroll_content")
        type_content_layout = QVBoxLayout(type_content)
        type_content_layout.setContentsMargins(0, 0, 0, 0)
        type_content_layout.setSpacing(10)

        type_stats = self.stats.get("type_stats") or []
        if type_stats:
            for item in type_stats:
                type_content_layout.addWidget(self._type_row(item))
        else:
            empty = QLabel("No nodes")
            empty.setObjectName("dashboard_empty")
            type_content_layout.addWidget(empty)
        type_content_layout.addStretch()
        scroll.setWidget(type_content)
        types_layout.addWidget(scroll, 1)
        layout.addWidget(types, 1)

        main_layout.addWidget(container)

    def _metric(self, label, value):
        frame = QFrame()
        frame.setObjectName("dashboard_metric")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(4)

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
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(10)

        heading = QLabel(title)
        heading.setObjectName("dashboard_heading")
        layout.addWidget(heading)
        return frame

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
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        name = QLabel(str(item.get("type", "Unknown")).capitalize())
        name.setObjectName("dashboard_type_name")
        layout.addWidget(name, 0)

        bar = QProgressBar()
        bar.setObjectName("dashboard_type_bar")
        bar.setRange(0, 1000)
        bar.setValue(int(round(float(item.get("percent", 0.0)) * 10)))
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

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._dragging = True
            self._drag_start_pos = event.position().toPoint()
            event.accept()

    def mouseMoveEvent(self, event):
        if self._dragging and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_start_pos)
            event.accept()

    def mouseReleaseEvent(self, event):
        self._dragging = False

    @staticmethod
    def _style():
        return Theme.Styles.get_about_dialog_qss() + """
            QLabel#dashboard_title {
                color: #e6158b;
                font-size: 24px;
                font-weight: 900;
            }
            QFrame#dashboard_metric,
            QFrame#dashboard_section {
                background: #1e1e1e;
                border: 1px solid #34383d;
                border-radius: 8px;
            }
            QLabel#dashboard_metric_value {
                color: #efefef;
                font-size: 24px;
                font-weight: 900;
            }
            QLabel#dashboard_metric_label,
            QLabel#dashboard_label,
            QLabel#dashboard_type_name,
            QLabel#dashboard_empty {
                color: #a8adb5;
                font-size: 13px;
            }
            QLabel#dashboard_value,
            QLabel#dashboard_type_count,
            QLabel#dashboard_type_percent {
                color: #efefef;
                font-size: 13px;
                font-weight: 700;
            }
            QLabel#dashboard_type_name {
                min-width: 72px;
            }
            QLabel#dashboard_type_percent {
                min-width: 44px;
            }
            QLabel#dashboard_type_count {
                min-width: 32px;
            }
            QLabel#dashboard_heading {
                color: #e6158b;
                font-size: 17px;
                font-weight: 900;
            }
            QScrollArea#dashboard_scroll,
            QWidget#dashboard_scroll_content {
                background: #1e1e1e;
                border: none;
            }
            QProgressBar#dashboard_type_bar {
                background: #26282b;
                border: 1px solid #34383d;
                border-radius: 4px;
                height: 8px;
            }
            QProgressBar#dashboard_type_bar::chunk {
                background: #e6158b;
                border-radius: 3px;
            }
            QScrollArea#dashboard_scroll QScrollBar:vertical {
                background: transparent;
                width: 8px;
                margin: 4px 2px 8px 0;
            }
            QScrollArea#dashboard_scroll QScrollBar::handle:vertical {
                background: #5a5a5a;
                border-radius: 4px;
                min-height: 32px;
            }
            QScrollArea#dashboard_scroll QScrollBar::add-line:vertical,
            QScrollArea#dashboard_scroll QScrollBar::sub-line:vertical {
                height: 0;
            }
        """
