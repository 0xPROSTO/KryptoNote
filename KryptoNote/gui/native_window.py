import sys
import ctypes
import ctypes.wintypes
from PySide6.QtGui import QCursor

WM_NCCALCSIZE = 0x0083
WM_NCHITTEST = 0x0084
WM_GETMINMAXINFO = 0x0024

HTCLIENT = 1
HTCAPTION = 2
HTLEFT = 10
HTRIGHT = 11
HTTOP = 12
HTTOPLEFT = 13
HTTOPRIGHT = 14
HTBOTTOM = 15
HTBOTTOMLEFT = 16
HTBOTTOMRIGHT = 17
HTMINBUTTON = 8
HTMAXBUTTON = 9
HTCLOSE = 20

WS_THICKFRAME = 0x00040000
WS_CAPTION = 0x00C00000
WS_MAXIMIZEBOX = 0x00010000
WS_MINIMIZEBOX = 0x00020000
GWL_STYLE = -16

DWMWA_EXTENDED_FRAME_BOUNDS = 9

class MARGINS(ctypes.Structure):
    _fields_ = [
        ("cxLeftWidth", ctypes.c_int),
        ("cxRightWidth", ctypes.c_int),
        ("cyTopHeight", ctypes.c_int),
        ("cyBottomHeight", ctypes.c_int),
    ]

class MINMAXINFO(ctypes.Structure):
    _fields_ = [
        ("ptReserved", ctypes.wintypes.POINT),
        ("ptMaxSize", ctypes.wintypes.POINT),
        ("ptMaxPosition", ctypes.wintypes.POINT),
        ("ptMinTrackSize", ctypes.wintypes.POINT),
        ("ptMaxTrackSize", ctypes.wintypes.POINT),
    ]

class NCCALCSIZE_PARAMS(ctypes.Structure):
    _fields_ = [
        ("rgrc", ctypes.wintypes.RECT * 3),
    ]

class NativeWindowMixin:
    RESIZE_BORDER_WIDTH = 6
    TITLE_BAR_HEIGHT = 32

    def init_native_window(self):
        if sys.platform != "win32":
            return

        self._native_initialized = True
        hwnd = int(self.winId())

        style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_STYLE)
        style |= WS_THICKFRAME | WS_CAPTION | WS_MAXIMIZEBOX | WS_MINIMIZEBOX
        ctypes.windll.user32.SetWindowLongW(hwnd, GWL_STYLE, style)

        margins = MARGINS(-1, -1, -1, -1)
        ctypes.windll.dwmapi.DwmExtendFrameIntoClientArea(hwnd, ctypes.byref(margins))

        ctypes.windll.user32.SetWindowPos(
            hwnd, 0, 0, 0, 0, 0,
            0x0001 | 0x0002 | 0x0004 | 0x0020
        )

    def _get_title_bar_widget(self):
        return getattr(self, 'title_bar', None)

    def _is_in_title_bar_buttons(self, global_x, global_y):
        title_bar = self._get_title_bar_widget()
        if not title_bar:
            return None

        for btn_name, ht_value in [
            ('btn_close', HTCLOSE),
            ('btn_maximize', HTMAXBUTTON),
            ('btn_minimize', HTMINBUTTON),
        ]:
            btn = getattr(title_bar, btn_name, None)
            if btn and btn.isVisible():
                btn_rect = btn.rect()
                btn_top_left = btn.mapToGlobal(btn_rect.topLeft())
                btn_bottom_right = btn.mapToGlobal(btn_rect.bottomRight())
                if (btn_top_left.x() <= global_x <= btn_bottom_right.x() and
                        btn_top_left.y() <= global_y <= btn_bottom_right.y()):
                    return ht_value
        return None

    def _is_in_menu_bar(self, global_x, global_y):
        title_bar = self._get_title_bar_widget()
        if not title_bar:
            return False

        menu_bar = getattr(title_bar, 'menu_bar', None)
        if menu_bar and menu_bar.isVisible():
            rect = menu_bar.rect()
            tl = menu_bar.mapToGlobal(rect.topLeft())
            br = menu_bar.mapToGlobal(rect.bottomRight())
            if tl.x() <= global_x <= br.x() and tl.y() <= global_y <= br.y():
                return True
        return False

    def nativeEvent(self, event_type, message):
        if not getattr(self, '_native_initialized', False):
            return super().nativeEvent(event_type, message)

        if event_type == b"windows_generic_MSG":
            msg = ctypes.wintypes.MSG.from_address(int(message))

            if msg.message == WM_NCCALCSIZE:
                if msg.wParam:
                    if ctypes.windll.user32.IsZoomed(msg.hWnd):
                        params = NCCALCSIZE_PARAMS.from_address(msg.lParam)
                        monitor = ctypes.windll.user32.MonitorFromWindow(msg.hWnd, 0x00000002)

                        class MONITORINFO(ctypes.Structure):
                            _fields_ = [
                                ("cbSize", ctypes.wintypes.DWORD),
                                ("rcMonitor", ctypes.wintypes.RECT),
                                ("rcWork", ctypes.wintypes.RECT),
                                ("dwFlags", ctypes.wintypes.DWORD),
                            ]

                        mi = MONITORINFO()
                        mi.cbSize = ctypes.sizeof(MONITORINFO)
                        ctypes.windll.user32.GetMonitorInfoW(monitor, ctypes.byref(mi))

                        params.rgrc[0].left = mi.rcWork.left
                        params.rgrc[0].top = mi.rcWork.top
                        params.rgrc[0].right = mi.rcWork.right
                        params.rgrc[0].bottom = mi.rcWork.bottom

                    return True, 0
                return True, 0

            elif msg.message == WM_NCHITTEST:
                global_pos = QCursor.pos()
                log_x, log_y = global_pos.x(), global_pos.y()
                
                local_pos = self.mapFromGlobal(global_pos)
                local_x, local_y = local_pos.x(), local_pos.y()

                if not ctypes.windll.user32.IsZoomed(msg.hWnd):
                    border = self.RESIZE_BORDER_WIDTH
                    on_left = local_x < border
                    on_right = local_x >= self.width() - border
                    on_top = local_y < border
                    on_bottom = local_y >= self.height() - border

                    if on_top and on_left: return True, HTTOPLEFT
                    if on_top and on_right: return True, HTTOPRIGHT
                    if on_bottom and on_left: return True, HTBOTTOMLEFT
                    if on_bottom and on_right: return True, HTBOTTOMRIGHT
                    if on_left: return True, HTLEFT
                    if on_right: return True, HTRIGHT
                    if on_top: return True, HTTOP
                    if on_bottom: return True, HTBOTTOM

                btn_ht = self._is_in_title_bar_buttons(log_x, log_y)
                if btn_ht is not None: return True, HTCLIENT

                if self._is_in_menu_bar(log_x, log_y): return True, HTCLIENT

                title_bar = self._get_title_bar_widget()
                if title_bar and title_bar.isVisible():
                    tb_rect = title_bar.rect()
                    tb_tl = title_bar.mapToGlobal(tb_rect.topLeft())
                    tb_br = title_bar.mapToGlobal(tb_rect.bottomRight())
                    if (tb_tl.x() <= log_x <= tb_br.x() and tb_tl.y() <= log_y <= tb_br.y()):
                        return True, HTCAPTION

                return True, HTCLIENT

            elif msg.message == WM_GETMINMAXINFO:
                info = MINMAXINFO.from_address(msg.lParam)
                monitor = ctypes.windll.user32.MonitorFromWindow(msg.hWnd, 0x00000002)

                class MONITORINFO(ctypes.Structure):
                    _fields_ = [
                        ("cbSize", ctypes.wintypes.DWORD),
                        ("rcMonitor", ctypes.wintypes.RECT),
                        ("rcWork", ctypes.wintypes.RECT),
                        ("dwFlags", ctypes.wintypes.DWORD),
                    ]

                mi = MONITORINFO()
                mi.cbSize = ctypes.sizeof(MONITORINFO)
                ctypes.windll.user32.GetMonitorInfoW(monitor, ctypes.byref(mi))

                work = mi.rcWork
                info.ptMaxSize.x = work.right - work.left
                info.ptMaxSize.y = work.bottom - work.top
                info.ptMaxPosition.x = work.left - mi.rcMonitor.left
                info.ptMaxPosition.y = work.top - mi.rcMonitor.top
                info.ptMinTrackSize.x = self.minimumWidth()
                info.ptMinTrackSize.y = self.minimumHeight()

                return True, 0

        return super().nativeEvent(event_type, message)
