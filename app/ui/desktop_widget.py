# SPDX-License-Identifier: GPL-3.0-or-later
# MiHome-Windows: 米家设备的 Windows 桌面控制端
# Copyright (C) 2026 MiHome-Windows contributors
"""桌面小组件窗口：多设备常驻桌面，托盘同款内容 + 圆角卡片。

实现要点：
- 顶层无边框 Tool 窗口（不占任务栏/Alt+Tab），WA_TranslucentBackground；
- 内容经 QGraphicsProxyWidget 承载 scale/100 倍缩放（1% 步进调节），
  调节行加载完成后自动按内容收放高度（默认展示完整，不留空白）；
- 四角圆角（卡片自身圆角 + 外透明边距裁出圆角）；
- 「背景透明度」只作用白色卡片底色（rgba 背景），可点击控件与边框
  保持不透明（QuickOps 行/SURFACE 均为实底）；标题与文字不受影响；
- 顶部细手柄未锁定时拖拽移动；右下角「↘」手柄拖动 = 连续调缩放/长度；
- 标题默认取设备名（单台）或设备名连读（多台），可在设置页自定义。
"""

from PySide6.QtCore import QEvent, QPoint, Qt, QTimer
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QFrame,
    QGraphicsProxyWidget,
    QGraphicsScene,
    QGraphicsView,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from app.core.jobs import JobExecutor
from app.core.service import MijiaService
from app.ui.power_button import PowerButton
from app.ui.quick_ops import QuickOpsPopup
from app.ui.si_theme import SiColors

_DESIGN_W = 268
_HANDLE_H = 24


def _hex_rgba(hex_color: str, alpha: int) -> str:
    """#RRGGBB + 0..100 → rgba(r,g,b,a)。"""
    h = hex_color.lstrip("#")
    if len(h) != 6:
        return hex_color
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    a = max(0, min(alpha, 100)) / 100.0
    return f"rgba({r},{g},{b},{a:g})"


def _auto_title(cfg: dict) -> str:
    custom = str(cfg.get("title") or "").strip()
    if custom:
        return custom
    meta = cfg.get("devices") or {}
    names = []
    for did in cfg.get("dids", []):
        m = meta.get(did) or {}
        names.append(m.get("name") or did)
    if not names:
        return "米家小组件"
    if len(names) == 1:
        return names[0]
    return "、".join(names[:3]) + (f" 等{len(names)}台" if len(names) > 3 else "")


class _HandleBar(QFrame):
    """顶部手柄：未锁定时整条可拖动窗口；左侧标题可自定义。"""

    def __init__(self, owner: "DesktopWidget", locked: bool, title: str):
        super().__init__()
        self._owner = owner
        self._press = None
        self.setObjectName("widgetHandle")
        self.setFixedHeight(_HANDLE_H)
        self.setCursor(Qt.CursorShape.OpenHandCursor if not locked
                       else Qt.CursorShape.ArrowCursor)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(10, 0, 6, 0)
        lay.setSpacing(6)
        mark = QLabel("◈")
        mark.setStyleSheet(f"color: {SiColors.THEME}; background: transparent;")
        lay.addWidget(mark)
        self.title_lab = QLabel(title)
        self.title_lab.setFont(
            QFont("Microsoft YaHei UI", 9, QFont.Weight.DemiBold))
        self.title_lab.setStyleSheet(
            f"color: {SiColors.TEXT_PRIMARY}; background: transparent;")
        lay.addWidget(self.title_lab)
        lay.addStretch(1)
        if locked:
            lock = QLabel("🔒")
            lock.setToolTip("已锁定位置：在「设置 → 桌面小组件」解锁后可拖动")
            lock.setStyleSheet("background: transparent;")
            lay.addWidget(lock)
        self.installEventFilter(self)

    def set_title(self, title: str) -> None:
        self.title_lab.setText(title)

    def eventFilter(self, obj, event) -> bool:  # noqa: N802
        if self._owner._cfg.get("locked", True):
            return super().eventFilter(obj, event)
        et = event.type()
        if et == QEvent.MouseButtonPress and event.button() == Qt.LeftButton:
            self._press = (event.globalPosition().toPoint()
                           - self._owner.frameGeometry().topLeft())
            return True
        if et == QEvent.MouseMove and self._press is not None \
                and event.buttons() & Qt.LeftButton:
            self._owner.move(event.globalPosition().toPoint() - self._press)
            return True
        if et == QEvent.MouseButtonRelease and event.button() == Qt.LeftButton:
            if self._press is not None:
                self._press = None
                self._owner._notify_moved()
            return True
        return super().eventFilter(obj, event)


class _ScaleGrip(QFrame):
    """右下角缩放手柄：上下拖动 = 连续调缩放（长度随内容同步）。"""

    def __init__(self, owner: "DesktopWidget"):
        super().__init__()
        self._owner = owner
        self._base = None
        self.setFixedSize(20, 16)
        self.setCursor(Qt.CursorShape.SizeFDiagCursor)
        lab = QLabel("↘")
        lab.setStyleSheet(
            f"color: {SiColors.TEXT_MUTED}; background: transparent;"
            f" font-size: 11pt;")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(lab, alignment=Qt.AlignRight | Qt.AlignBottom)
        self.installEventFilter(self)

    def eventFilter(self, obj, event) -> bool:  # noqa: N802
        et = event.type()
        if et == QEvent.MouseButtonPress and event.button() == Qt.LeftButton:
            self._base = (self._owner._cfg.get("scale", 100),
                          event.globalPosition().toPoint().y())
            return True
        if et == QEvent.MouseMove and self._base is not None \
                and event.buttons() & Qt.LeftButton:
            base_scale, base_y = self._base
            delta = (event.globalPosition().toPoint().y() - base_y) // 2
            self._owner._set_scale(max(50, min(200, base_scale + delta)))
            return True
        if et == QEvent.MouseButtonRelease and event.button() == Qt.LeftButton:
            self._base = None
            return True
        return super().eventFilter(obj, event)


class DesktopWidget(QWidget):
    def __init__(self, manager, service: MijiaService, jobs: JobExecutor,
                 cfg: dict):
        super().__init__(None)
        self._manager = manager
        self._service = service
        self._jobs = jobs
        self._cfg = dict(cfg)
        self._devices_meta = dict(cfg.get("devices") or {})
        self._handle: _HandleBar | None = None
        self._card: QWidget | None = None

        flags = Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool
        if cfg.get("topmost", True):
            flags |= Qt.WindowType.WindowStaysOnTopHint
        self.setWindowFlags(flags)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        self._scene = QGraphicsScene(self)
        self._view = QGraphicsView(self._scene, self)
        self._view.setFrameShape(QGraphicsView.Shape.NoFrame)
        self._view.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._view.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._view.setStyleSheet("background: transparent; border: none;")
        root.addWidget(self._view)

        self._proxy: QGraphicsProxyWidget | None = None
        self._content: QWidget | None = None
        self._rebuild_content()
        self.apply_config(self._cfg)

    # ---------- 构建内容 ----------

    def _rebuild_content(self) -> None:
        if self._content is not None:
            self._scene.removeItem(self._proxy)
            self._content.deleteLater()
            self._content = None
            self._proxy = None
        outer = QWidget()
        outer.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        outer.setFixedWidth(_DESIGN_W + 16)
        o_lay = QVBoxLayout(outer)
        o_lay.setContentsMargins(8, 8, 8, 8)
        card = QFrame()
        card.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        card.setObjectName("widgetCard")
        o_lay.addWidget(card)
        self._content = outer
        self._card = card

        lay = QVBoxLayout(card)
        lay.setContentsMargins(2, 2, 2, 0)
        lay.setSpacing(2)
        self._handle = _HandleBar(
            self, self._cfg.get("locked", True), _auto_title(self._cfg))
        lay.addWidget(self._handle)

        devices = (self._manager.devices_lookup()
                   if hasattr(self._manager, "devices_lookup") else {})
        for did in [d for d in self._cfg.get("dids", [])]:
            block = self._build_device_block(did, devices.get(did))
            if block is not None:
                lay.addWidget(block)
        # 右下角缩放手柄
        foot = QHBoxLayout()
        foot.addStretch(1)
        foot.addWidget(_ScaleGrip(self))
        lay.addLayout(foot)

        self._paint_bg()
        self._proxy = self._scene.addWidget(outer)
        QTimer.singleShot(0, self._refit)

    def _paint_bg(self) -> None:
        """背景 = 圆角 + 半透明白底；控件与文字保持不透明。"""
        if self._card is None:
            return
        alpha = max(8, int(self._cfg.get("bg_alpha", 90)))
        rgba = _hex_rgba(SiColors.CARD, alpha)
        self._card.setStyleSheet(
            f"QFrame#widgetCard {{ background: {rgba};"
            f" border: 1px solid {SiColors.LINE};"
            f" border-radius: 16px; }}")

    def _build_device_block(self, did: str, dev):
        meta = self._devices_meta.get(did) or {}
        name = (dev.name if dev is not None
                else meta.get("name") or did)
        room = (dev.room_name if dev is not None
                else meta.get("room") or "")
        online = bool(dev.online if dev is not None
                      else meta.get("online", True))

        host = QWidget()
        host.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        lay = QVBoxLayout(host)
        lay.setContentsMargins(6, 4, 6, 0)
        lay.setSpacing(2)

        head = QHBoxLayout()
        head.setSpacing(6)
        name_lab = QLabel(f"{name}  ·  {room}".rstrip(" ·"))
        name_lab.setFont(
            QFont("Microsoft YaHei UI", 9, QFont.Weight.DemiBold))
        name_lab.setStyleSheet(
            f"color: {SiColors.TEXT_PRIMARY if online else SiColors.OFFLINE_TEXT};"
            " background: transparent;")
        head.addWidget(name_lab, 1)
        btn = PowerButton(26, icon_size=20)
        btn.set_online(online)

        def _toggle(checked=False, d=did, b=btn):
            b.set_busy(True)
            self._jobs.submit(
                lambda: self._service.toggle_power(d),
                on_success=lambda ns, bb=b: bb.set_state(ns),
                on_error=lambda e, bb=b: bb.set_busy(False),
            )
        btn.clicked.connect(_toggle)
        head.addWidget(btn)
        lay.addLayout(head)

        popup = QuickOpsPopup(self._service, self._jobs,
                              self._fake_device(dev, did),
                              parent=host, inline=True, show_header=False)
        # 调节项异步长出后按内容收放窗口高度
        popup.loaded.connect(lambda: QTimer.singleShot(0, self._refit))
        lay.addWidget(popup)
        return host

    @staticmethod
    def _fake_device(dev, did: str):
        if dev is not None:
            return dev
        from app.core.models import DeviceInfo
        return DeviceInfo(did=did, name=did, model="",
                          home_name="", room_name="", online=True)

    # ---------- 配置应用 ----------

    def apply_config(self, cfg: dict) -> None:
        old_title = _auto_title(self._cfg)
        changed_scale = (cfg.get("scale") != self._cfg.get("scale"))
        self._cfg = dict(cfg)
        self._devices_meta = dict(cfg.get("devices") or {})
        topmost = bool(cfg.get("topmost", True))
        has = bool(self.windowFlags() & Qt.WindowType.WindowStaysOnTopHint)
        if topmost != has:
            self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, topmost)
            self.show()
        # 背景透明度：只改卡片底色 alpha（控件/文字/边框不透）
        if "bg_alpha" in cfg:
            self._paint_bg()
        if changed_scale:
            self._refit()
        if self._handle is not None:
            new_title = _auto_title(self._cfg)
            if new_title != old_title:
                self._handle.set_title(new_title)
        self.move(cfg.get("x", self.x()), cfg.get("y", self.y()))

    def _set_scale(self, scale: int) -> None:
        """缩放手柄回调：1% 整数步进写入配置并即时生效。"""
        self._manager.update(self._cfg["id"], "scale",
                             max(50, min(200, int(scale))))

    def _refit(self) -> None:
        """按内容当前实际尺寸重设可视区（行内调节异步加载后调用）。"""
        if self._proxy is None or self._content is None:
            return
        scale = self._cfg.get("scale", 100) / 100.0
        self._content.adjustSize()
        w = self._content.width() or _DESIGN_W + 16
        h = self._content.height() or 120
        self._proxy.setScale(scale)
        self._view.setFixedSize(max(48, round(w * scale)),
                                max(30, round(h * scale)))
        self.adjustSize()

    def _notify_moved(self) -> None:
        self._manager.move_done(self._cfg["id"], self.x(), self.y())
