from .palette import Palette
from .typography import Typography


class StyleFactory:
    @staticmethod
    def _generate_button_qss(bg, border, text, hover_bg, hover_border, selector="QPushButton"):
        return f"""
            {selector} {{
                background-color: {bg};
                border: 1px solid {border};
                color: {text};
                padding: 8px 15px;
                font-size: 12px;
                font-weight: bold;
                border-radius: 4px;
                text-transform: uppercase;
            }}
            {selector}:hover {{
                background-color: {hover_bg};
                border-color: {hover_border};
            }}
        """

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
            {StyleFactory._generate_button_qss(Palette.BTN_APPLY, "#2a5a32", "#99ff99", Palette.BTN_APPLY_HOVER, "#3eb05d", "QPushButton#btn_apply")}
            {StyleFactory._generate_button_qss(Palette.BTN_CANCEL, "#5a2a2a", "#ff9999", Palette.BTN_CANCEL_HOVER, "#8c2a2a", "QPushButton#btn_cancel")}
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
            {StyleFactory._generate_button_qss(Palette.BTN_CANCEL, "#5a2a2a", "#ff9999", Palette.BTN_CANCEL_HOVER, "#8c2a2a", "QPushButton#btn_danger")}
            {StyleFactory._generate_button_qss(Palette.BTN_APPLY, "#2a5a2a", "#99ff99", Palette.BTN_APPLY_HOVER, "#2a8c2a", "QPushButton#btn_success")}
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

    @staticmethod
    def get_title_bar_qss():
        return f"""
            CustomTitleBar {{
                background-color: {Palette.BG_TITLE_BAR};
                border-bottom: 1px solid {Palette.BORDER_TITLE_BAR};
            }}
            QMenuBar {{
                background: transparent;
                color: {Palette.TEXT_DIM};
                border: none;
                font-family: 'Segoe UI', sans-serif;
                font-size: 13px;
                margin: 0;
                padding: 0;
            }}
            QMenuBar::item {{
                background: transparent;
                padding: 6px 15px;
                margin: 0;
            }}
            QMenuBar::item:selected {{
                background-color: #333333;
                color: {Palette.TEXT_MAIN};
            }}
            QMenu {{
                background-color: {Palette.BG_PANEL};
                color: {Palette.TEXT_MAIN};
                border: 1px solid {Palette.BORDER_DEFAULT};
                font-size: 13px;
                margin-top: 0;
            }}
            QMenu::item {{
                padding: 8px 32px;
            }}
            QMenu::item:selected {{
                background-color: {Palette.ACCENT_LOW};
                color: {Palette.ACCENT_MAIN};
            }}
            QMenu::separator {{
                height: 1px;
                background: {Palette.BORDER_DEFAULT};
                margin: 4px 0;
            }}
            QLabel#window_title {{
                color: {Palette.TEXT_MUTED};
                font-family: 'Segoe UI', sans-serif;
                font-size: 12px;
            }}
        """

    @staticmethod
    def get_player_qss():
        return f"""
            QDialog {{ background-color: {Palette.BG_CANVAS}; }} 
            QWidget {{ color: {Palette.TEXT_MAIN}; }} 
            QSlider::groove:horizontal {{ border: 1px solid {Palette.BORDER_DEFAULT}; height: 4px; background: {Palette.BG_INPUT}; margin: 0px; border-radius: 2px; }} 
            QSlider::sub-page:horizontal {{ background: {Palette.ACCENT_LOW}; border-radius: 2px; }} 
            QSlider::handle:horizontal {{ background: {Palette.TEXT_MAIN}; border: 1px solid {Palette.BORDER_DEFAULT}; width: 12px; height: 12px; margin: -4px 0; border-radius: 6px; }} 
            QSlider::handle:horizontal:hover {{ background: {Palette.ACCENT_HIGH}; }} 
            QLabel {{ font-family: {Typography.FONT_BODY}, sans-serif; font-size: 12px; color: {Palette.TEXT_DIM}; }} 
        """

    @staticmethod
    def get_status_bar_qss(type="normal"):
        color = Palette.TEXT_MUTED
        weight = "normal"
        size = "12px"
        padding = "0 10px"

        if type == "secure":
            color = "#00FF00"
            weight = "bold"
        elif type == "accent":
            color = Palette.ACCENT_MAIN
            weight = "bold"
        elif type == "coords":
            color = Palette.TEXT_MUTED
            weight = "bold"
            size = "11px"

        return f"padding: {padding}; color: {color}; font-weight: {weight}; font-size: {size};"
