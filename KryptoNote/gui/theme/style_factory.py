from .palette import Palette


class StyleFactory:
    @staticmethod
    def get_main_window_qss():
        return f"""
            QMainWindow {{ 
                background-color: {Palette.BG_CANVAS};
            }} 
            QStatusBar {{ 
                background-color: {Palette.BG_PANEL};
                color: {Palette.TEXT_MUTED};
                border-top: 1px solid {Palette.BORDER_DEFAULT};
            }} 
            QMenuBar {{ 
                background-color: {Palette.BG_PANEL};
                color: {Palette.TEXT_DIM};
                border-bottom: 1px solid {Palette.BORDER_DEFAULT};
            }} 
            QMenuBar::item:selected {{ 
                background-color: {Palette.BG_NODE};
                color: {Palette.ACCENT_MAIN};
            }} 
            QMenu {{ 
                background-color: {Palette.BG_PANEL};
                color: {Palette.TEXT_MAIN};
                border: 1px solid {Palette.BORDER_DEFAULT};
                border-radius: 4px;
            }} 
            QMenu::item:selected {{ 
                background-color: {Palette.ACCENT_LOW};
                color: {Palette.ACCENT_MAIN};
            }} 
        """

    @staticmethod
    def get_node_editor_qss():
        return f"""
            QDialog {{ 
                background-color: {Palette.BG_PANEL};
                color: {Palette.TEXT_MAIN};
            }} 
            QLineEdit#title_edit {{ 
                background-color: {Palette.BG_INPUT};
                color: {Palette.ACCENT_MAIN};
                border: 1px solid {Palette.BORDER_DEFAULT};
                border-radius: 4px;
                padding: 8px 10px;
                font-size: 14px;
                font-weight: bold;
            }} 
            QLineEdit#title_edit:focus {{ 
                border-color: {Palette.ACCENT_MAIN};
            }} 
            QFrame#separator {{ 
                background-color: rgba(255, 255, 255, 0.05);
                border: none;
                max-height: 1px;
                margin: 5px 0px;
            }} 
            QTextEdit {{ 
                background-color: {Palette.BG_INPUT};
                color: {Palette.TEXT_MAIN};
                border: 1px solid {Palette.BORDER_DEFAULT};
                border-radius: 4px;
                padding: 10px;
                font-size: 13px;
                line-height: 1.4;
            }} 
            QPushButton {{ 
                border: 1px solid {Palette.BORDER_DEFAULT};
                padding: 8px 15px;
                font-size: 12px;
                font-weight: bold;
                border-radius: 4px;
                text-transform: uppercase;
                color: {Palette.TEXT_MAIN};
            }} 
            QPushButton#btn_apply {{ 
                background-color: {Palette.BTN_APPLY};
                border-color: #2a5a32;
                color: #99ff99;
            }} 
            QPushButton#btn_apply:hover {{ 
                background-color: {Palette.BTN_APPLY_HOVER};
                border-color: #3eb05d;
            }} 
            QPushButton#btn_cancel {{ 
                background-color: {Palette.BTN_CANCEL};
                border-color: #5a2a2a;
                color: #ff9999;
            }} 
            QPushButton#btn_cancel:hover {{ 
                background-color: {Palette.BTN_CANCEL_HOVER};
                border-color: #8c2a2a;
            }} 
            QComboBox#font_combo {{
                background-color: {Palette.BG_INPUT};
                color: {Palette.TEXT_MAIN};
                border: 1px solid {Palette.BORDER_DEFAULT};
                border-radius: 4px;
                padding: 4px;
                min-width: 60px;
            }}
            QComboBox#font_combo:hover {{
                border-color: {Palette.ACCENT_MAIN};
            }}
            QLabel {{
                color: {Palette.TEXT_DIM};
                font-size: 11px;
                font-weight: bold;
                text-transform: uppercase;
            }}
        """

    @staticmethod
    def get_launcher_qss():
        return f"""
            QDialog {{ 
                background-color: {Palette.BG_PANEL};
                color: {Palette.TEXT_MAIN};
            }} 
            QLabel {{ 
                color: {Palette.TEXT_DIM};
                font-size: 11px;
                text-transform: uppercase;
                letter-spacing: 0.5px;
                font-weight: bold;
            }} 
            QListWidget {{ 
                background-color: {Palette.BG_INPUT};
                color: {Palette.TEXT_MAIN};
                border: 1px solid {Palette.BORDER_DEFAULT};
                border-radius: 4px;
                outline: none;
                padding: 2px;
                font-size: 13px;
            }} 
            QListWidget::item {{ 
                padding: 6px 10px;
                border-bottom: 1px solid #1a1a1a;
                border-radius: 4px;
                margin-bottom: 1px;
            }} 
            QListWidget::item:hover {{ 
                background-color: #1e1e1e;
            }} 
            QListWidget::item:selected {{ 
                background-color: #2a2a2a;
                color: {Palette.ACCENT_MAIN};
                border: 1px solid {Palette.ACCENT_LOW};
            }} 
            QLineEdit {{ 
                background-color: {Palette.BG_INPUT};
                color: {Palette.TEXT_MAIN};
                border: 1px solid {Palette.BORDER_DEFAULT};
                border-radius: 4px;
                padding: 5px 8px;
                font-size: 13px;
            }} 
            QLineEdit:focus {{ 
                border-color: {Palette.ACCENT_MAIN};
            }} 
            QPushButton {{ 
                background-color: #2a2a2a;
                color: {Palette.TEXT_MAIN};
                border: 1px solid {Palette.BORDER_DEFAULT};
                padding: 6px 10px;
                font-size: 12px;
                font-weight: bold;
                border-radius: 4px;
            }} 
            QPushButton:hover {{ 
                border-color: {Palette.ACCENT_MAIN};
                background-color: #333333;
            }} 
            QPushButton#btn_create {{ 
                background-color: #222222;
                border-color: #333333;
                color: {Palette.TEXT_DIM};
            }} 
            QPushButton#btn_danger {{ 
                background-color: {Palette.BTN_CANCEL};
                color: #ff9999;
                border: 1px solid #5a2a2a;
            }} 
            QPushButton#btn_danger:hover {{ 
                background-color: {Palette.BTN_CANCEL_HOVER};
                border-color: #8c2a2a;
            }} 
            QPushButton#btn_success {{ 
                background-color: {Palette.BTN_APPLY};
                color: #99ff99;
                border: 1px solid #2a5a2a;
            }} 
            QPushButton#btn_success:hover {{ 
                background-color: {Palette.BTN_APPLY_HOVER};
                border-color: #2a8c2a;
            }} 
        """

    @staticmethod
    def get_about_dialog_qss():
        return f"""
            QDialog {{ 
                background: transparent;
            }} 
            QWidget#about_container {{ 
                background-color: {Palette.BG_PANEL};
                border: 1px solid {Palette.BORDER_DEFAULT};
                border-radius: 12px;
            }} 
            QLabel {{ 
                background: transparent;
                border: none;
            }} 
            QLabel#logo_label {{ 
                margin-top: 5px;
                margin-bottom: 25px;
            }} 
            QLabel#app_name {{ 
                color: {Palette.ACCENT_MAIN};
                font-size: 20px;
                font-weight: bold;
            }} 
            QLabel#author_label {{ 
                color: {Palette.TEXT_MAIN};
                font-size: 14px;
            }} 
            QLabel#version_label {{ 
                color: {Palette.TEXT_DIM};
                font-size: 12px;
            }} 
            QLabel#desc_label {{ 
                color: {Palette.TEXT_MUTED};
                font-size: 12px;
                line-height: 1.5;
                margin-bottom: 20px;
            }} 
            QLabel#github_link {{ 
                color: {Palette.ACCENT_MAIN};
                margin-bottom: 20px;
            }} 
            QPushButton#btn_close {{ 
                background: transparent;
                color: {Palette.TEXT_MUTED};
                border: none;
                font-size: 24px;
                font-weight: 900;
                padding: 5px;
            }} 
            QPushButton#btn_close:hover {{ 
                color: {Palette.ACCENT_MAIN};
            }} 
        """
