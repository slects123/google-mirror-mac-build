# -*- coding: utf-8 -*-
"""自助框架教程 - 精简投屏软件（白色主题）"""

import base64
import os
import re
import sys
import time
import zipfile
import subprocess
import threading
import urllib.parse
from pathlib import Path

IS_WIN = sys.platform == "win32"
IS_MAC = sys.platform == "darwin"
if IS_WIN:
    import ctypes
    from ctypes import wintypes

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QCheckBox, QListWidget, QLineEdit, QTextEdit,
    QLabel, QMessageBox, QInputDialog, QStackedWidget,
    QListWidgetItem, QFrame, QSizePolicy, QDialog, QScrollArea
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QObject, QEvent, QPoint
from PyQt6.QtGui import QTextCursor, QPalette, QColor, QIcon, QKeyEvent

try:
    from licenses_data import LICENSE_MAP, UNLIMITED_KEYS
except ImportError:
    LICENSE_MAP = {}
    UNLIMITED_KEYS = set()

from license_usage import (
    refresh_license_maps,
    ensure_key_bound,
    try_consume_key_with_info,
    try_consume_password,
    format_usage_lines,
)

if getattr(sys, "frozen", False):
    ROOT = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
else:
    ROOT = Path(__file__).parent
BUNDLE_ROOT = ROOT


def _tool_path(name):
    return ROOT / (f"{name}.exe" if IS_WIN else name)


ADB = _tool_path("adb")
SCRCPY = _tool_path("scrcpy")
SCRCPY_SERVER = ROOT / "scrcpy-server"

KEYCODE_HOME = 3
KEYCODE_BACK = 4
KEYCODE_APP_SWITCH = 187
KEYCODE_DEL = 67
KEYCODE_FORWARD_DEL = 112
KEYCODE_ENTER = 66
KEYCODE_SPACE = 62
KEYCODE_TAB = 61
KEYCODE_ESCAPE = 111

QT_KEY_TO_ANDROID = {
    Qt.Key.Key_Backspace: KEYCODE_DEL,
    Qt.Key.Key_Delete: KEYCODE_FORWARD_DEL,
    Qt.Key.Key_Return: KEYCODE_ENTER,
    Qt.Key.Key_Enter: KEYCODE_ENTER,
    Qt.Key.Key_Escape: KEYCODE_BACK,
    Qt.Key.Key_Tab: KEYCODE_TAB,
    Qt.Key.Key_Home: KEYCODE_HOME,
    Qt.Key.Key_End: 123,
    Qt.Key.Key_PageUp: 92,
    Qt.Key.Key_PageDown: 93,
    Qt.Key.Key_Left: 21,
    Qt.Key.Key_Up: 19,
    Qt.Key.Key_Right: 22,
    Qt.Key.Key_Down: 20,
    Qt.Key.Key_Space: KEYCODE_SPACE,
}

DRIVER_INSTALL_CANDIDATES = [
    ROOT / "drivers" / "安装USB驱动.exe",
    ROOT / "drivers" / "UniversalAdbDriverSetup.msi",
    ROOT / "drivers" / "安装驱动.exe",
    ROOT / "drivers" / "driver_install.exe",
    ROOT / "drivers" / "usb_driver" / "android_winusb.inf",
]

BACKUP_SRC = ROOT / "Software" / "Backup"
PHONE_HUAWEI_DIR = "/sdcard/Huawei"
GOOGLE_HELPER_NAME = "谷歌服务助手"
GOOGLE_HELPER_PACKAGE = "com.lzplay.helper"
GOOGLE_STORE_NAME = "谷歌商店"
GOOGLE_PLAY_PACKAGE = "com.android.vending"
GSF_PACKAGE = "com.google.android.gsf"
GOOGLE_ACCOUNT_APK = ROOT / "Software" / "1.apk"
GOOGLE_FRAMEWORK_APKS = {
    "v10": ROOT / "Software" / "2v10.apk",
    "v12": ROOT / "Software" / "2v12.apk",
}
GOOGLE_SERVICE_APK = ROOT / "Software" / "3.apk"
GOOGLE_STORE_APK = ROOT / "Software" / "4.apk"
FLCLASH_APK = ROOT / "Software" / "flclash.apk"
FLCLASH_PACKAGE = "com.follow.clash"
_FLCLASH_SUB_URL_DATA = (
    "aHR0cHM6Ly9kYXNoLnBxamMuc2l0ZS9hcGkvdjEvcHEvZGM0NGJmNDg2YTA2YTI3"
    "NTNjNmIzYmE3ODE0NTM1OWM="
)
FLCLASH_SUBSCRIBE_PASSWORD = "tbvip888"

AFTER_SALE_NOTES = """有4点注意事项
1.不要清理所有关于google的数据
2.不要升级华为鸿蒙5以上系统
3.不要恢复手机出厂设置
4.不要在除了安装手机外的地方修改你的谷歌账号密码
5.不可添加谷歌账号

后续如果没有问题  麻烦再淘宝给个五星好评  非常感谢
售后微信: tui65743
后续 您如果需要  vpn魔术上网  以及各种类型的账号  可以联系我tui65743
"""


def _desktop_dir():
    home = Path.home()
    for name in ("Desktop", "桌面"):
        path = home / name
        if path.is_dir():
            return path
    return home


def _open_path(path):
    path = Path(path)
    if IS_WIN:
        os.startfile(str(path))
    elif IS_MAC:
        subprocess.run(["open", str(path)], check=False)
    else:
        subprocess.run(["xdg-open", str(path)], check=False)


MIRROR_PAGE_BASE_W = 280
MIRROR_PAGE_BASE_H = 498
SIDE_PANEL_W = MIRROR_PAGE_BASE_W + 100
MIRROR_SCREEN_W = 280
MIRROR_SCREEN_H = 622
MIRROR_PHONE_FRAME_PAD = 16
MIRROR_PHONE_FRAME_W = MIRROR_SCREEN_W + MIRROR_PHONE_FRAME_PAD
MIRROR_PHONE_FRAME_H = MIRROR_SCREEN_H + MIRROR_PHONE_FRAME_PAD
MIRROR_PANEL_FIXED_W = MIRROR_PHONE_FRAME_W + 24
MIRROR_PANEL_FIXED_H = MIRROR_PHONE_FRAME_H + 110
APP_WINDOW_W = SIDE_PANEL_W + MIRROR_PANEL_FIXED_W + 38
APP_WINDOW_H = MIRROR_PANEL_FIXED_H + 66
MIRROR_FIXED = {
    "conn_btn": (164, 54),
    "device_list": (336, 72),
    "ctrl_btn": (86, 28),
    "refresh_btn": (60, 28),
    "quick_btn": (108, 26),
    "quick_btn_wide": (164, 26),
    "input": (336, 26),
    "adb_btn": (50, 26),
    "log": (336, 96),
}


def _get_flclash_subscribe_url():
    return base64.b64decode(_FLCLASH_SUB_URL_DATA).decode("utf-8")
GMS_UNINSTALL_APKS = (
    GOOGLE_ACCOUNT_APK,
    GOOGLE_FRAMEWORK_APKS["v10"],
    GOOGLE_FRAMEWORK_APKS["v12"],
    GOOGLE_SERVICE_APK,
    GOOGLE_STORE_APK,
)
APK_PACKAGE_FALLBACKS = {
    "1.apk": [],
    "2v10.apk": ["com.google.android.gsf"],
    "2v12.apk": ["com.google.android.gsf"],
    "3.apk": ["com.google.android.gms"],
    "4.apk": [GOOGLE_PLAY_PACKAGE],
}

SUBPROCESS_FLAGS = {}
if IS_WIN:
    SUBPROCESS_FLAGS["creationflags"] = subprocess.CREATE_NO_WINDOW


class LogSignal(QObject):
    append = pyqtSignal(str)
    transfer_done = pyqtSignal(bool, str)
    date_change_done = pyqtSignal()
    activate_guide = pyqtSignal()
    google_account_install_done = pyqtSignal(bool, str)
    google_framework_install_done = pyqtSignal(bool, str, str)
    google_service_install_done = pyqtSignal(bool, str)
    google_store_install_done = pyqtSignal(bool, str)
    login_google_guide = pyqtSignal()
    refresh_google_guide = pyqtSignal()
    stabilize_framework_done = pyqtSignal(bool, str)
    uninstall_gms_done = pyqtSignal(bool, str)
    flclash_install_done = pyqtSignal(bool, str)
    flclash_subscribe_done = pyqtSignal(bool, str)
    flclash_uninstall_done = pyqtSignal(bool, str)

# 2019-01-01 00:00:00 (北京时间)
TARGET_DATE_MS = "1546272000000"


def calc_fit_rect(container_w, container_h, dev_w, dev_h):
    if dev_w <= 0 or dev_h <= 0:
        dev_w, dev_h = 1080, 2400
    ratio = dev_w / dev_h
    if container_w / container_h > ratio:
        h = container_h
        w = int(h * ratio)
    else:
        w = container_w
        h = int(w / ratio)
    return (container_w - w) // 2, (container_h - h) // 2, w, h


def _set_window_owner(hwnd, owner_hwnd):
    if not IS_WIN or not hwnd:
        return
    user32 = ctypes.windll.user32
    user32.SetParent(hwnd, 0)
    if ctypes.sizeof(ctypes.c_void_p) == 8:
        user32.SetWindowLongPtrW(hwnd, -8, owner_hwnd or 0)
    else:
        user32.SetWindowLongW(hwnd, -8, owner_hwnd or 0)


def _configure_scrcpy_overlay(hwnd, owner_hwnd):
    if not IS_WIN or not hwnd:
        return
    user32 = ctypes.windll.user32
    style = user32.GetWindowLongW(hwnd, -16)
    style = (style & ~(0x00C00000 | 0x00040000 | 0x00800000)) | 0x80000000 | 0x10000000
    user32.SetWindowLongW(hwnd, -16, style)
    ex_style = user32.GetWindowLongW(hwnd, -20)
    user32.SetWindowLongW(hwnd, -20, ex_style | 0x08000000)
    _set_window_owner(hwnd, owner_hwnd)


def _move_scrcpy_overlay(hwnd, x, y, width, height):
    if not IS_WIN or not hwnd or width < 1 or height < 1:
        return
    ctypes.windll.user32.SetWindowPos(hwnd, 0, x, y, width, height, 0x0014)


def _detach_scrcpy_overlay(hwnd):
    if not IS_WIN or not hwnd:
        return
    _set_window_owner(hwnd, 0)
    ctypes.windll.user32.ShowWindow(hwnd, 0)


def find_scrcpy_hwnd(pid, title_hint=None, exclude=()):
    if not IS_WIN:
        return None
    user32 = ctypes.windll.user32
    best = None
    best_area = 0
    title_buf = ctypes.create_unicode_buffer(512)

    def enum_cb(hwnd, _):
        nonlocal best, best_area
        if hwnd in exclude:
            return True
        proc_id = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(proc_id))
        if proc_id.value != pid or not user32.IsWindowVisible(hwnd):
            return True
        if title_hint:
            user32.GetWindowTextW(hwnd, title_buf, 512)
            if title_hint not in title_buf.value:
                return True
        rect = wintypes.RECT()
        user32.GetWindowRect(hwnd, ctypes.byref(rect))
        area = (rect.right - rect.left) * (rect.bottom - rect.top)
        if area > best_area:
            best_area = area
            best = hwnd
        return True

    cb = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)(enum_cb)
    user32.EnumWindows(cb, 0)
    return best


def _focus_native_window(hwnd):
    if not IS_WIN or not hwnd:
        return
    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32
    foreground = user32.GetForegroundWindow()
    fg_thread = user32.GetWindowThreadProcessId(foreground, None)
    cur_thread = kernel32.GetCurrentThreadId()
    attached = False
    if fg_thread and fg_thread != cur_thread:
        attached = bool(user32.AttachThreadInput(cur_thread, fg_thread, True))
    try:
        user32.ShowWindow(hwnd, 5)
        user32.SetForegroundWindow(hwnd)
        user32.SetFocus(hwnd)
    finally:
        if attached:
            user32.AttachThreadInput(cur_thread, fg_thread, False)


class MirrorWindow(QMainWindow):
    def __init__(self, license_key=None):
        super().__init__()
        self.license_key = license_key
        self.setWindowTitle("谷歌框架远程操作")
        self.setWindowIcon(_app_icon())
        self.apply_white_theme()
        self._last_mirror_size = None
        self._last_overlay_rect = None
        self._overlay_configured = False
        self._mirror_kb_armed = False
        self._mirror_kb_prev = ""

        self.devices = []
        self.current_serial = None
        self.scrcpy_proc = None
        self.scrcpy_qwindow = None
        self.scrcpy_embed_widget = None
        self.scrcpy_hwnd = None
        self.embed_attempts = 0
        self.device_w = 1080
        self.device_h = 2400
        self.mirroring = False
        self.mirror_page = None
        self._mirror_scale_items = []
        self._mirror_scale_fonts = None

        self.log_signal = LogSignal()
        self._connect_log_signals()

        self.embed_timer = QTimer()
        self.embed_timer.timeout.connect(self._try_embed_scrcpy)
        self.proc_timer = QTimer()
        self.proc_timer.timeout.connect(self._check_scrcpy_alive)
        self.device_refresh_timer = QTimer()
        self.device_refresh_timer.timeout.connect(
            lambda: self.refresh_devices(quiet=True)
        )

        self._build_ui()
        self.refresh_devices()
        self.device_refresh_timer.start(2000)

    def _connect_log_signals(self):
        """连接日志信号，启动前校验回调方法是否存在。"""
        bindings = (
            (self.log_signal.append, "_append_log"),
            (self.log_signal.transfer_done, "_on_transfer_done"),
            (self.log_signal.date_change_done, "_on_date_change_done"),
            (self.log_signal.activate_guide, "_show_activate_guide"),
            (self.log_signal.google_account_install_done, "_on_google_account_install_done"),
            (self.log_signal.google_framework_install_done, "_on_google_framework_install_done"),
            (self.log_signal.google_service_install_done, "_on_google_service_install_done"),
            (self.log_signal.google_store_install_done, "_on_google_store_install_done"),
            (self.log_signal.login_google_guide, "_show_login_google_guide"),
            (self.log_signal.refresh_google_guide, "_show_refresh_google_guide"),
            (self.log_signal.stabilize_framework_done, "_on_stabilize_framework_done"),
            (self.log_signal.uninstall_gms_done, "_on_uninstall_gms_done"),
            (self.log_signal.flclash_install_done, "_on_flclash_install_done"),
            (self.log_signal.flclash_subscribe_done, "_on_flclash_subscribe_done"),
            (self.log_signal.flclash_uninstall_done, "_on_flclash_uninstall_done"),
        )
        for signal, method_name in bindings:
            if not hasattr(self, method_name):
                raise RuntimeError(f"程序缺少回调方法: {method_name}")
            signal.connect(getattr(self, method_name))

    def apply_white_theme(self):
        pal = self.palette()
        pal.setColor(QPalette.ColorRole.Window, QColor("#f3f6fb"))
        pal.setColor(QPalette.ColorRole.Base, QColor("#ffffff"))
        pal.setColor(QPalette.ColorRole.Text, QColor("#1f2937"))
        pal.setColor(QPalette.ColorRole.Button, QColor("#ffffff"))
        pal.setColor(QPalette.ColorRole.ButtonText, QColor("#1f2937"))
        self.setPalette(pal)
        self.setStyleSheet("""
            QMainWindow { background: #f3f6fb; color: #1f2937; font-size: 13px; }
            QStackedWidget { background: #ffffff; }
            QScrollArea { border: none; background: #ffffff; }
            QFrame#SidePanel { background: #eef2f8; border-radius: 12px; }
            QFrame#ContentCard {
                background: #ffffff; border: 1px solid #e3e8f0; border-radius: 12px;
            }
            QFrame#SectionCard {
                background: #f8fafc; border: 1px solid #e5e7eb; border-radius: 10px;
            }
            QFrame#MirrorPanel {
                background: #ffffff; border: 1px solid #e3e8f0; border-radius: 12px;
            }
            QWidget#MirrorViewport {
                background: #f1f5f9; border-radius: 10px;
            }
            QFrame#MirrorPhoneFrame {
                background: #0f172a; border: 2px solid #334155; border-radius: 18px;
            }
            QWidget#MirrorScreen {
                background: #000000; border-radius: 10px;
            }
            QLabel#MirrorPanelTitle {
                font-size: 14px; font-weight: bold; color: #111827;
            }
            QLabel#MirrorPanelDevice {
                font-size: 11px; color: #6b7280;
            }
            QLabel#MirrorPanelFooter {
                font-size: 11px; color: #9ca3af;
            }
            QLabel#PageTitle { font-size: 18px; font-weight: bold; color: #111827; }
            QLabel#PageSubtitle { font-size: 12px; color: #6b7280; }
            QLabel#SectionLabel {
                font-size: 12px; font-weight: bold; color: #4b5563;
                padding-bottom: 2px;
            }
            QLabel#MirrorHint {
                font-size: 15px; color: #9ca3af; line-height: 1.5;
            }
            QPushButton {
                min-height: 30px; font-size: 12px; color: #1f2937;
            }
            QPushButton#AppPrimaryBtn {
                background: #1a73e8; color: #ffffff; border: none;
                border-radius: 8px; padding: 8px 14px; font-weight: bold;
            }
            QPushButton#AppPrimaryBtn:hover { background: #1666cf; }
            QPushButton#AppPrimaryBtn:pressed { background: #1256ad; }
            QPushButton#AppAccentBtn {
                background: #0f9d58; color: #ffffff; border: none;
                border-radius: 8px; padding: 9px 16px; font-weight: bold;
            }
            QPushButton#AppAccentBtn:hover { background: #0d8a4d; }
            QPushButton#AppSecondaryBtn {
                background: #e8f1fd; color: #1a56c6; border: 1px solid #c7dcfa;
                border-radius: 8px; padding: 9px 14px; font-weight: bold;
            }
            QPushButton#AppSecondaryBtn:hover { background: #dbeafe; }
            QPushButton#AppGhostBtn {
                background: #ffffff; color: #374151; border: 1px solid #d1d5db;
                border-radius: 8px; padding: 8px 14px;
            }
            QPushButton#AppGhostBtn:hover { background: #f9fafb; }
            QPushButton#AppDangerBtn {
                background: #fff1f2; color: #be123c; border: 1px solid #fecdd3;
                border-radius: 8px; padding: 8px 14px;
            }
            QPushButton#AppDangerBtn:hover { background: #ffe4e6; }
            QFrame#ConnStepCard {
                background: #ffffff; border: 1px solid #dbeafe;
                border-radius: 10px;
            }
            QLabel#ConnStepBadge {
                background: #1a73e8; color: #ffffff;
                border-radius: 4px; padding: 2px 8px;
                font-size: 11px; font-weight: bold;
            }
            QLabel#ConnStepHint { color: #6b7280; font-size: 11px; }
            QLabel#ConnStatus {
                color: #374151; font-size: 11px;
                background: #f8fafc; border: 1px solid #e5e7eb;
                border-radius: 6px; padding: 6px 8px;
            }
            QPushButton#ConnWifiBtn {
                background: #eff6ff; color: #1d4ed8;
                border: 2px solid #93c5fd; border-radius: 10px;
                padding: 4px 6px; font-weight: bold;
            }
            QPushButton#ConnWifiBtn:hover {
                background: #dbeafe; border: 2px solid #60a5fa;
            }
            QPushButton#ConnUsbBtn {
                background: #1a73e8; color: #ffffff;
                border: 2px solid #1a73e8; border-radius: 10px;
                padding: 4px 6px; font-weight: bold;
            }
            QPushButton#ConnUsbBtn:hover { background: #1666cf; }
            QPushButton#TutorialBtn {
                background: #ffffff; color: #1f2937; border: 1px solid #e5e7eb;
                border-radius: 8px; padding: 10px 12px; text-align: left;
            }
            QPushButton#TutorialBtn:hover {
                background: #f0f7ff; border: 1px solid #bfdbfe; color: #1a56c6;
            }
            QLineEdit, QTextEdit {
                background: #ffffff; border: 1px solid #d1d5db;
                border-radius: 8px; padding: 8px 10px; color: #111827;
            }
            QLineEdit:focus, QTextEdit:focus { border: 1px solid #1a73e8; }
            QListWidget {
                background: #ffffff; border: 1px solid #d1d5db;
                border-radius: 8px; outline: none;
            }
            QListWidget::item { padding: 8px 10px; border-bottom: 1px solid #f3f4f6; }
            QListWidget::item:selected { background: #e8f1fd; color: #1a56c6; }
            QListWidget::item:hover { background: #f3f4f6; }
            QCheckBox { color: #4b5563; spacing: 8px; }
            QCheckBox::indicator {
                width: 16px; height: 16px; border-radius: 4px;
                border: 1px solid #cbd5e1; background: #ffffff;
            }
            QCheckBox::indicator:checked {
                background: #1a73e8; border: 1px solid #1a73e8;
            }
            QStatusBar {
                background: #ffffff; color: #6b7280;
                border-top: 1px solid #e5e7eb;
            }
            QSplitter::handle { background: #e5e7eb; width: 2px; }
            QListWidget#navList {
                background: transparent; border: none; outline: none;
            }
            QListWidget#navList::item {
                padding: 14px 10px; margin: 4px 6px; border-radius: 8px;
                color: #4b5563; font-weight: bold;
            }
            QListWidget#navList::item:selected {
                background: #1a73e8; color: #ffffff;
            }
            QListWidget#navList::item:hover:!selected { background: #e5e7eb; }
            QPushButton#NavActionBtn {
                background: #ffffff; color: #1f2937; border: 1px solid #d1d5db;
                border-radius: 8px; padding: 8px 6px; font-size: 12px;
            }
            QPushButton#NavActionBtn:hover {
                background: #f0f7ff; border: 1px solid #bfdbfe; color: #1a56c6;
            }
        """)

    def _action_button(self, text, role="ghost", fixed=False):
        btn = QPushButton(text)
        role_map = {
            "primary": "AppPrimaryBtn",
            "accent": "AppAccentBtn",
            "secondary": "AppSecondaryBtn",
            "ghost": "AppGhostBtn",
            "danger": "AppDangerBtn",
            "tutorial": "TutorialBtn",
        }
        btn.setObjectName(role_map.get(role, "AppGhostBtn"))
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        if fixed:
            btn.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        else:
            btn.setMinimumHeight(30)
            btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        return btn

    def _fixed_button(self, text, role, width, height):
        btn = self._action_button(text, role, fixed=True)
        btn.setFixedSize(width, height)
        self._register_mirror_scale(btn, width, height)
        return btn

    def _conn_link_button(self, title, subtitle, kind, width, height):
        btn = QPushButton(f"{title}\n{subtitle}")
        btn.setObjectName("ConnWifiBtn" if kind == "wifi" else "ConnUsbBtn")
        btn.setFixedSize(width, height)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self._register_mirror_scale(btn, width, height)
        return btn

    def _set_conn_status(self, text):
        if hasattr(self, "conn_status_label"):
            self.conn_status_label.setText(text)

    def _build_connection_step(self):
        card = QFrame()
        card.setObjectName("ConnStepCard")
        lay = QVBoxLayout(card)
        lay.setContentsMargins(10, 10, 10, 10)
        lay.setSpacing(8)

        title_row = QHBoxLayout()
        badge = QLabel("第1步")
        badge.setObjectName("ConnStepBadge")
        title = QLabel("连接设备")
        title.setObjectName("SectionLabel")
        title_row.addWidget(badge)
        title_row.addWidget(title)
        title_row.addStretch()
        lay.addLayout(title_row)

        hint = QLabel("先选连接方式：WiFi 需配对码，USB 需插数据线并开调试")
        hint.setObjectName("ConnStepHint")
        hint.setWordWrap(True)
        lay.addWidget(hint)

        cw, ch = MIRROR_FIXED["conn_btn"]
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        self.btn_wifi_conn = self._conn_link_button("WiFi连接", "无线配对", "wifi", cw, ch)
        self.btn_usb_conn = self._conn_link_button("USB连接", "数据线连接", "usb", cw, ch)
        self.btn_wifi_conn.clicked.connect(self._on_wifi_conn_click)
        self.btn_usb_conn.clicked.connect(self._on_usb_conn_click)
        btn_row.addWidget(self.btn_wifi_conn)
        btn_row.addWidget(self.btn_usb_conn)
        lay.addLayout(btn_row)

        self.conn_status_label = QLabel("状态：等待连接（连接后点「刷新」查看设备）")
        self.conn_status_label.setObjectName("ConnStatus")
        self.conn_status_label.setWordWrap(True)
        lay.addWidget(self.conn_status_label)
        return card

    def _on_wifi_conn_click(self):
        self._set_conn_status("状态：正在配置 WiFi 无线连接...")
        self.wifi_connect()

    def _on_usb_conn_click(self):
        self._set_conn_status("状态：正在检测 USB 设备，请确认已开启 USB 调试...")
        self.usb_connect()

    def _register_mirror_scale(self, widget, width, height):
        self._mirror_scale_items.append({"widget": widget, "w": width, "h": height})

    def _scale_mirror_layout(self):
        if not self.mirror_page:
            return
        margin = 16
        scale = min(
            (self.mirror_page.width() - margin) / MIRROR_PAGE_BASE_W,
            (self.mirror_page.height() - margin) / MIRROR_PAGE_BASE_H,
        )
        scale = max(0.85, min(scale, 1.2))
        for item in self._mirror_scale_items:
            widget = item["widget"]
            widget.setFixedSize(int(item["w"] * scale), int(item["h"] * scale))
        if self._mirror_scale_fonts:
            title_px = max(13, int(self._mirror_scale_fonts["title"] * scale))
            section_px = max(10, int(self._mirror_scale_fonts["section"] * scale))
            body_px = max(10, int(self._mirror_scale_fonts["body"] * scale))
            self.mirror_page.setStyleSheet(f"""
                QLabel#PageTitle {{ font-size: {title_px}px; font-weight: bold; }}
                QLabel#SectionLabel {{ font-size: {section_px}px; font-weight: bold; }}
                QPushButton {{ font-size: {body_px}px; }}
                QLineEdit, QTextEdit, QListWidget {{ font-size: {body_px}px; }}
                QCheckBox {{ font-size: {body_px}px; }}
            """)

    def _section_frame(self, compact=False):
        frame = QFrame()
        frame.setObjectName("SectionCard")
        layout = QVBoxLayout(frame)
        if compact:
            layout.setContentsMargins(8, 6, 8, 6)
            layout.setSpacing(5)
        else:
            layout.setContentsMargins(12, 12, 12, 12)
            layout.setSpacing(8)
        return frame, layout

    def _compact_page_header(self, title):
        wrap = QWidget()
        layout = QVBoxLayout(wrap)
        layout.setContentsMargins(0, 0, 0, 2)
        title_lbl = QLabel(title)
        title_lbl.setObjectName("PageTitle")
        layout.addWidget(title_lbl)
        return wrap

    def _page_header(self, title, subtitle=""):
        wrap = QWidget()
        layout = QVBoxLayout(wrap)
        layout.setContentsMargins(4, 2, 4, 10)
        layout.setSpacing(2)
        title_lbl = QLabel(title)
        title_lbl.setObjectName("PageTitle")
        layout.addWidget(title_lbl)
        if subtitle:
            sub_lbl = QLabel(subtitle)
            sub_lbl.setObjectName("PageSubtitle")
            sub_lbl.setWordWrap(True)
            layout.addWidget(sub_lbl)
        return wrap

    def _section_label(self, text):
        lbl = QLabel(text)
        lbl.setObjectName("SectionLabel")
        return lbl

    def _wrap_scroll_page(self, title, subtitle, content_widget):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)
        layout.addWidget(self._page_header(title, subtitle))
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setWidget(content_widget)
        layout.addWidget(scroll, 1)
        return page

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(14, 14, 14, 10)
        layout.setSpacing(10)

        body_row = QHBoxLayout()
        body_row.setSpacing(10)
        body_row.setContentsMargins(0, 0, 0, 0)

        side_panel = QFrame()
        side_panel.setObjectName("SidePanel")
        side_panel.setFixedSize(SIDE_PANEL_W, MIRROR_PANEL_FIXED_H)
        side_layout = QHBoxLayout(side_panel)
        side_layout.setContentsMargins(6, 6, 6, 6)
        side_layout.setSpacing(6)

        nav_column = QWidget()
        nav_column.setFixedWidth(88)
        nav_column_layout = QVBoxLayout(nav_column)
        nav_column_layout.setContentsMargins(0, 0, 0, 0)
        nav_column_layout.setSpacing(6)

        self.nav_list = QListWidget()
        self.nav_list.setObjectName("navList")
        for name in ["投屏界面", "安装教程", "其他服务"]:
            self.nav_list.addItem(QListWidgetItem(name))
        self.nav_list.setCurrentRow(0)
        self.nav_list.currentRowChanged.connect(self.on_nav_changed)
        nav_column_layout.addWidget(self.nav_list, 1)

        for text, keycode in (
            ("打开后台", KEYCODE_APP_SWITCH),
            ("返回桌面", KEYCODE_HOME),
            ("返回一步", KEYCODE_BACK),
        ):
            btn = QPushButton(text)
            btn.setObjectName("NavActionBtn")
            btn.setFixedHeight(34)
            btn.clicked.connect(
                lambda _checked=False, k=keycode, m=text: self.send_phone_key(k, m)
            )
            nav_column_layout.addWidget(btn)

        side_layout.addWidget(nav_column)

        content_card = QFrame()
        content_card.setObjectName("ContentCard")
        content_card_layout = QVBoxLayout(content_card)
        content_card_layout.setContentsMargins(0, 0, 0, 0)
        self.page_stack = QStackedWidget()
        self.page_stack.addWidget(self._build_mirror_page())
        self.page_stack.addWidget(self._build_install_tutorial_page())
        self.page_stack.addWidget(self._build_other_services_page())
        content_card_layout.addWidget(self.page_stack)
        side_layout.addWidget(content_card, 1)
        body_row.addWidget(side_panel)

        self.mirror_container = QFrame()
        self.mirror_container.setObjectName("MirrorPanel")
        self.mirror_container.setFixedSize(MIRROR_PANEL_FIXED_W, MIRROR_PANEL_FIXED_H)
        self.mirror_layout = QVBoxLayout(self.mirror_container)
        self.mirror_layout.setContentsMargins(12, 12, 12, 10)
        self.mirror_layout.setSpacing(8)

        mirror_header = QWidget()
        mirror_header_lay = QHBoxLayout(mirror_header)
        mirror_header_lay.setContentsMargins(2, 0, 2, 0)
        self.mirror_title = QLabel("投屏画面")
        self.mirror_title.setObjectName("MirrorPanelTitle")
        self.mirror_device_label = QLabel("等待连接")
        self.mirror_device_label.setObjectName("MirrorPanelDevice")
        mirror_header_lay.addWidget(self.mirror_title)
        mirror_header_lay.addStretch()
        mirror_header_lay.addWidget(self.mirror_device_label)
        mirror_header.setFixedHeight(28)
        self.mirror_layout.addWidget(mirror_header)

        self.mirror_viewport = QWidget()
        self.mirror_viewport.setObjectName("MirrorViewport")
        self.mirror_viewport.setFixedSize(MIRROR_PHONE_FRAME_W, MIRROR_PHONE_FRAME_H)
        viewport_lay = QVBoxLayout(self.mirror_viewport)
        viewport_lay.setContentsMargins(0, 0, 0, 0)
        viewport_lay.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.mirror_phone_frame = QFrame()
        self.mirror_phone_frame.setObjectName("MirrorPhoneFrame")
        phone_lay = QVBoxLayout(self.mirror_phone_frame)
        phone_lay.setContentsMargins(8, 8, 8, 8)
        phone_lay.setSpacing(0)
        phone_lay.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.mirror_embed_holder = QWidget()
        self.mirror_embed_holder.setObjectName("MirrorScreen")
        self.mirror_embed_holder.setSizePolicy(
            QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed
        )
        self.mirror_holder_layout = QVBoxLayout(self.mirror_embed_holder)
        self.mirror_holder_layout.setContentsMargins(0, 0, 0, 0)
        self.mirror_holder_layout.setSpacing(0)
        self.mirror_holder_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.mirror_hint = QLabel(
            "连接手机后开始投屏\n\n"
            "点击左侧「检测手机链接」\n"
            "画面将显示在此手机框内"
        )
        self.mirror_hint.setObjectName("MirrorHint")
        self.mirror_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.mirror_hint.setWordWrap(True)

        self.mirror_stack = QStackedWidget()
        self.mirror_stack.addWidget(self.mirror_hint)
        self.mirror_stack.addWidget(self.mirror_embed_holder)
        phone_lay.addWidget(self.mirror_stack, 0, Qt.AlignmentFlag.AlignCenter)
        viewport_lay.addWidget(self.mirror_phone_frame, 0, Qt.AlignmentFlag.AlignCenter)
        self.mirror_layout.addWidget(self.mirror_viewport, 0, Qt.AlignmentFlag.AlignHCenter)

        self.mirror_kb_input = QLineEdit()
        self.mirror_kb_input.setPlaceholderText("在此输入文字（实时同步到手机）")
        self.mirror_kb_input.setFixedHeight(28)
        self.mirror_kb_input.returnPressed.connect(self._send_mirror_kb_input)
        self.mirror_kb_input.textChanged.connect(self._on_mirror_kb_text_changed)
        self.mirror_layout.addWidget(self.mirror_kb_input)

        self.mirror_footer = QLabel("或先点投屏画面，再直接打字")
        self.mirror_footer.setObjectName("MirrorPanelFooter")
        self.mirror_footer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.mirror_footer.setFixedHeight(20)
        self.mirror_layout.addWidget(self.mirror_footer)

        body_row.addWidget(self.mirror_container)
        layout.addLayout(body_row)
        self.statusBar().showMessage("谷歌框架远程操作 · 精简投屏")
        self._lock_window_size()
        QTimer.singleShot(0, self._apply_mirror_viewport_size_fixed)

        for w in (
            self.mirror_container, self.mirror_viewport, self.mirror_phone_frame,
            self.mirror_embed_holder, self.mirror_stack,
        ):
            w.installEventFilter(self)
        self.mirror_container.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.mirror_kb_input.installEventFilter(self)
        self.page_stack.installEventFilter(self)
        self.nav_list.installEventFilter(self)

    def _mirror_input_targets(self):
        targets = [
            self.mirror_container, self.mirror_viewport, self.mirror_phone_frame,
            self.mirror_embed_holder, self.mirror_stack,
        ]
        if self.scrcpy_embed_widget:
            targets.append(self.scrcpy_embed_widget)
        return targets

    def _focus_mirror_keyboard(self):
        """键盘走 ADB 转发，焦点留在 Qt 容器上，避免被嵌入的 scrcpy 窗口吞键。"""
        self.activateWindow()
        self.mirror_container.setFocus(Qt.FocusReason.OtherFocusReason)

    def _focus_scrcpy_window(self):
        if IS_WIN and self.scrcpy_hwnd:
            _focus_native_window(self.scrcpy_hwnd)
        if self.scrcpy_embed_widget:
            self.scrcpy_embed_widget.setFocus(Qt.FocusReason.MouseFocusReason)

    def _disarm_mirror_keyboard(self):
        self._mirror_kb_armed = False

    def _arm_mirror_keyboard(self):
        if not self.mirroring:
            return
        self._mirror_kb_armed = True
        self._focus_mirror_keyboard()

    def _mirror_keyboard_active(self):
        if not self.mirroring or not self.current_serial or not self._mirror_kb_armed:
            return False
        modal = QApplication.activeModalWidget()
        if modal and modal is not self:
            return False
        fw = QApplication.focusWidget()
        if fw is self.mirror_kb_input:
            return False
        if fw and isinstance(fw, (QLineEdit, QTextEdit)):
            return False
        return True

    def eventFilter(self, obj, event):
        if obj is self.mirror_kb_input and event.type() == QEvent.Type.FocusIn:
            self._disarm_mirror_keyboard()

        if obj in (self.page_stack, self.nav_list) and event.type() == QEvent.Type.MouseButtonPress:
            self._disarm_mirror_keyboard()

        if self.mirroring and obj in self._mirror_input_targets():
            et = event.type()
            if et == QEvent.Type.MouseButtonPress:
                self._arm_mirror_keyboard()
            elif et == QEvent.Type.KeyPress and isinstance(event, QKeyEvent):
                if self._mirror_keyboard_active() and self._handle_mirror_key_event(event):
                    return True
        return super().eventFilter(obj, event)

    def keyPressEvent(self, event):
        if self._mirror_keyboard_active() and self._handle_mirror_key_event(event):
            return
        super().keyPressEvent(event)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._scale_mirror_layout()
        self._sync_scrcpy_overlay()

    def moveEvent(self, event):
        super().moveEvent(event)
        self._sync_scrcpy_overlay()

    def _lock_window_size(self):
        flags = self.windowFlags()
        flags &= ~Qt.WindowType.WindowMaximizeButtonHint
        flags |= Qt.WindowType.MSWindowsFixedSizeDialogHint
        self.setWindowFlags(flags)
        self.setFixedSize(APP_WINDOW_W, APP_WINDOW_H)

    def _mirror_display_size(self):
        return 0, 0, MIRROR_SCREEN_W, MIRROR_SCREEN_H

    def _mirror_screen_global_rect(self):
        origin = self.mirror_embed_holder.mapToGlobal(QPoint(0, 0))
        return origin.x(), origin.y(), MIRROR_SCREEN_W, MIRROR_SCREEN_H

    def _sync_scrcpy_overlay(self, force=False):
        if not self.mirroring or not self.scrcpy_hwnd:
            return
        x, y, w, h = self._mirror_screen_global_rect()
        rect = (x, y, w, h)
        if not self._overlay_configured:
            _configure_scrcpy_overlay(self.scrcpy_hwnd, int(self.winId()))
            self._overlay_configured = True
            force = True
        if force or rect != self._last_overlay_rect:
            _move_scrcpy_overlay(self.scrcpy_hwnd, x, y, w, h)
            self._last_overlay_rect = rect

    def _apply_mirror_viewport_size_fixed(self):
        w, h = MIRROR_SCREEN_W, MIRROR_SCREEN_H
        if self._last_mirror_size != (w, h):
            self._last_mirror_size = (w, h)
            self.mirror_stack.setFixedSize(w, h)
            self.mirror_phone_frame.setFixedSize(MIRROR_PHONE_FRAME_W, MIRROR_PHONE_FRAME_H)
            self.mirror_hint.setFixedSize(w, h)
        self._sync_scrcpy_overlay()

    def _update_mirror_size(self):
        self._apply_mirror_viewport_size_fixed()

    def _remove_embed_widget(self):
        self._disarm_mirror_keyboard()
        self._overlay_configured = False
        self._last_overlay_rect = None
        if self.scrcpy_hwnd:
            _detach_scrcpy_overlay(self.scrcpy_hwnd)
        if self.scrcpy_embed_widget:
            self.mirror_holder_layout.removeWidget(self.scrcpy_embed_widget)
            self.scrcpy_embed_widget.setParent(None)
            self.scrcpy_embed_widget.deleteLater()
            self.scrcpy_embed_widget = None
        self.scrcpy_qwindow = None
        self.scrcpy_hwnd = None
        self.mirroring = False

    def _get_device_resolution(self):
        try:
            r = self.run_adb_cmd(["-s", self.current_serial, "shell", "wm", "size"])
            m = re.search(r"(\d+)x(\d+)", r.stdout)
            if m:
                return int(m.group(1)), int(m.group(2))
        except Exception:
            pass
        return 1080, 2400

    def _check_scrcpy_alive(self):
        if self.scrcpy_proc and self.scrcpy_proc.poll() is not None:
            self.log("投屏已结束")
            self.stop_mirror()
            return

    def _try_embed_scrcpy(self):
        if not self.scrcpy_proc or self.scrcpy_proc.poll() is not None:
            self.embed_timer.stop()
            return

        title_hint = f"scrcpy_embed_{self.current_serial}"
        exclude = (int(self.winId()),)
        hwnd = find_scrcpy_hwnd(
            self.scrcpy_proc.pid,
            title_hint=title_hint,
            exclude=exclude,
        )
        if not hwnd:
            hwnd = find_scrcpy_hwnd(self.scrcpy_proc.pid, exclude=exclude)
        if not hwnd:
            self.embed_attempts += 1
            if self.embed_attempts > 80:
                self.embed_timer.stop()
                self.log("等待投屏窗口超时")
            return

        try:
            if self.scrcpy_hwnd and self.scrcpy_hwnd != hwnd:
                self._remove_embed_widget()

            self.mirror_stack.setCurrentIndex(1)
            self.mirror_embed_holder.show()
            QApplication.processEvents()

            self.scrcpy_hwnd = hwnd
            self.mirroring = True
            self._overlay_configured = False
            self._last_overlay_rect = None
            self._last_mirror_size = None
            self._sync_scrcpy_overlay(force=True)
            QTimer.singleShot(150, lambda: self._sync_scrcpy_overlay(force=True))
            self._disarm_mirror_keyboard()
            QTimer.singleShot(200, self.mirror_kb_input.setFocus)
            self.embed_timer.stop()
            self.proc_timer.start(1000)
            self.statusBar().showMessage(
                "投屏中 · 用下方输入框打字，或点击画面后直接输入"
            )
            self.log("投屏画面已嵌入右侧区域（比例自适应，键盘已对接）")
        except Exception as e:
            self.embed_timer.stop()
            self.log(f"嵌入失败: {e}，投屏在独立窗口运行")

    def on_nav_changed(self, index):
        if index >= 0:
            self.page_stack.setCurrentIndex(index)

    def _build_other_services_page(self):
        body = QWidget()
        layout = QVBoxLayout(body)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(10)

        gms_card, gms_lay = self._section_frame()
        gms_lay.addWidget(self._section_label("谷歌服务"))
        btn_uninstall_gms = self._action_button("一键卸载 GMS", "danger")
        btn_uninstall_gms.clicked.connect(self.uninstall_gms_all)
        gms_lay.addWidget(btn_uninstall_gms)
        layout.addWidget(gms_card)

        clash_card, clash_lay = self._section_frame()
        clash_lay.addWidget(self._section_label("FlClash 工具"))
        for text, role, fn in (
            ("安装 FlClash", "primary", self.install_flclash),
            ("一键订阅", "accent", self.subscribe_flclash),
            ("卸载 FlClash", "ghost", self.uninstall_flclash),
        ):
            btn = self._action_button(text, role)
            btn.clicked.connect(fn)
            clash_lay.addWidget(btn)
        layout.addWidget(clash_card)
        layout.addStretch()
        return self._wrap_scroll_page("其他服务", "GMS 卸载与 FlClash 相关操作", body)

    def _build_install_tutorial_page(self):
        body = QWidget()
        layout = QVBoxLayout(body)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(10)

        prep_card, prep_lay = self._section_frame()
        prep_lay.addWidget(self._section_label("准备步骤"))
        for text, fn in (
            ("传输文件", self.transfer_backup_files),
            ("更改手机日期", self.change_phone_date),
        ):
            btn = self._action_button(text, "tutorial")
            btn.clicked.connect(fn)
            prep_lay.addWidget(btn)
        layout.addWidget(prep_card)

        google_card, google_lay = self._section_frame()
        google_lay.addWidget(self._section_label("谷歌框架安装"))
        tutorial_actions = (
            ("谷歌服务助手", self.restore_google_assistant),
            ("激活谷歌服务助手", self.activate_google_assistant),
            ("Google 账户管理系统", self.install_google_account_manager),
            ("Google 框架", self.show_google_framework_dialog),
            ("Google 服务", self.install_google_service),
            ("登录谷歌账号", self.login_google_account),
            ("谷歌商店", self.install_google_store),
            ("刷新谷歌数据", self.refresh_google_data),
        )
        for text, fn in tutorial_actions:
            btn = self._action_button(text, "tutorial")
            btn.clicked.connect(fn)
            google_lay.addWidget(btn)
        layout.addWidget(google_card)

        adv_card, adv_lay = self._section_frame()
        adv_lay.addWidget(self._section_label("高级功能"))
        btn_stabilize = self._action_button("稳定框架", "accent")
        btn_stabilize.clicked.connect(self.stabilize_framework)
        adv_lay.addWidget(btn_stabilize)
        layout.addWidget(adv_card)
        layout.addStretch()
        return self._wrap_scroll_page("安装教程", "按顺序完成谷歌框架配置", body)

    def _create_mirror_stubs(self, parent):
        """隐藏控件，保证后台逻辑不报错，页面上不显示。"""
        stub = QWidget(parent)
        stub.setFixedSize(0, 0)
        stub.setVisible(False)
        self.auto_refresh = QCheckBox(stub)
        self.auto_refresh.setChecked(True)
        self.prompt_box = QLineEdit(stub)
        self.adb_input = QLineEdit(stub)
        self.log_box = QTextEdit(stub)
        self.log_box.setReadOnly(True)
        self.conn_status_label = QLabel(stub)
        self.device_list = QListWidget(stub)
        self.device_list.itemClicked.connect(self.on_device_click)
        self.device_list.itemDoubleClicked.connect(self.on_device_double_click)

    def _build_mirror_page(self):
        self._mirror_scale_items = []
        self._mirror_scale_fonts = None

        page = QWidget()
        page.setObjectName("MirrorControlPage")
        margin = 10
        btn_h = 30
        inner_w = MIRROR_PAGE_BASE_W - margin * 2
        btn_gap = 10
        btn_w = (inner_w - btn_gap) // 2

        layout = QVBoxLayout(page)
        layout.setContentsMargins(margin, margin, margin, margin)
        layout.setSpacing(2)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        page.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(btn_gap)
        btn_row.setContentsMargins(0, 0, 0, 0)

        btn_detect = self._action_button("检测手机链接", "primary", fixed=True)
        if IS_MAC:
            btn_detect.setFixedSize(inner_w, btn_h)
        else:
            btn_detect.setFixedSize(btn_w, btn_h)
        btn_detect.clicked.connect(self.detect_phone_connection)
        btn_row.addWidget(btn_detect)

        if not IS_MAC:
            btn_driver = self._action_button("安装usb驱动", "secondary", fixed=True)
            btn_driver.setFixedSize(btn_w, btn_h)
            btn_driver.clicked.connect(self.install_usb_driver)
            btn_row.addWidget(btn_driver)
        btn_row.addStretch()

        layout.addLayout(btn_row)

        btn_notes = self._action_button("注意事项", "tutorial", fixed=True)
        btn_notes.setFixedSize(inner_w, btn_h)
        btn_notes.clicked.connect(self.show_after_sale_notes)
        layout.addWidget(btn_notes)
        layout.addStretch()

        self._create_mirror_stubs(page)
        self.mirror_page = page
        return page

    def show_after_sale_notes(self):
        try:
            path = _desktop_dir() / "谷歌框架售后.txt"
            if path.exists():
                _open_path(path)
                self.log(f"已打开: {path}")
            else:
                path.write_text(AFTER_SALE_NOTES, encoding="utf-8")
                _open_path(path)
                self.log(f"已生成并打开: {path}")
        except Exception as e:
            self.log(f"打开注意事项失败: {e}")
            QMessageBox.warning(self, "注意事项", f"无法打开文档：\n{e}")

    def detect_phone_connection(self):
        self.log("正在检测手机连接...")
        self.refresh_devices()
        ready = [d for d in self.devices if d["status"] == "device"]
        if not ready:
            if self.devices:
                QMessageBox.warning(
                    self,
                    "检测手机链接",
                    "已发现设备，但未授权。\n请在手机上允许 USB 调试后重试。",
                )
            else:
                QMessageBox.warning(
                    self,
                    "检测手机链接",
                    "未检测到设备。\n请确认手机已通过 USB 连接，并已开启 USB 调试。",
                )
            return
        model = ready[0]["model"]
        reply = QMessageBox.question(
            self,
            "检测手机链接",
            f"已检测到手机：{model}\n\n是否接入投屏链接？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        self.current_serial = ready[0]["serial"]
        self.device_list.setCurrentRow(self.devices.index(ready[0]))
        self.mirror_device_label.setText(model)
        self.log(f"正在接入投屏: {model}")
        self.start_mirror()

    def _append_log(self, text):
        self.log_box.moveCursor(QTextCursor.MoveOperation.End)
        self.log_box.insertPlainText(text + "\n")
        self.log_box.moveCursor(QTextCursor.MoveOperation.End)

    def log(self, msg):
        self.log_signal.append.emit(msg)

    def run_adb_cmd(self, args, timeout=15):
        if not ADB.exists():
            raise FileNotFoundError(f"未找到 {ADB.name}")
        return subprocess.run(
            [str(ADB)] + args,
            capture_output=True, text=True, timeout=timeout,
            encoding="utf-8", errors="ignore", cwd=str(ROOT),
            **SUBPROCESS_FLAGS
        )

    def refresh_devices(self, quiet=False):
        prev_serial = self.current_serial
        self.device_list.clear()
        self.devices = []
        if not quiet:
            self.log("正在刷新设备...")
        try:
            result = self.run_adb_cmd(["devices", "-l"])
        except Exception as e:
            if not quiet:
                self.log(f"adb 错误: {e}")
            return
        select_row = -1
        for line in result.stdout.splitlines()[1:]:
            if not line.strip():
                continue
            parts = line.split()
            if len(parts) >= 2 and parts[1] in ("device", "unauthorized"):
                serial = parts[0]
                model = next((p.split(":")[1] for p in parts if p.startswith("model:")), serial)
                self.devices.append({"serial": serial, "model": model, "status": parts[1]})
                linked = serial == prev_serial
                text = f"{model}  [{parts[1]}]"
                if linked:
                    text += "  ← 当前链接"
                self.device_list.addItem(text)
                if linked:
                    select_row = len(self.devices) - 1
        if select_row >= 0:
            self.device_list.setCurrentRow(select_row)
        elif self.devices and not prev_serial:
            self.device_list.setCurrentRow(0)
        if not quiet:
            if self.devices:
                self.log(f"检测到 {len(self.devices)} 台设备")
                self._set_conn_status(f"状态：已发现 {len(self.devices)} 台设备，双击列表可投屏")
            else:
                self.log("未检测到设备")
                self._set_conn_status("状态：未检测到设备，请检查连接")
        if not self.devices:
            self.device_list.addItem("暂无设备，请连接手机...")
            item = self.device_list.item(0)
            if item:
                item.setFlags(Qt.ItemFlag.NoItemFlags)

    def on_device_click(self, _item):
        idx = self.device_list.currentRow()
        if 0 <= idx < len(self.devices):
            self.current_serial = self.devices[idx]["serial"]
            self.log(f"已选择: {self.devices[idx]['model']}")

    def on_device_double_click(self, item):
        self.on_device_click(item)
        QTimer.singleShot(100, self.start_mirror)

    def wifi_connect(self):
        ip, ok = QInputDialog.getText(self, "无线配对", "请输入 IP:端口\n例如 192.168.1.100:45123")
        if not ok or not ip.strip():
            return
        code, ok = QInputDialog.getText(self, "配对码", "请输入 6 位配对码")
        if not ok or not code.strip():
            return
        self.log(f"正在配对 {ip}...")
        threading.Thread(target=self._do_pair, args=(ip.strip(), code.strip()), daemon=True).start()

    def _do_pair(self, ip, code):
        try:
            r = self.run_adb_cmd(["pair", ip, code], timeout=25)
            if "success" in r.stdout.lower() or r.returncode == 0:
                r2 = self.run_adb_cmd(["connect", ip], timeout=15)
                if "connected" in r2.stdout.lower():
                    self.log("无线连接成功")
                    QTimer.singleShot(0, lambda: self._set_conn_status("状态：WiFi 已连接，请在设备列表中选择设备"))
                    QTimer.singleShot(0, self.refresh_devices)
                else:
                    self.log(f"连接失败: {r2.stdout}")
            else:
                self.log(f"配对失败: {r.stdout}")
        except Exception as e:
            self.log(str(e))

    def usb_connect(self):
        self.log("请确保手机已通过 USB 连接并开启调试")
        self._set_conn_status("状态：正在扫描 USB 设备...")
        self.refresh_devices()

    def _ensure_serial(self):
        if not self.current_serial:
            idx = self.device_list.currentRow()
            if 0 <= idx < len(self.devices):
                self.current_serial = self.devices[idx]["serial"]
        if not self.current_serial:
            QMessageBox.warning(self, "提示", "请先选择一台设备")
            return False
        return True

    def send_phone_key(self, keycode, ok_msg):
        if not self._ensure_serial():
            return
        threading.Thread(
            target=self._do_send_phone_key,
            args=(keycode, ok_msg),
            daemon=True,
        ).start()

    def _do_send_phone_key(self, keycode, ok_msg):
        try:
            r = self.run_adb_cmd([
                "-s", self.current_serial, "shell",
                "input", "keyevent", str(keycode),
            ])
            if r.returncode == 0:
                if ok_msg:
                    self.log(ok_msg)
            else:
                self.log((r.stderr or r.stdout or "按键发送失败").strip())
        except Exception as e:
            self.log(f"操作失败: {e}")

    def _escape_adb_text(self, text):
        chars = []
        for ch in text:
            if ch == " ":
                chars.append("%s")
            elif ch in "%&<>|;(){}[]#^$`\\'\"*?!":
                chars.append("\\" + ch)
            else:
                chars.append(ch)
        return "".join(chars)

    def _do_send_phone_text(self, text):
        if not self.current_serial or not text:
            return
        try:
            payload = self._escape_adb_text(text)
            r = self.run_adb_cmd([
                "-s", self.current_serial, "shell",
                "input", "text", payload,
            ])
            if r.returncode != 0:
                self.log((r.stderr or r.stdout or "文字输入失败").strip())
        except Exception as e:
            self.log(f"文字输入失败: {e}")

    def _on_mirror_kb_text_changed(self, text):
        if not self.mirroring or not self.current_serial:
            self._mirror_kb_prev = text
            return
        prev = self._mirror_kb_prev
        if len(text) > len(prev):
            for ch in text[len(prev):]:
                if ord(ch) < 128:
                    threading.Thread(
                        target=self._do_send_phone_text,
                        args=(ch,),
                        daemon=True,
                    ).start()
        elif len(text) < len(prev):
            for _ in range(len(prev) - len(text)):
                threading.Thread(
                    target=self._do_send_phone_key,
                    args=(KEYCODE_DEL, ""),
                    daemon=True,
                ).start()
        self._mirror_kb_prev = text

    def _send_mirror_kb_input(self):
        if not self.mirroring or not self.current_serial:
            return
        threading.Thread(
            target=self._do_send_phone_key,
            args=(KEYCODE_ENTER, ""),
            daemon=True,
        ).start()

    def _handle_mirror_key_event(self, event):
        if not self.current_serial:
            return False

        mods = event.modifiers()
        if mods & (
            Qt.KeyboardModifier.ControlModifier
            | Qt.KeyboardModifier.AltModifier
            | Qt.KeyboardModifier.MetaModifier
        ):
            self._focus_scrcpy_window()
            return False

        android_code = QT_KEY_TO_ANDROID.get(event.key())
        if android_code is not None:
            threading.Thread(
                target=self._do_send_phone_key,
                args=(android_code, ""),
                daemon=True,
            ).start()
            return True

        text = event.text()
        if not text:
            self._focus_scrcpy_window()
            return False

        if any(ord(ch) > 127 for ch in text):
            self._focus_scrcpy_window()
            return False

        threading.Thread(
            target=self._do_send_phone_text,
            args=(text,),
            daemon=True,
        ).start()
        return True

    def reboot_phone(self):
        if not self._ensure_serial():
            return
        reply = QMessageBox.question(
            self, "确认重启", "确定要重启当前手机吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        threading.Thread(target=self._do_reboot_phone, daemon=True).start()

    def _do_reboot_phone(self):
        try:
            self.run_adb_cmd(["-s", self.current_serial, "reboot"], timeout=5)
            self.log("已发送重启指令")
        except Exception as e:
            self.log(f"重启失败: {e}")

    def transfer_backup_files(self):
        if not self._ensure_serial():
            return
        if not BACKUP_SRC.exists():
            QMessageBox.warning(
                self, "提示",
                f"未找到备份文件夹：\n{BACKUP_SRC}",
            )
            return
        self.log("正在传输谷歌服务助手文件到手机 Huawei 目录...")
        threading.Thread(target=self._do_transfer_backup, daemon=True).start()

    def _do_transfer_backup(self):
        serial = self.current_serial
        dest = f"{PHONE_HUAWEI_DIR}/Backup"
        try:
            self.run_adb_cmd(["-s", serial, "shell", "mkdir", "-p", PHONE_HUAWEI_DIR])
            self.run_adb_cmd(["-s", serial, "shell", "rm", "-rf", dest])
            result = subprocess.run(
                [str(ADB), "-s", serial, "push", str(BACKUP_SRC), f"{PHONE_HUAWEI_DIR}/"],
                capture_output=True,
                text=True,
                timeout=300,
                encoding="utf-8",
                errors="ignore",
                cwd=str(ROOT),
                **SUBPROCESS_FLAGS,
            )
            output = (result.stdout or "") + (result.stderr or "")
            if result.returncode == 0:
                self.log("传输完成: " + dest)
                self.log_signal.transfer_done.emit(True, "")
            else:
                self.log(f"传输失败: {output.strip()}")
                self.log_signal.transfer_done.emit(False, output.strip() or "adb push 失败")
        except Exception as e:
            self.log(f"传输失败: {e}")
            self.log_signal.transfer_done.emit(False, str(e))

    def _on_transfer_done(self, success, error_msg):
        if success:
            QMessageBox.information(
                self,
                "传输完成",
                "已经将谷歌服务助手文件传输到 Huawei 目录下",
            )
        else:
            QMessageBox.warning(
                self,
                "传输失败",
                error_msg or "传输失败，请检查 USB 连接与手机存储权限",
            )

    def change_phone_date(self):
        if not self._ensure_serial():
            return
        self.log("正在更改手机日期为 2019年1月1日...")
        threading.Thread(target=self._do_change_phone_date, daemon=True).start()

    def _adb_shell(self, serial, args):
        return self.run_adb_cmd(["-s", serial, "shell"] + args, timeout=20)

    def _do_change_phone_date(self):
        serial = self.current_serial
        ok = False
        try:
            self._adb_shell(serial, ["settings", "put", "global", "auto_time", "0"])
            self._adb_shell(serial, ["settings", "put", "global", "auto_time_zone", "0"])

            r = self._adb_shell(serial, ["cmd", "alarm", "set-time", TARGET_DATE_MS])
            if r.returncode == 0:
                ok = True
                self.log("已通过 alarm 命令设置日期")

            r2 = self._adb_shell(serial, ["date", "010100002019.00"])
            if r2.returncode == 0:
                ok = True
                self.log("已通过 date 命令设置日期")

            open_cmds = [
                ["am", "start", "-a", "android.settings.DATE_SETTINGS"],
                ["am", "start", "-n",
                 "com.android.settings/com.android.settings.Settings$DateTimeSettingsActivity"],
                ["am", "start", "-n",
                 "com.android.settings/com.huawei.settings.datetime.DateTimeSettings"],
            ]
            for cmd in open_cmds:
                r3 = self._adb_shell(serial, cmd)
                if r3.returncode == 0:
                    self.log("已打开日期和时间设置")
                    break

            self.log("日期修改命令已执行")
            self.log_signal.date_change_done.emit()
        except Exception as e:
            self.log(f"更改日期: {e}")
            self.log_signal.date_change_done.emit()

    def _on_date_change_done(self):
        QMessageBox.information(
            self,
            "提示",
            "已经将时间修改成2019年1月1日",
        )

    def restore_google_assistant(self):
        self.log("已显示谷歌服务助手操作说明")
        QMessageBox.information(
            self,
            "谷歌服务助手",
            "请按以下步骤在手机上操作：\n\n"
            "1. 打开 设置\n"
            "2. 进入 系统和更新\n"
            "3. 进入 备份和恢复 → 外部存储\n"
            "4. 返回 后再次进入 备份和恢复\n"
            "5. 点击右上角 菜单（四个点）\n"
            "6. 选择 从内部存储恢复\n"
            "7. 进入 2019年12月7日 目录\n"
            "8. 全选 并 恢复\n"
            "9. 输入密码 a12345678",
        )

    def activate_google_assistant(self):
        if not self._ensure_serial():
            return
        self.log("正在检测桌面并打开谷歌服务助手...")
        threading.Thread(target=self._do_activate_google_assistant, daemon=True).start()

    def _tap_launcher_app(self, serial, app_name):
        self._adb_shell(serial, [
            "uiautomator", "dump", "--compressed", "/sdcard/window_dump.xml"
        ])
        time.sleep(0.3)
        r = self.run_adb_cmd(["-s", serial, "shell", "cat", "/sdcard/window_dump.xml"])
        if r.returncode != 0 or not r.stdout:
            return False
        xml = r.stdout
        for m in re.finditer(
            r'(?:text|content-desc)="([^"]*)"[^>]*bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"',
            xml,
        ):
            label = m.group(1)
            if app_name not in label:
                continue
            x1, y1, x2, y2 = map(int, m.groups()[1:])
            cx = (x1 + x2) // 2
            cy = (y1 + y2) // 2
            self._adb_shell(serial, ["input", "tap", str(cx), str(cy)])
            return True
        return False

    def _launch_google_helper_package(self, serial):
        for comp in (
            f"{GOOGLE_HELPER_PACKAGE}/.MainActivity",
            f"{GOOGLE_HELPER_PACKAGE}/.ui.main.MainActivity",
            f"{GOOGLE_HELPER_PACKAGE}/.ui.MainActivity",
        ):
            r = self._adb_shell(serial, ["am", "start", "-n", comp])
            if r.returncode == 0 and "Error" not in (r.stderr or ""):
                return True
        r = self._adb_shell(serial, [
            "monkey", "-p", GOOGLE_HELPER_PACKAGE,
            "-c", "android.intent.category.LAUNCHER", "1",
        ])
        out = (r.stdout or "") + (r.stderr or "")
        return r.returncode == 0 and "No activities" not in out

    def _auto_open_google_helper(self, serial):
        """1秒内回到桌面，识别并打开谷歌服务助手。"""
        self._adb_shell(serial, ["input", "keyevent", str(KEYCODE_HOME)])
        time.sleep(0.25)
        if self._tap_launcher_app(serial, GOOGLE_HELPER_NAME):
            return True
        return self._launch_google_helper_package(serial)

    def _launch_google_play_package(self, serial):
        r = self._adb_shell(serial, [
            "monkey", "-p", GOOGLE_PLAY_PACKAGE,
            "-c", "android.intent.category.LAUNCHER", "1",
        ])
        out = (r.stdout or "") + (r.stderr or "")
        return r.returncode == 0 and "No activities" not in out

    def _auto_open_google_store(self, serial):
        """1秒内回到桌面，识别并打开谷歌商店。"""
        self._adb_shell(serial, ["input", "keyevent", str(KEYCODE_HOME)])
        time.sleep(0.25)
        if self._tap_launcher_app(serial, GOOGLE_STORE_NAME):
            return True
        for name in ("Google Play", "Play 商店", "Play Store"):
            if self._tap_launcher_app(serial, name):
                return True
        return self._launch_google_play_package(serial)

    def _do_activate_google_assistant(self):
        serial = self.current_serial
        try:
            if self._auto_open_google_helper(serial):
                self.log("已自动打开谷歌服务助手")
            else:
                self.log("未在桌面找到谷歌服务助手，请手动打开")
        except Exception as e:
            self.log(f"自动打开失败: {e}")
        self.log_signal.activate_guide.emit()

    def _show_activate_guide(self):
        QMessageBox.information(
            self,
            "激活谷歌服务助手(手动操作)",
            "已尝试自动打开谷歌服务助手。\n\n"
            "请按以下步骤继续操作：\n\n"
            "1. 如未打开，请在手机桌面找到 谷歌服务助手 并打开\n"
            "2. 点击 激活\n"
            "3. 如有权限或协议，勾选同意即可",
        )

    def refresh_google_data(self):
        if not self._ensure_serial():
            return
        self.log("正在检测桌面并打开谷歌商店...")
        threading.Thread(target=self._do_refresh_google_data, daemon=True).start()

    def _do_refresh_google_data(self):
        serial = self.current_serial
        try:
            if self._auto_open_google_store(serial):
                self.log("已自动打开谷歌商店")
            else:
                self.log("未在桌面找到谷歌商店，请手动打开")
        except Exception as e:
            self.log(f"自动打开失败: {e}")
        self.log_signal.refresh_google_guide.emit()

    def _show_refresh_google_guide(self):
        QMessageBox.information(
            self,
            "刷新谷歌数据",
            "已尝试自动打开谷歌商店。\n\n"
            "请按以下步骤操作：\n\n"
            "1. 请进入谷歌商店，有权限允许就可以\n"
            "2. 有更新，直接跳过\n"
            "3. 进入谷歌商店之后，浏览 30 秒\n"
            "4. 后台清理 Google Play\n"
            "5. 再重新打开，浏览 30 秒",
        )

    def stabilize_framework(self):
        if not self._ensure_serial():
            return
        QMessageBox.information(
            self,
            "稳定框架",
            "您好，恭喜您做到最后一步，请您淘宝收货，问淘宝客服询问6位数密码，"
            "您输入运行就可以。此操作也是为了防止某些客户恶意退款逃单。"
            "感谢您的理解！！",
        )
        password, ok = QInputDialog.getText(
            self,
            "稳定框架",
            "请输入6位数密码：",
            QLineEdit.EchoMode.Password,
        )
        if not ok:
            return
        pwd = password.strip().upper()
        expected = LICENSE_MAP.get(self.license_key, "")
        if pwd != expected:
            QMessageBox.warning(self, "稳定框架", "密码不正确，无法运行。")
            return
        unlimited = self.license_key in UNLIMITED_KEYS
        ok, msg = try_consume_password(self.license_key, pwd, unlimited=unlimited)
        if not ok:
            QMessageBox.warning(self, "稳定框架", msg or "此密码已使用，无法再次运行。")
            return
        self.log("正在稳定框架...")
        threading.Thread(target=self._do_stabilize_framework, daemon=True).start()

    def _do_stabilize_framework(self):
        serial = self.current_serial
        try:
            r = self._adb_shell(serial, [
                "pm", "disable-user", "--user", "0", GSF_PACKAGE,
            ])
            output = (r.stdout or "") + (r.stderr or "")
            success = r.returncode == 0
            if success:
                self.log("稳定框架命令已执行")
            else:
                self.log(f"稳定框架失败: {output.strip() or '未知错误'}")
            self.log_signal.stabilize_framework_done.emit(success, output.strip())
        except Exception as e:
            self.log(f"稳定框架失败: {e}")
            self.log_signal.stabilize_framework_done.emit(False, str(e))

    def _on_stabilize_framework_done(self, success, detail):
        if success:
            QMessageBox.information(
                self,
                "稳定框架",
                "框架以稳定 开启您的快乐时光",
            )
        else:
            QMessageBox.warning(
                self,
                "稳定框架",
                (detail + "\n\n") if detail else ""
                + "命令执行失败，请检查手机连接后重试。",
            )

    def uninstall_gms_all(self):
        if not self._ensure_serial():
            return
        reply = QMessageBox.question(
            self,
            "一键卸载GMS",
            "将卸载以下组件：\n\n"
            "• 谷歌服务助手\n"
            "• 1.apk / 2.apk / 3.apk / 4.apk 对应应用\n\n"
            "确定要继续吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        self.log("正在一键卸载 GMS 相关应用...")
        threading.Thread(target=self._do_uninstall_gms_all, daemon=True).start()

    def _extract_apk_package(self, apk_path):
        if not apk_path.exists():
            return None
        try:
            with zipfile.ZipFile(apk_path, "r") as zf:
                data = zf.read("AndroidManifest.xml")
            found = []
            for m in re.finditer(rb"([a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*){2,})", data):
                name = m.group(1).decode("ascii", errors="ignore")
                if name not in found:
                    found.append(name)
            for prefix in ("com.lzplay.", "com.google.", "com.android.vending"):
                for name in found:
                    if name.startswith(prefix) or name == GOOGLE_PLAY_PACKAGE:
                        return name
            return found[0] if found else None
        except Exception:
            return None

    def _collect_gms_uninstall_packages(self):
        packages = []
        seen = set()

        def add_package(pkg):
            if pkg and pkg not in seen:
                seen.add(pkg)
                packages.append(pkg)

        add_package(GOOGLE_HELPER_PACKAGE)
        for apk in GMS_UNINSTALL_APKS:
            pkg = self._extract_apk_package(apk)
            if pkg:
                add_package(pkg)
            for fallback in APK_PACKAGE_FALLBACKS.get(apk.name, []):
                add_package(fallback)
        return packages

    def _is_package_installed(self, serial, package):
        r = self._adb_shell(serial, ["pm", "path", package])
        out = (r.stdout or "") + (r.stderr or "")
        return r.returncode == 0 and "package:" in out

    def _uninstall_package(self, serial, package):
        for cmd in (
            ["pm", "uninstall", "--user", "0", package],
            ["pm", "uninstall", package],
        ):
            r = self._adb_shell(serial, cmd)
            out = (r.stdout or "") + (r.stderr or "")
            if r.returncode == 0 and "Success" in out:
                return True, out.strip()
        r = self._adb_shell(serial, ["pm", "uninstall", "--user", "0", package])
        out = (r.stdout or "") + (r.stderr or "")
        return False, out.strip() or "卸载失败"

    def _do_uninstall_gms_all(self):
        serial = self.current_serial
        packages = self._collect_gms_uninstall_packages()
        removed = []
        skipped = []
        failed = []
        try:
            for package in packages:
                if not self._is_package_installed(serial, package):
                    skipped.append(package)
                    self.log(f"未安装，跳过: {package}")
                    continue
                ok, detail = self._uninstall_package(serial, package)
                if ok:
                    removed.append(package)
                    self.log(f"已卸载: {package}")
                else:
                    failed.append(f"{package}: {detail}")
                    self.log(f"卸载失败: {package} - {detail}")
            summary = []
            if removed:
                summary.append("已卸载：\n" + "\n".join(f"• {p}" for p in removed))
            if skipped:
                summary.append("未安装（已跳过）：\n" + "\n".join(f"• {p}" for p in skipped))
            if failed:
                summary.append("卸载失败：\n" + "\n".join(f"• {item}" for item in failed))
            detail_text = "\n\n".join(summary) if summary else "未找到需要卸载的应用。"
            self.log_signal.uninstall_gms_done.emit(not failed, detail_text)
        except Exception as e:
            self.log(f"一键卸载 GMS 失败: {e}")
            self.log_signal.uninstall_gms_done.emit(False, str(e))

    def _on_uninstall_gms_done(self, success, detail):
        if success:
            QMessageBox.information(self, "一键卸载GMS", detail or "卸载完成。")
        else:
            QMessageBox.warning(self, "一键卸载GMS", detail or "卸载失败，请检查手机连接后重试。")

    def uninstall_flclash(self):
        if not self._ensure_serial():
            return
        reply = QMessageBox.question(
            self,
            "卸载flclash",
            "确定要卸载 flclash 吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        self.log("正在卸载 flclash...")
        threading.Thread(target=self._do_uninstall_flclash, daemon=True).start()

    def _do_uninstall_flclash(self):
        serial = self.current_serial
        try:
            if not self._is_package_installed(serial, FLCLASH_PACKAGE):
                self.log("未安装 flclash，无需卸载")
                self.log_signal.flclash_uninstall_done.emit(
                    True, "未安装 flclash，无需卸载。",
                )
                return
            ok, detail = self._uninstall_package(serial, FLCLASH_PACKAGE)
            if ok:
                self.log("已卸载 flclash")
                self.log_signal.flclash_uninstall_done.emit(True, "flclash 已卸载。")
            else:
                self.log(f"卸载 flclash 失败: {detail}")
                self.log_signal.flclash_uninstall_done.emit(False, detail)
        except Exception as e:
            self.log(f"卸载 flclash 失败: {e}")
            self.log_signal.flclash_uninstall_done.emit(False, str(e))

    def _on_flclash_uninstall_done(self, success, detail):
        if success:
            QMessageBox.information(self, "卸载flclash", detail or "卸载完成。")
        else:
            QMessageBox.warning(
                self,
                "卸载flclash",
                (detail + "\n\n") if detail else ""
                + "卸载失败，请检查手机连接后重试。",
            )

    def install_flclash(self):
        if not self._ensure_serial():
            return
        if not FLCLASH_APK.exists():
            QMessageBox.warning(self, "提示", f"未找到安装包：\n{FLCLASH_APK}")
            return
        self.log("正在安装 flclash...")
        threading.Thread(
            target=self._do_install_apk,
            args=(FLCLASH_APK, "flclash", "flclash"),
            daemon=True,
        ).start()

    def _on_flclash_install_done(self, success, detail):
        if success:
            QMessageBox.information(
                self,
                "flclash",
                "flclash 已安装完成。\n\n"
                "请在手机桌面找到 flclash 并打开。",
            )
        else:
            QMessageBox.warning(
                self,
                "安装失败",
                (detail + "\n\n") if detail else ""
                + "请检查手机是否允许 USB 安装，\n"
                "或在手机上手动安装 Software\\flclash.apk",
            )

    def _prompt_subscribe_password(self):
        dlg = QDialog(self)
        dlg.setWindowTitle("一键订阅")
        dlg.setMinimumWidth(300)
        layout = QVBoxLayout(dlg)
        layout.addWidget(QLabel("请输入配置密码："))
        edit = QLineEdit()
        edit.setEchoMode(QLineEdit.EchoMode.Password)
        edit.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)
        layout.addWidget(edit)
        row = QHBoxLayout()
        btn_ok = QPushButton("确定")
        btn_cancel = QPushButton("取消")
        row.addWidget(btn_ok)
        row.addWidget(btn_cancel)
        layout.addLayout(row)
        btn_ok.clicked.connect(dlg.accept)
        btn_cancel.clicked.connect(dlg.reject)
        edit.returnPressed.connect(dlg.accept)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return None
        return edit.text()

    def subscribe_flclash(self):
        if not self._ensure_serial():
            return
        password = self._prompt_subscribe_password()
        if password is None:
            return
        if password != FLCLASH_SUBSCRIBE_PASSWORD:
            QMessageBox.warning(self, "一键订阅", "密码不正确，禁止导入。")
            return
        self.log("正在导入 flclash 订阅配置...")
        threading.Thread(target=self._do_subscribe_flclash, daemon=True).start()

    def _do_subscribe_flclash(self):
        serial = self.current_serial
        encoded_url = urllib.parse.quote(_get_flclash_subscribe_url(), safe="")
        schemes = (
            f"flclash://install-config?url={encoded_url}",
            f"clashmeta://install-config?url={encoded_url}",
            f"clash://install-config?url={encoded_url}",
        )
        success = False
        last_error = ""
        try:
            for scheme in schemes:
                r = self._adb_shell(serial, [
                    "am", "start", "-a", "android.intent.action.VIEW",
                    "-d", scheme, FLCLASH_PACKAGE,
                ])
                out = (r.stdout or "") + (r.stderr or "")
                if r.returncode == 0 and "Error" not in out:
                    success = True
                    self.log("已发送订阅导入请求")
                    break
                last_error = out.strip() or "未知错误"
            if not success:
                self.log("导入订阅失败")
            self.log_signal.flclash_subscribe_done.emit(success, last_error)
        except Exception as e:
            self.log("导入订阅失败")
            self.log_signal.flclash_subscribe_done.emit(False, str(e))

    def _on_flclash_subscribe_done(self, success, detail):
        if success:
            QMessageBox.information(
                self,
                "一键订阅",
                "订阅配置已导入 flclash。\n\n"
                "请在手机上确认导入并启用代理。",
            )
        else:
            QMessageBox.warning(
                self,
                "一键订阅",
                "导入失败，请确认 flclash 已安装后重试。",
            )

    def install_google_account_manager(self):
        if not self._ensure_serial():
            return
        if not GOOGLE_ACCOUNT_APK.exists():
            QMessageBox.warning(self, "提示", f"未找到安装包：\n{GOOGLE_ACCOUNT_APK}")
            return
        self.log("正在安装 google账户管理系统...")
        threading.Thread(
            target=self._do_install_apk,
            args=(GOOGLE_ACCOUNT_APK, "google账户管理系统", "google_account"),
            daemon=True,
        ).start()

    def show_google_framework_dialog(self):
        if not self._ensure_serial():
            return
        dlg = QDialog(self)
        dlg.setWindowTitle("google框架(手动安装)")
        dlg.setMinimumWidth(280)
        layout = QVBoxLayout(dlg)
        layout.addWidget(QLabel("请选择要安装的 Google 框架版本："))
        row = QHBoxLayout()
        btn_v10 = QPushButton("v10")
        btn_v12 = QPushButton("v12")
        btn_v10.clicked.connect(lambda: self._install_google_framework("v10", dlg))
        btn_v12.clicked.connect(lambda: self._install_google_framework("v12", dlg))
        row.addWidget(btn_v10)
        row.addWidget(btn_v12)
        layout.addLayout(row)
        dlg.exec()

    def _install_google_framework(self, version, dlg):
        apk = GOOGLE_FRAMEWORK_APKS.get(version)
        if not apk or not apk.exists():
            QMessageBox.warning(self, "提示", f"未找到安装包：\n{apk}")
            return
        dlg.accept()
        self.log(f"正在安装 Google框架 {version}...")
        threading.Thread(
            target=self._do_install_apk,
            args=(apk, f"Google框架 {version}", version),
            daemon=True,
        ).start()

    def install_google_service(self):
        if not self._ensure_serial():
            return
        if not GOOGLE_SERVICE_APK.exists():
            QMessageBox.warning(self, "提示", f"未找到安装包：\n{GOOGLE_SERVICE_APK}")
            return
        self.log("正在安装 google服务...")
        threading.Thread(
            target=self._do_install_apk,
            args=(GOOGLE_SERVICE_APK, "google服务", "google_service"),
            daemon=True,
        ).start()

    def install_google_store(self):
        if not self._ensure_serial():
            return
        if not GOOGLE_STORE_APK.exists():
            QMessageBox.warning(self, "提示", f"未找到安装包：\n{GOOGLE_STORE_APK}")
            return
        self.log("正在安装 谷歌商店...")
        threading.Thread(
            target=self._do_install_apk,
            args=(GOOGLE_STORE_APK, "谷歌商店", "google_store"),
            daemon=True,
        ).start()

    def _emit_apk_install_done(self, emit_tag, success, detail):
        if emit_tag == "google_account":
            self.log_signal.google_account_install_done.emit(success, detail)
        elif emit_tag == "google_service":
            self.log_signal.google_service_install_done.emit(success, detail)
        elif emit_tag == "google_store":
            self.log_signal.google_store_install_done.emit(success, detail)
        elif emit_tag == "flclash":
            self.log_signal.flclash_install_done.emit(success, detail)
        else:
            self.log_signal.google_framework_install_done.emit(success, detail, emit_tag)

    def _do_install_apk(self, apk_path, label, emit_tag):
        serial = self.current_serial
        timeout = 600 if apk_path.stat().st_size > 50_000_000 else 180
        try:
            result = subprocess.run(
                [str(ADB), "-s", serial, "install", "-r", str(apk_path)],
                capture_output=True,
                text=True,
                timeout=timeout,
                encoding="utf-8",
                errors="ignore",
                cwd=str(ROOT),
                **SUBPROCESS_FLAGS,
            )
            output = (result.stdout or "") + (result.stderr or "")
            success = result.returncode == 0 and "Success" in output
            if success:
                self.log(f"{label} 安装成功")
            else:
                self.log(f"{label} 安装结果: {output.strip() or '未知错误'}")
            self._emit_apk_install_done(emit_tag, success, output.strip())
        except Exception as e:
            self.log(f"{label} 安装失败: {e}")
            self._emit_apk_install_done(emit_tag, False, str(e))

    def _on_google_account_install_done(self, success, detail):
        if success:
            QMessageBox.information(
                self,
                "google账户管理系统(手动安装)",
                "安装包已安装完成。\n\n"
                "请按以下步骤继续操作：\n\n"
                "1. 在手机桌面找到 google账户管理系统\n"
                "2. 打开该软件\n"
                "3. 按软件内提示完成设置",
            )
        else:
            QMessageBox.warning(
                self,
                "安装失败",
                (detail + "\n\n") if detail else ""
                + "请检查手机是否允许 USB 安装，\n"
                "或在手机上手动安装 Software\\1.apk",
            )

    def _on_google_framework_install_done(self, success, detail, version):
        apk_name = GOOGLE_FRAMEWORK_APKS.get(version, Path("")).name
        if success:
            QMessageBox.information(
                self,
                "google框架(手动安装)",
                f"Google框架 {version} 已安装完成。\n\n"
                "请按以下步骤继续操作：\n\n"
                "1. 在手机上确认安装提示（如有）\n"
                "2. 按软件内提示完成 Google 框架设置",
            )
        else:
            QMessageBox.warning(
                self,
                "安装失败",
                (detail + "\n\n") if detail else ""
                + "请检查手机是否允许 USB 安装，\n"
                f"或在手机上手动安装 Software\\{apk_name}",
            )

    def _on_google_service_install_done(self, success, detail):
        if success:
            QMessageBox.information(
                self,
                "google服务(手动安装)",
                "请打开您自己手机的魔术上网vpn，\n"
                "如果没有，请解决它，\n"
                "也可以寻找微信客服进行咨询购买。",
            )
        else:
            QMessageBox.warning(
                self,
                "安装失败",
                (detail + "\n\n") if detail else ""
                + "请检查手机是否允许 USB 安装，\n"
                "或在手机上手动安装 Software\\3.apk",
            )

    def _on_google_store_install_done(self, success, detail):
        if success:
            QMessageBox.information(
                self,
                "谷歌商店(手动安装)",
                "安装包已安装完成。\n\n"
                "请按以下步骤继续操作：\n\n"
                "1. 在手机桌面找到 谷歌商店\n"
                "2. 打开该软件\n"
                "3. 按软件内提示完成设置",
            )
        else:
            QMessageBox.warning(
                self,
                "安装失败",
                (detail + "\n\n") if detail else ""
                + "请检查手机是否允许 USB 安装，\n"
                "或在手机上手动安装 Software\\4.apk",
            )

    def login_google_account(self):
        if not self._ensure_serial():
            return
        self.log("正在打开手机设置...")
        threading.Thread(target=self._do_login_google_account, daemon=True).start()

    def _do_login_google_account(self):
        serial = self.current_serial
        try:
            for cmd in (
                ["am", "start", "-a", "android.settings.SETTINGS"],
                ["am", "start", "-n", "com.android.settings/.Settings"],
            ):
                if self._adb_shell(serial, cmd).returncode == 0:
                    self.log("已打开手机设置")
                    break
        except Exception as e:
            self.log(f"打开设置失败: {e}")
        self.log_signal.login_google_guide.emit()

    def _show_login_google_guide(self):
        QMessageBox.information(
            self,
            "登录谷歌账号(手动登录)",
            "已为您打开手机设置。\n\n"
            "请按以下步骤操作：\n\n"
            "1. 滑到设置最下面，点击 Google 选项\n"
            "2. 登录谷歌账户\n"
            "3. 如果没有，可以选择找客服购买或者创建一个\n\n"
            "在这里，请登录您的所有谷歌账号。\n"
            "如果后续想要添加别的谷歌账号，需要重新付费。",
        )

    def install_usb_driver(self):
        if IS_MAC:
            QMessageBox.information(
                self,
                "USB 连接",
                "macOS 无需安装 Windows USB 驱动。\n\n"
                "请用数据线连接手机，在手机端开启「USB 调试」后，"
                "点击「检测手机链接」即可。",
            )
            return
        for path in DRIVER_INSTALL_CANDIDATES:
            if not path.exists():
                continue
            if path.suffix.lower() == ".inf":
                self.log(f"正在安装驱动: {path.name}")
                subprocess.Popen(
                    ["pnputil", "/add-driver", str(path), "/install"],
                    cwd=str(path.parent),
                    **SUBPROCESS_FLAGS,
                )
                return
            if path.suffix.lower() == ".msi":
                self.log(f"正在运行驱动安装程序: {path.name}")
                subprocess.Popen(["msiexec", "/i", str(path)])
                return
            self.log(f"正在运行驱动安装程序: {path.name}")
            subprocess.Popen([str(path)], cwd=str(path.parent))
            return

        self.log("未找到内置驱动包，正在打开设备管理器...")
        subprocess.Popen(["devmgmt.msc"], shell=True)
        QMessageBox.information(
            self,
            "安装USB驱动",
            "已打开「设备管理器」。\n\n"
            "请在带叹号或问号的 Android 设备上右键，选择「更新驱动程序」。",
        )

    def run_adb(self):
        cmd = self.adb_input.text().strip()
        if not cmd:
            return
        self.log(f"> adb {cmd}")
        threading.Thread(target=self._run_adb_text, args=(cmd,), daemon=True).start()
        self.adb_input.clear()

    def _run_adb_text(self, cmd):
        try:
            r = self.run_adb_cmd(cmd.split())
            self.log(r.stdout + r.stderr)
        except Exception as e:
            self.log(str(e))

    def start_mirror(self):
        if self.mirroring or (self.scrcpy_proc and self.scrcpy_proc.poll() is None):
            self.log("投屏已在运行中")
            return

        idx = self.device_list.currentRow()
        if 0 <= idx < len(self.devices):
            self.current_serial = self.devices[idx]["serial"]
        if not self.current_serial:
            QMessageBox.warning(self, "提示", "请先选择一台设备")
            return
        if not SCRCPY.exists():
            QMessageBox.warning(self, "提示", f"未找到 {SCRCPY.name}")
            return
        if not SCRCPY_SERVER.exists():
            QMessageBox.warning(self, "提示", "未找到 scrcpy-server 文件")
            return

        self.stop_mirror()

        model = next((d["model"] for d in self.devices if d["serial"] == self.current_serial), "")
        self.mirror_device_label.setText(model or self.current_serial)
        self.log(f"正在投屏: {model or self.current_serial}")
        self.mirror_stack.setCurrentIndex(0)
        self._update_mirror_size()

        if IS_MAC:
            args = [
                str(SCRCPY), "-s", self.current_serial,
                "--max-fps", "60", "--video-bit-rate", "8M",
                "--stay-awake",
                "--window-title", f"谷歌投屏 - {model or self.current_serial}",
            ]
            self.mirror_hint.setText(
                f"正在连接...\n\n{model or self.current_serial}\n\n"
                "macOS 投屏在独立窗口中显示"
            )
            embed_msg = "投屏已启动，请在独立窗口查看画面"
        else:
            self.device_w, self.device_h = self._get_device_resolution()
            _, _, ww, wh = self._mirror_display_size()
            args = [
                str(SCRCPY), "-s", self.current_serial,
                "--max-fps", "60", "--video-bit-rate", "8M",
                "--window-title", f"scrcpy_embed_{self.current_serial}",
                "--window-borderless",
                "--max-size", str(max(ww, wh)),
                "--window-width", str(ww),
                "--window-height", str(wh),
                "--window-x", "-32000",
                "--window-y", "-32000",
                "--stay-awake",
                "--keyboard=sdk",
            ]
            self.mirror_hint.setText(f"正在连接...\n\n{model or self.current_serial}")
            embed_msg = "投屏已启动，正在嵌入画面..."

        try:
            self.scrcpy_proc = subprocess.Popen(args, cwd=str(ROOT), **SUBPROCESS_FLAGS)
            if IS_MAC:
                self.mirroring = True
                self.proc_timer.start(200)
                self.mirror_hint.setText(
                    f"投屏窗口已打开\n\n{model or self.current_serial}\n\n"
                    "请查看名为「谷歌投屏」的独立窗口"
                )
            else:
                self.embed_attempts = 0
                self.embed_timer.start(500)
            self.log(embed_msg)
        except Exception as e:
            self.log(f"启动失败: {e}")
            QMessageBox.critical(self, "错误", str(e))

    def stop_mirror(self):
        self.embed_timer.stop()
        self.proc_timer.stop()
        self._remove_embed_widget()

        if self.scrcpy_proc and self.scrcpy_proc.poll() is None:
            self.scrcpy_proc.terminate()
            try:
                self.scrcpy_proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self.scrcpy_proc.kill()
        self.scrcpy_proc = None

        if IS_WIN:
            try:
                subprocess.run(
                    ["taskkill", "/F", "/IM", "scrcpy.exe"],
                    capture_output=True, **SUBPROCESS_FLAGS
                )
            except Exception:
                pass

        self.mirror_hint.setText(
            "连接手机后开始投屏\n\n"
            "点击左侧「检测手机链接」\n"
            "画面将显示在此手机框内"
        )
        self.mirror_device_label.setText("等待连接")
        self.mirror_stack.setCurrentIndex(0)
        self._last_mirror_size = None
        self._mirror_kb_prev = ""
        self.mirror_kb_input.clear()
        self._apply_mirror_viewport_size_fixed()
        self.statusBar().showMessage("谷歌框架远程操作 · 精简投屏")
        self.log("已停止投屏")

    def showEvent(self, event):
        super().showEvent(event)
        QTimer.singleShot(100, self._scale_mirror_layout)
        QTimer.singleShot(120, self._apply_mirror_viewport_size_fixed)

    def clear_log(self):
        self.log_box.clear()


LICENSE_DIALOG_STYLE = """
    QDialog#LicenseDialog {
        background: #f3f6fb;
    }
    QFrame#LicenseCard {
        background: #ffffff;
        border: 1px solid #e3e8f0;
        border-radius: 14px;
    }
    QFrame#LicenseHeader {
        background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
            stop:0 #1a73e8, stop:1 #4f8df7);
        border-radius: 14px;
    }
    QLabel#LicenseTitle {
        color: #ffffff;
        font-size: 22px;
        font-weight: bold;
    }
    QLabel#LicenseSubtitle {
        color: rgba(255, 255, 255, 0.92);
        font-size: 13px;
    }
    QLabel#LicenseHint {
        color: #6b7280;
        font-size: 12px;
    }
    QLabel#LicenseStatTitle {
        color: #6b7280;
        font-size: 12px;
    }
    QLabel#LicenseStatValue {
        color: #111827;
        font-size: 15px;
        font-weight: bold;
    }
    QLabel#LicenseSuccessTitle {
        color: #111827;
        font-size: 20px;
        font-weight: bold;
    }
    QLabel#LicenseSuccessBadge {
        color: #0f9d58;
        font-size: 13px;
        font-weight: bold;
    }
    QLineEdit#LicenseKeyEdit {
        background: #f8fafc;
        border: 2px solid #dbe3ef;
        border-radius: 10px;
        padding: 12px 14px;
        font-size: 20px;
        font-weight: bold;
        color: #1f2937;
        letter-spacing: 3px;
    }
    QLineEdit#LicenseKeyEdit:focus {
        border: 2px solid #1a73e8;
        background: #ffffff;
    }
    QPushButton#LicensePrimaryBtn {
        background: #1a73e8;
        color: #ffffff;
        border: none;
        border-radius: 10px;
        padding: 12px 18px;
        font-size: 14px;
        font-weight: bold;
    }
    QPushButton#LicensePrimaryBtn:hover { background: #1666cf; }
    QPushButton#LicensePrimaryBtn:pressed { background: #1256ad; }
    QPushButton#LicenseGhostBtn {
        background: #ffffff;
        color: #4b5563;
        border: 1px solid #d1d5db;
        border-radius: 10px;
        padding: 12px 18px;
        font-size: 14px;
    }
    QPushButton#LicenseGhostBtn:hover { background: #f9fafb; }
    QFrame#LicenseStatCard {
        background: #f8fafc;
        border: 1px solid #e5e7eb;
        border-radius: 10px;
    }
"""


class LicenseDialog(QDialog):
    def __init__(self):
        super().__init__()
        self.setObjectName("LicenseDialog")
        self.setWindowTitle("授权验证")
        self.setFixedSize(460, 560)
        self.setStyleSheet(LICENSE_DIALOG_STYLE)
        self.result_key = None
        self.usage_info = {}

        root = QVBoxLayout(self)
        root.setContentsMargins(22, 22, 22, 22)

        card = QFrame()
        card.setObjectName("LicenseCard")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(0, 0, 0, 0)
        card_layout.setSpacing(0)

        self.stack = QStackedWidget()
        self.stack.addWidget(self._build_input_page())
        self.stack.addWidget(self._build_success_page())
        card_layout.addWidget(self.stack)
        root.addWidget(card)

    def _build_header(self, title, subtitle):
        header = QFrame()
        header.setObjectName("LicenseHeader")
        header.setFixedHeight(118)
        layout = QVBoxLayout(header)
        layout.setContentsMargins(24, 22, 24, 18)
        layout.setSpacing(6)
        title_lbl = QLabel(title)
        title_lbl.setObjectName("LicenseTitle")
        title_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sub_lbl = QLabel(subtitle)
        sub_lbl.setObjectName("LicenseSubtitle")
        sub_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sub_lbl.setWordWrap(True)
        layout.addWidget(title_lbl)
        layout.addWidget(sub_lbl)
        return header

    def _build_input_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._build_header("谷歌框架远程操作", "请输入 10 位授权密钥，验证后可查看使用情况"))

        body = QWidget()
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(28, 26, 28, 28)
        body_layout.setSpacing(14)

        hint = QLabel("授权密钥")
        hint.setObjectName("LicenseHint")
        self.key_edit = QLineEdit()
        self.key_edit.setObjectName("LicenseKeyEdit")
        self.key_edit.setMaxLength(10)
        self.key_edit.setPlaceholderText("例如 BMPBI3EP1G")
        self.key_edit.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.key_edit.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)
        self.key_edit.textChanged.connect(self._normalize_key_input)
        self.key_edit.returnPressed.connect(self._verify_key)

        tip = QLabel("普通密钥仅可进入 1 次；不限次数密钥可重复使用。")
        tip.setObjectName("LicenseHint")
        tip.setWordWrap(True)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(12)
        btn_cancel = QPushButton("退出")
        btn_cancel.setObjectName("LicenseGhostBtn")
        btn_cancel.clicked.connect(self.reject)
        btn_ok = QPushButton("验证密钥")
        btn_ok.setObjectName("LicensePrimaryBtn")
        btn_ok.clicked.connect(self._verify_key)
        btn_row.addWidget(btn_cancel)
        btn_row.addWidget(btn_ok)

        body_layout.addWidget(hint)
        body_layout.addWidget(self.key_edit)
        body_layout.addWidget(tip)
        body_layout.addSpacing(8)
        body_layout.addLayout(btn_row)
        layout.addWidget(body)
        return page

    def _build_success_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._build_header("验证成功", "授权信息已确认，可进入软件开始使用"))

        body = QWidget()
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(28, 24, 28, 28)
        body_layout.setSpacing(12)

        self.success_badge = QLabel("密钥有效")
        self.success_badge.setObjectName("LicenseSuccessBadge")
        self.success_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.success_title = QLabel("欢迎使用")
        self.success_title.setObjectName("LicenseSuccessTitle")
        self.success_title.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.stat_first = self._make_stat_card("首次使用", "--")
        self.stat_last = self._make_stat_card("最近使用", "--")
        self.stat_entry = self._make_stat_card("进入剩余", "--")
        self.stat_password = self._make_stat_card("稳定框架剩余", "--")
        self.stat_extra = QLabel("")
        self.stat_extra.setObjectName("LicenseHint")
        self.stat_extra.setAlignment(Qt.AlignmentFlag.AlignCenter)

        btn_enter = QPushButton("进入软件")
        btn_enter.setObjectName("LicensePrimaryBtn")
        btn_enter.clicked.connect(self._enter_app)

        body_layout.addWidget(self.success_badge)
        body_layout.addWidget(self.success_title)
        body_layout.addWidget(self.stat_first)
        body_layout.addWidget(self.stat_last)
        body_layout.addWidget(self.stat_entry)
        body_layout.addWidget(self.stat_password)
        body_layout.addWidget(self.stat_extra)
        body_layout.addSpacing(6)
        body_layout.addWidget(btn_enter)
        layout.addWidget(body)
        return page

    def _make_stat_card(self, title, value):
        frame = QFrame()
        frame.setObjectName("LicenseStatCard")
        row = QHBoxLayout(frame)
        row.setContentsMargins(14, 12, 14, 12)
        title_lbl = QLabel(title)
        title_lbl.setObjectName("LicenseStatTitle")
        value_lbl = QLabel(value)
        value_lbl.setObjectName("LicenseStatValue")
        value_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        row.addWidget(title_lbl)
        row.addStretch()
        row.addWidget(value_lbl)
        frame.value_label = value_lbl
        return frame

    def _normalize_key_input(self, text):
        cleaned = re.sub(r"[^A-Za-z0-9]", "", text).upper()
        if cleaned != text:
            pos = self.key_edit.cursorPosition()
            self.key_edit.blockSignals(True)
            self.key_edit.setText(cleaned)
            self.key_edit.setCursorPosition(min(pos, len(cleaned)))
            self.key_edit.blockSignals(False)

    def _fmt_remain_text(self, info, field):
        remaining = info.get(field, 0)
        total = info.get(field.replace("remaining", "total"), 1)
        if info.get("unlimited") or remaining == -1:
            return "不限次数"
        return f"{remaining} / {total} 次"

    def _fill_success_page(self, key, info):
        self.result_key = key
        self.usage_info = info or {}
        unlimited = bool(self.usage_info.get("unlimited"))
        self.success_badge.setText("不限次数密钥" if unlimited else "一次性密钥")
        masked = f"{key[:4]}****{key[-2:]}" if len(key) >= 6 else key
        self.success_title.setText(f"密钥 {masked} 已激活")
        self.stat_first.value_label.setText(self.usage_info.get("first_used") or "--")
        self.stat_last.value_label.setText(self.usage_info.get("last_used") or "--")
        self.stat_entry.value_label.setText(self._fmt_remain_text(self.usage_info, "entry_remaining"))
        self.stat_password.value_label.setText(self._fmt_remain_text(self.usage_info, "password_remaining"))
        extra = ""
        if unlimited:
            used = int(self.usage_info.get("entry_used", 0))
            if used > 0:
                extra = f"累计进入 {used} 次"
        self.stat_extra.setText(extra)

    def _verify_key(self):
        global LICENSE_MAP, UNLIMITED_KEYS
        key = self.key_edit.text().strip().upper()
        if not key:
            QMessageBox.warning(self, "提示", "请输入 10 位密钥。")
            return
        if len(key) != 10:
            QMessageBox.warning(self, "提示", "密钥必须为 10 位字母或数字。")
            return
        LICENSE_MAP, UNLIMITED_KEYS = ensure_key_bound(
            key, LICENSE_MAP, UNLIMITED_KEYS
        )
        if key not in LICENSE_MAP:
            QMessageBox.warning(self, "密钥错误", "密钥不正确，请重新输入。")
            return
        unlimited = key in UNLIMITED_KEYS
        ok, msg, info = try_consume_key_with_info(key, unlimited=unlimited)
        if not ok:
            detail = "\n".join(format_usage_lines(info)) if info else ""
            text = msg or "此密钥已使用，无法再次进入。"
            if detail:
                text += f"\n\n{detail}"
            QMessageBox.warning(self, "密钥不可用", text)
            return
        self._fill_success_page(key, info)
        self.stack.setCurrentIndex(1)

    def _enter_app(self):
        if self.result_key:
            self.accept()


def verify_license_at_startup():
    app = QApplication.instance() or QApplication(sys.argv)
    app.setStyle("Fusion")
    global LICENSE_MAP, UNLIMITED_KEYS
    LICENSE_MAP, UNLIMITED_KEYS = refresh_license_maps(
        LICENSE_MAP, UNLIMITED_KEYS
    )
    if not LICENSE_MAP:
        QMessageBox.critical(None, "错误", "授权数据缺失，程序无法启动。")
        return None
    dlg = LicenseDialog()
    if dlg.exec() != QDialog.DialogCode.Accepted:
        return None
    return dlg.result_key


def _app_icon():
    for name in ("app_icon.ico", "app_icon.png"):
        path = ROOT / name
        if path.exists():
            return QIcon(str(path))
    return QIcon()


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setWindowIcon(_app_icon())
    license_key = verify_license_at_startup()
    if not license_key:
        sys.exit(0)
    win = MirrorWindow(license_key=license_key)
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
