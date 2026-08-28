from .palette import Palette
from .icons import SvgIcons


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
                background-color: {Palette.BG_CONTROL};
                color: {Palette.TEXT_MAIN};
            }}
            QMenu {{
                background-color: {Palette.BG_POPOVER};
                color: {Palette.TEXT_MAIN};
                border: 1px solid {Palette.BORDER_DEFAULT};
                border-radius: 4px;
            }}
            QMenu::item:selected {{
                background-color: {Palette.BG_CONTROL_HOVER};
                color: {Palette.TEXT_MAIN};
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
                background-color: {Palette.WHITE_ALPHA_05};
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
            {StyleFactory._generate_button_qss(Palette.BTN_APPLY, Palette.BTN_APPLY_BORDER, Palette.BTN_APPLY_TEXT, Palette.BTN_APPLY_HOVER, Palette.SUCCESS_HOVER, "QPushButton#btn_apply")}
            {StyleFactory._generate_button_qss(Palette.BTN_CANCEL, Palette.BTN_CANCEL_BORDER, Palette.BTN_CANCEL_TEXT, Palette.BTN_CANCEL_HOVER, Palette.DANGER_HOVER, "QPushButton#btn_cancel")}
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
        dropdown_arrow = SvgIcons.path("move-down").as_posix()
        return f"""
            QDialog {{
                background-color: {Palette.BG_PANEL};
                color: {Palette.TEXT_MAIN};
            }}
            QLabel {{
                color: {Palette.TEXT_DIM};
                font-size: 11px;
                font-weight: bold;
            }}
            QLabel#directory_description {{
                color: {Palette.TEXT_DIM};
                font-size: 12px;
                font-weight: normal;
            }}
            QLabel#directory_status {{
                color: {Palette.BTN_CANCEL_TEXT};
                font-size: 12px;
                font-weight: normal;
                padding: 2px 0;
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
                border-bottom: 1px solid {Palette.GRID_SUB};
                border-radius: 4px;
                margin-bottom: 1px;
            }}
            QListWidget::item:hover {{
                background-color: {Palette.BG_CONTROL_HOVER};
            }}
            QListWidget::item:selected {{
                background-color: {Palette.BG_NODE};
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
            QComboBox {{
                min-height: 28px;
                background-color: {Palette.BG_INPUT};
                color: {Palette.TEXT_MAIN};
                border: 1px solid {Palette.BORDER_DEFAULT};
                border-radius: 4px;
                padding: 0 36px 0 8px;
                font-size: 13px;
            }}
            QComboBox:hover,
            QComboBox:focus {{
                border-color: {Palette.ACCENT_MAIN};
            }}
            QComboBox:disabled {{
                color: {Palette.TEXT_DISABLED};
                border-color: {Palette.BORDER_SUBTLE};
            }}
            QComboBox::drop-down {{
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 28px;
                background-color: {Palette.BG_CONTROL};
                border: none;
                border-left: 1px solid {Palette.BORDER_DEFAULT};
                border-top-right-radius: 3px;
                border-bottom-right-radius: 3px;
            }}
            QComboBox::drop-down:hover {{
                background-color: {Palette.BG_CONTROL_HOVER};
            }}
            QComboBox::drop-down:pressed {{
                background-color: {Palette.BG_CONTROL_PRESSED};
            }}
            QComboBox::down-arrow {{
                image: url("{dropdown_arrow}");
                width: 12px;
                height: 12px;
            }}
            QComboBox::down-arrow:on {{
                top: 1px;
            }}
            QComboBox QAbstractItemView {{
                background-color: {Palette.BG_POPOVER};
                color: {Palette.TEXT_MAIN};
                border: 1px solid {Palette.BORDER_DEFAULT};
                border-radius: 4px;
                outline: none;
                padding: 2px;
                selection-background-color: {Palette.ACCENT_LOW};
                selection-color: {Palette.TEXT_MAIN};
            }}
            QComboBox QAbstractItemView::item {{
                min-height: 24px;
                padding: 0 8px;
            }}
            QComboBox QAbstractItemView::item:selected {{
                background-color: {Palette.ACCENT_LOW};
                color: {Palette.TEXT_MAIN};
            }}
            QComboBox QAbstractItemView::item:hover {{
                background-color: {Palette.BG_CONTROL_HOVER};
                color: {Palette.TEXT_MAIN};
            }}
            QPushButton {{
                background-color: {Palette.BG_CONTROL};
                color: {Palette.TEXT_MAIN};
                border: 1px solid {Palette.BORDER_DEFAULT};
                padding: 6px 10px;
                font-size: 12px;
                font-weight: bold;
                border-radius: 4px;
            }}
            QPushButton:hover {{
                border-color: {Palette.ACCENT_MAIN};
                background-color: {Palette.BG_CONTROL_HOVER};
            }}
            QPushButton#btn_create {{
                background-color: {Palette.BG_INPUT};
                border-color: {Palette.BORDER_DEFAULT};
                color: {Palette.TEXT_DIM};
            }}
            QPushButton#btn_danger {{
                background-color: {Palette.BTN_CANCEL};
                border-color: {Palette.BTN_CANCEL_BORDER};
                color: {Palette.BTN_CANCEL_TEXT};
            }}
            QPushButton#btn_danger:hover {{
                background-color: {Palette.BTN_CANCEL_HOVER};
                border-color: {Palette.DANGER_HOVER};
            }}
            QPushButton#btn_success {{
                background-color: {Palette.BTN_APPLY};
                border-color: {Palette.BTN_APPLY_BORDER};
                color: {Palette.BTN_APPLY_TEXT};
            }}
            QPushButton#btn_success:hover {{
                background-color: {Palette.BTN_APPLY_HOVER};
                border-color: {Palette.SUCCESS_HOVER};
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
            QPushButton#about_action_link {{
                color: {Palette.ACCENT_MAIN};
                background: transparent;
                border: none;
                outline: none;
                padding: 0;
                margin: 0;
                min-height: 18px;
                max-height: 18px;
                font-size: 12px;
                font-weight: 400;
            }}
            QPushButton#about_action_link:hover,
            QPushButton#about_action_link:focus {{
                color: {Palette.ACCENT_HIGH};
                background: transparent;
                border: none;
                outline: none;
            }}
            QPushButton#about_action_link:pressed {{
                color: {Palette.ACCENT_HOVER};
                background: transparent;
                border: none;
            }}
            QLabel#about_action_separator {{
                color: {Palette.TEXT_MUTED};
            }}
            QLabel#support_title {{
                color: {Palette.ACCENT_MAIN};
                font-size: 20px;
                font-weight: 700;
            }}
            QLabel#support_intro {{
                color: {Palette.TEXT_DIM};
                font-size: 12px;
            }}
            QFrame#wallet_card {{
                background: {Palette.BG_NODE};
                border: 1px solid {Palette.BORDER_DEFAULT};
                border-radius: 8px;
            }}
            QLabel#wallet_network {{
                color: {Palette.TEXT_MAIN};
                font-size: 13px;
                font-weight: 700;
            }}
            QLabel#wallet_asset {{
                color: {Palette.TEXT_MUTED};
                font-size: 12px;
            }}
            QLineEdit#wallet_address {{
                min-height: 30px;
                padding: 0 9px;
                color: {Palette.TEXT_MAIN};
                background: {Palette.BG_INPUT};
                border: 1px solid {Palette.BORDER_SUBTLE};
                border-radius: 4px;
                font-family: Consolas, monospace;
                font-size: 12px;
                selection-color: {Palette.ON_ACCENT};
                selection-background-color: {Palette.ACCENT_MAIN};
            }}
            QLineEdit#wallet_address:focus {{
                border-color: {Palette.ACCENT_MAIN};
            }}
            QPushButton#wallet_copy {{
                min-width: 66px;
                min-height: 30px;
                padding: 0 10px;
                color: {Palette.TEXT_MAIN};
                background: {Palette.BG_CONTROL};
                border: 1px solid {Palette.BORDER_DEFAULT};
                border-radius: 4px;
                outline: none;
                font-size: 12px;
                font-weight: 600;
            }}
            QPushButton#wallet_copy:hover,
            QPushButton#wallet_copy:focus {{
                background: {Palette.BG_CONTROL_HOVER};
                border-color: {Palette.ACCENT_MAIN};
            }}
            QPushButton#wallet_copy:pressed {{
                background: {Palette.BG_CONTROL_PRESSED};
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
    def get_confirmation_dialog_qss():
        return f"""
            QDialog#confirmation_dialog {{
                background: transparent;
                color: {Palette.TEXT_MAIN};
                font-family: 'Segoe UI', sans-serif;
            }}
            QWidget#confirmation_container {{
                background: {Palette.BG_PANEL};
                border: 1px solid {Palette.BORDER_DEFAULT};
                border-radius: 10px;
            }}
            QWidget#confirmation_header {{
                background: transparent;
                border: none;
            }}
            QLabel {{
                background: transparent;
                border: none;
            }}
            QLabel#confirmation_icon {{
                background: {Palette.BG_CONTROL};
                border: 1px solid {Palette.BORDER_DEFAULT};
                border-radius: 8px;
            }}
            QLabel#confirmation_icon[destructive="true"] {{
                background: {Palette.BTN_CANCEL};
                border-color: {Palette.BTN_CANCEL_BORDER};
            }}
            QLabel#confirmation_title {{
                color: {Palette.TEXT_MAIN};
                font-size: 15px;
                font-weight: 600;
            }}
            QLabel#confirmation_message {{
                color: {Palette.TEXT_DIM};
                font-size: 12px;
            }}
            QPushButton {{
                min-width: 92px;
                min-height: 34px;
                padding: 0 14px;
                outline: none;
                color: {Palette.TEXT_MAIN};
                background: {Palette.BG_CONTROL};
                border: 1px solid {Palette.BORDER_DEFAULT};
                border-radius: 6px;
                font-size: 12px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background: {Palette.BG_CONTROL_HOVER};
                border-color: {Palette.BORDER_HOVER};
            }}
            QPushButton:pressed {{
                background: {Palette.BG_CONTROL_PRESSED};
            }}
            QPushButton:focus {{
                border: 2px solid {Palette.ACCENT_MAIN};
            }}
            QPushButton#confirmation_close {{
                min-width: 34px;
                max-width: 34px;
                min-height: 34px;
                max-height: 34px;
                padding: 0;
                background: transparent;
                border: none;
            }}
            QPushButton#confirmation_close:hover {{
                background: {Palette.BG_CONTROL_HOVER};
            }}
            QPushButton#confirmation_close:focus {{
                border: 1px solid {Palette.ACCENT_MAIN};
            }}
            QPushButton#confirmation_confirm {{
                color: {Palette.ON_ACCENT};
                background: {Palette.ACCENT_MAIN};
                border-color: {Palette.ACCENT_MAIN};
            }}
            QPushButton#confirmation_confirm:hover {{
                background: {Palette.ACCENT_HOVER};
                border-color: {Palette.ACCENT_HOVER};
            }}
            QPushButton#confirmation_confirm_danger {{
                color: {Palette.TEXT_MAIN};
                background: {Palette.DANGER};
                border-color: {Palette.DANGER};
            }}
            QPushButton#confirmation_confirm_danger:hover {{
                background: {Palette.DANGER_HOVER};
                border-color: {Palette.DANGER_HOVER};
            }}
            QPushButton#confirmation_confirm_danger:focus {{
                border: 2px solid {Palette.TEXT_MAIN};
            }}
        """

    @staticmethod
    def get_theme_dialog_qss():
        return f"""
            QDialog#theme_dialog {{
                background: transparent;
                font-family: 'Segoe UI', sans-serif;
                color: {Palette.TEXT_MAIN};
            }}
            QWidget#theme_container {{
                background: {Palette.BG_PANEL};
                border: 1px solid {Palette.BORDER_DEFAULT};
                border-radius: 10px;
            }}
            QWidget#theme_header,
            QWidget#theme_footer,
            QWidget#theme_settings,
            QWidget#settings_body,
            QWidget#settings_page,
            QStackedWidget#settings_pages {{
                background: transparent;
                border: none;
            }}
            QStackedWidget#theme_route_options {{
                background: transparent;
                border: none;
            }}
            QLabel {{
                background: transparent;
                color: {Palette.TEXT_DIM};
                border: none;
                font-size: 10pt;
            }}
            QLabel#theme_title {{
                color: {Palette.TEXT_MAIN};
                font-size: 14pt;
                font-weight: 600;
            }}
            QLabel#settings_page_title {{
                color: {Palette.TEXT_MAIN};
                font-size: 14pt;
                font-weight: 650;
            }}
            QLabel[sectionTitle="true"] {{
                color: {Palette.TEXT_MAIN};
                font-size: 11pt;
                font-weight: 600;
            }}
            QLabel[controlLabel="true"] {{
                color: {Palette.TEXT_DIM};
                font-size: 9pt;
            }}
            QFrame#theme_separator {{
                background: {Palette.BORDER_SUBTLE};
                border: none;
                min-height: 1px;
                max-height: 1px;
            }}
            QPushButton {{
                min-height: 28px;
                padding: 0 12px;
                color: {Palette.TEXT_MAIN};
                background: {Palette.BG_CONTROL};
                border: 1px solid {Palette.BORDER_DEFAULT};
                border-radius: 5px;
                font-size: 9pt;
            }}
            QPushButton:hover {{
                background: {Palette.BG_CONTROL_HOVER};
                border-color: {Palette.BORDER_HOVER};
            }}
            QPushButton:pressed {{
                background: {Palette.BG_CONTROL_PRESSED};
            }}
            QPushButton:focus {{
                border: 2px solid {Palette.ACCENT_MAIN};
            }}
            QComboBox#font_combo {{
                min-height: 28px;
                padding: 0 8px;
                color: {Palette.TEXT_MAIN};
                background: {Palette.BG_INPUT};
                border: 1px solid {Palette.BORDER_DEFAULT};
                border-radius: 5px;
            }}
            QComboBox#font_combo:hover,
            QComboBox#font_combo:focus {{
                border: 2px solid {Palette.ACCENT_MAIN};
            }}
            QComboBox#font_combo QAbstractItemView {{
                color: {Palette.TEXT_MAIN};
                background: {Palette.BG_POPOVER};
                selection-background-color: {Palette.ACCENT_LOW};
                selection-color: {Palette.TEXT_MAIN};
            }}
            QLabel#maintenance_hint {{
                color: {Palette.TEXT_MUTED};
                font-size: 9pt;
            }}
            QLabel#vacuum_threshold_value {{
                color: {Palette.TEXT_MAIN};
                font-size: 9pt;
                font-weight: 600;
            }}
            QLabel#vacuum_threshold_scale {{
                color: {Palette.TEXT_MUTED};
                font-size: 8pt;
            }}
            QSlider#vacuum_threshold_slider {{
                min-height: 28px;
            }}
            QSlider#vacuum_threshold_slider::groove:horizontal {{
                height: 4px;
                background: {Palette.BORDER_SUBTLE};
                border-radius: 2px;
            }}
            QSlider#vacuum_threshold_slider::sub-page:horizontal {{
                background: {Palette.ACCENT_MAIN};
                border-radius: 2px;
            }}
            QSlider#vacuum_threshold_slider::handle:horizontal {{
                width: 16px;
                margin: -6px 0;
                background: {Palette.BG_CONTROL_HOVER};
                border: 2px solid {Palette.ACCENT_MAIN};
                border-radius: 8px;
            }}
            QSlider#vacuum_threshold_slider::handle:horizontal:hover,
            QSlider#vacuum_threshold_slider::handle:horizontal:focus {{
                background: {Palette.TEXT_MAIN};
            }}
            QPushButton:checked {{
                color: {Palette.TEXT_MAIN};
                background: {Palette.ACCENT_LOW};
                border: 2px solid {Palette.ACCENT_MAIN};
            }}
            QPushButton[connectionStyleButton="true"] {{
                min-height: 54px;
                padding: 0;
            }}
            QPushButton[scopeSwitch="true"] {{
                min-width: 92px;
                max-width: 92px;
            }}
            QWidget#settings_nav {{
                background: {Palette.BG_NODE};
                border: 1px solid {Palette.BORDER_SUBTLE};
                border-radius: 7px;
            }}
            QPushButton[settingsNav="true"] {{
                min-height: 34px;
                padding: 0 10px;
                color: {Palette.TEXT_DIM};
                background: transparent;
                border: 1px solid transparent;
                text-align: left;
                font-weight: 500;
            }}
            QPushButton[settingsNav="true"]:hover {{
                color: {Palette.TEXT_MAIN};
                background: {Palette.BG_CONTROL_HOVER};
                border-color: transparent;
            }}
            QPushButton[settingsNav="true"]:checked {{
                color: {Palette.TEXT_MAIN};
                background: {Palette.ACCENT_LOW};
                border: 1px solid {Palette.ACCENT_MAIN};
                font-weight: 600;
            }}
            QPushButton[settingsNav="true"]:focus {{
                border: 2px solid {Palette.ACCENT_MAIN};
            }}
            QPushButton[sectionReset="true"] {{
                min-height: 22px;
                padding: 0 6px;
                color: {Palette.TEXT_MUTED};
                background: transparent;
                border: none;
                font-size: 9pt;
            }}
            QPushButton[sectionReset="true"]:hover {{
                color: {Palette.ACCENT_MAIN};
                background: {Palette.ACCENT_LOW};
            }}
            QPushButton#theme_close {{
                min-width: 34px;
                max-width: 34px;
                min-height: 34px;
                max-height: 34px;
                padding: 0;
                background: transparent;
                border: none;
            }}
            QPushButton#theme_close:hover {{
                background: {Palette.BG_CONTROL_HOVER};
            }}
            QPushButton#theme_apply {{
                min-width: 88px;
                min-height: 34px;
                padding: 0 14px;
                color: {Palette.ON_ACCENT};
                background: {Palette.ACCENT_MAIN};
                border-color: {Palette.ACCENT_MAIN};
                font-weight: 600;
            }}
            QPushButton[footerAction="true"] {{
                min-width: 88px;
                min-height: 34px;
                padding: 0 14px;
            }}
            QPushButton#theme_apply:hover {{
                background: {Palette.ACCENT_HOVER};
                border-color: {Palette.ACCENT_HOVER};
            }}
            QComboBox {{
                min-height: 28px;
                padding: 0 40px 0 10px;
                color: {Palette.TEXT_MAIN};
                background: {Palette.BG_INPUT};
                border: 1px solid {Palette.BORDER_DEFAULT};
                border-radius: 5px;
                font-size: 9pt;
            }}
            QComboBox:hover,
            QComboBox:focus {{
                border-color: {Palette.ACCENT_MAIN};
            }}
            QComboBox::drop-down {{
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 32px;
                background: {Palette.BG_CONTROL};
                border: none;
                border-left: 1px solid {Palette.BORDER_DEFAULT};
                border-top-right-radius: 4px;
                border-bottom-right-radius: 4px;
            }}
            QComboBox::drop-down:hover {{
                background: {Palette.BG_CONTROL_HOVER};
            }}
            QComboBox::down-arrow {{
                image: none;
                width: 0;
                height: 0;
            }}
            QComboBox QAbstractItemView {{
                color: {Palette.TEXT_MAIN};
                background: {Palette.BG_POPOVER};
                selection-color: {Palette.ON_ACCENT};
                selection-background-color: {Palette.ACCENT_MAIN};
                border: 1px solid {Palette.BORDER_DEFAULT};
                outline: none;
                padding: 3px;
            }}
            QScrollBar:vertical {{
                width: 10px;
                margin: 0;
                background: {Palette.BG_INPUT};
                border: none;
                border-radius: 5px;
            }}
            QScrollBar::handle:vertical {{
                min-height: 28px;
                margin: 2px;
                background: {Palette.BG_CONTROL_HOVER};
                border-radius: 3px;
            }}
            QScrollBar:horizontal {{
                height: 10px;
                margin: 0;
                background: {Palette.BG_INPUT};
                border: none;
                border-radius: 5px;
            }}
            QScrollBar::handle:horizontal {{
                min-width: 28px;
                margin: 2px;
                background: {Palette.BG_CONTROL_HOVER};
                border-radius: 3px;
            }}
            QScrollBar::handle:hover {{
                background: {Palette.BORDER_HOVER};
            }}
            QScrollBar::add-line,
            QScrollBar::sub-line {{
                width: 0;
                height: 0;
                background: transparent;
                border: none;
            }}
            QScrollBar::add-page,
            QScrollBar::sub-page {{
                background: transparent;
            }}
        """

    @staticmethod
    def get_export_dialog_qss():
        return f"""
            QDialog#export_dialog {{
                background: transparent;
                color: {Palette.TEXT_MAIN};
                font-family: 'Segoe UI', sans-serif;
            }}
            QWidget#export_container {{
                background: {Palette.BG_PANEL};
                border: 1px solid {Palette.BORDER_DEFAULT};
                border-radius: 10px;
            }}
            QWidget#export_header,
            QWidget#export_footer,
            QWidget#export_option_block,
            QWidget#export_password_field {{
                background: transparent;
                border: none;
            }}
            QLabel {{
                color: {Palette.TEXT_DIM};
                background: transparent;
                border: none;
                font-size: 9pt;
            }}
            QLabel#export_title {{
                color: {Palette.TEXT_MAIN};
                font-size: 14pt;
                font-weight: 600;
            }}
            QLabel#export_subtitle,
            QLabel#export_hint,
            QLabel#export_section_hint,
            QLabel#export_summary {{
                color: {Palette.TEXT_MUTED};
            }}
            QLabel#export_section_hint {{
                font-size: 8.5pt;
            }}
            QLabel#export_summary {{
                font-size: 8.5pt;
            }}
            QLabel#export_format_description {{
                color: {Palette.TEXT_MUTED};
                font-size: 8.5pt;
            }}
            QLabel[sectionTitle="true"] {{
                color: {Palette.TEXT_MAIN};
                font-size: 10pt;
                font-weight: 600;
            }}
            QLabel#export_format_extension {{
                min-width: 38px;
                max-width: 38px;
                min-height: 26px;
                max-height: 26px;
                color: {Palette.TEXT_DIM};
                background: transparent;
                border: none;
                font-family: 'Consolas', monospace;
                font-size: 8pt;
                font-weight: 600;
            }}
            QLabel#export_field_label {{
                color: {Palette.TEXT_DIM};
                font-size: 8pt;
            }}
            QLabel#export_validation {{
                color: {Palette.BTN_CANCEL_TEXT};
                background: {Palette.BTN_CANCEL};
                border: 1px solid {Palette.BTN_CANCEL_BORDER};
                border-radius: 5px;
                padding: 8px 10px;
            }}
            QFrame#export_separator {{
                background: {Palette.BORDER_SUBTLE};
                border: none;
                min-height: 1px;
                max-height: 1px;
            }}
            QFrame#export_vertical_separator {{
                background: {Palette.BORDER_SUBTLE};
                border: none;
                min-width: 1px;
                max-width: 1px;
            }}
            QFrame#export_format_grid {{
                background: transparent;
                border: none;
            }}
            QFrame#export_format_choice,
            QFrame#export_options_panel {{
                background: {Palette.BG_INPUT};
                border: 1px solid {Palette.BORDER_DEFAULT};
                border-radius: 6px;
            }}
            QFrame#export_format_choice:hover {{
                background: {Palette.BG_POPOVER};
                border-color: {Palette.BORDER_HOVER};
            }}
            QFrame#export_format_choice[selected="true"] {{
                background: {Palette.ACCENT_LOW};
                border: 2px solid {Palette.ACCENT_MAIN};
            }}
            QRadioButton,
            QCheckBox {{
                color: {Palette.TEXT_MAIN};
                spacing: 8px;
                font-size: 9pt;
            }}
            QRadioButton[formatChoice="true"] {{
                spacing: 0;
                font-weight: 600;
            }}
            QRadioButton:focus,
            QCheckBox:focus {{
                color: {Palette.ACCENT_ULTRA};
            }}
            QRadioButton::indicator,
            QCheckBox::indicator {{
                width: 16px;
                height: 16px;
                border: 1px solid {Palette.BORDER_HOVER};
                background: {Palette.BG_CONTROL};
            }}
            QRadioButton::indicator {{ border-radius: 9px; }}
            QCheckBox::indicator {{ border-radius: 3px; }}
            QRadioButton::indicator:checked {{
                background: {Palette.ACCENT_MAIN};
                border: 1px solid {Palette.ACCENT_MAIN};
                border-radius: 9px;
            }}
            QCheckBox::indicator:checked {{
                background: {Palette.ACCENT_MAIN};
                border-color: {Palette.ACCENT_MAIN};
            }}
            QRadioButton[formatChoice="true"]::indicator,
            QRadioButton[formatChoice="true"]::indicator:checked {{
                width: 0;
                height: 0;
                background: transparent;
                border: none;
            }}
            QLineEdit {{
                min-height: 30px;
                padding: 0 9px;
                color: {Palette.TEXT_MAIN};
                background: {Palette.BG_INPUT};
                border: 1px solid {Palette.BORDER_DEFAULT};
                border-radius: 4px;
                selection-background-color: {Palette.ACCENT_MAIN};
            }}
            QLineEdit:focus {{ border-color: {Palette.ACCENT_MAIN}; }}
            QPushButton {{
                min-height: 30px;
                padding: 0 12px;
                color: {Palette.TEXT_MAIN};
                background: {Palette.BG_CONTROL};
                border: 1px solid {Palette.BORDER_DEFAULT};
                border-radius: 5px;
                font-size: 9pt;
            }}
            QPushButton:hover {{
                background: {Palette.BG_CONTROL_HOVER};
                border-color: {Palette.BORDER_HOVER};
            }}
            QPushButton:pressed {{ background: {Palette.BG_CONTROL_PRESSED}; }}
            QPushButton:focus {{ border: 2px solid {Palette.ACCENT_MAIN}; }}
            QPushButton:checked {{
                background: {Palette.ACCENT_LOW};
                border: 2px solid {Palette.ACCENT_MAIN};
            }}
            QPushButton:disabled {{
                color: {Palette.TEXT_DISABLED};
                background: {Palette.BG_INPUT};
                border-color: {Palette.BORDER_SUBTLE};
            }}
            QPushButton#export_close {{
                min-width: 34px;
                max-width: 34px;
                min-height: 34px;
                max-height: 34px;
                padding: 0;
                background: transparent;
                border: none;
            }}
            QPushButton#export_close:hover {{ background: {Palette.BG_CONTROL_HOVER}; }}
            QPushButton#export_browse {{
                min-width: 104px;
            }}
            QPushButton#export_cancel {{
                min-width: 74px;
            }}
            QPushButton#export_apply {{
                min-width: 104px;
                color: {Palette.ON_ACCENT};
                background: {Palette.ACCENT_MAIN};
                border-color: {Palette.ACCENT_MAIN};
                font-weight: 600;
            }}
            QPushButton#export_apply:hover {{
                background: {Palette.ACCENT_HOVER};
                border-color: {Palette.ACCENT_HOVER};
            }}
        """

    @staticmethod
    def get_title_bar_qss():
        return f"""
            #CustomTitleBar {{
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
                background-color: {Palette.BG_CONTROL};
                color: {Palette.TEXT_MAIN};
            }}
            QMenu {{
                background-color: {Palette.BG_POPOVER};
                color: {Palette.TEXT_MAIN};
                border: 1px solid {Palette.BORDER_DEFAULT};
                font-size: 13px;
                margin-top: 0;
            }}
            QMenu::item {{
                padding: 8px 28px 8px 16px;
            }}
            QMenu::icon {{
                left: 10px;
                width: 16px;
                height: 16px;
            }}
            QMenu::item:selected {{
                background-color: {Palette.BG_CONTROL_HOVER};
                color: {Palette.TEXT_MAIN};
            }}
            QMenu::separator {{
                height: 1px;
                background: {Palette.BORDER_DEFAULT};
                margin: 4px 0;
            }}
            QLabel#window_title {{
                color: {Palette.TEXT_DIM};
                font-family: 'Segoe UI', sans-serif;
                font-size: 12px;
            }}
        """

    @staticmethod
    def get_player_qss():
        """Compatibility style for the legacy widget video player."""
        return f"""
            QDialog {{ background-color: {Palette.BG_CANVAS}; }}
            QWidget {{ color: {Palette.TEXT_MAIN}; }}
        """

    @staticmethod
    def get_player_controls_qss():
        """Compatibility style for the legacy widget player controls."""
        return f"""
            #ControlsContainer {{
                background-color: {Palette.BG_CANVAS};
                border-top: 1px solid {Palette.WHITE_ALPHA_05};
            }}
            QPushButton {{
                background: transparent;
                border: none;
                border-radius: 6px;
                padding: 4px;
            }}
            QPushButton:hover {{
                background: {Palette.WHITE_ALPHA_10};
            }}
            QPushButton:pressed {{
                background: {Palette.WHITE_ALPHA_15};
            }}
            QSlider::groove:horizontal {{
                height: 4px;
                background: {Palette.WHITE_ALPHA_15};
                border-radius: 2px;
            }}
            QSlider::sub-page:horizontal {{
                background: {Palette.SLIDER_TRACK};
                border-radius: 2px;
            }}
            QSlider::handle:horizontal {{
                background: {Palette.SLIDER_HANDLE};
                width: 14px;
                height: 14px;
                margin: -5px 0;
                border-radius: 7px;
            }}
            QSlider::handle:horizontal:hover {{
                background: {Palette.SLIDER_HANDLE_HOVER};
                width: 16px;
                height: 16px;
                margin: -6px 0;
                border-radius: 8px;
            }}
            QLabel {{
                color: {Palette.WHITE_ALPHA_85};
                font-family: 'Segoe UI', sans-serif;
                font-size: 13px;
                font-weight: 500;
            }}
        """

    @staticmethod
    def get_status_bar_qss(type="normal"):
        color = Palette.TEXT_MUTED
        weight = "normal"
        size = "12px"
        padding = "0 10px"

        if type == "secure":
            color = Palette.GREEN_SECURE
            weight = "bold"
        elif type == "accent":
            color = Palette.ACCENT_MAIN
            weight = "bold"
        elif type == "coords":
            color = Palette.TEXT_MUTED
            weight = "bold"
            size = "11px"

        return f"padding: {padding}; color: {color}; font-weight: {weight}; font-size: {size};"
