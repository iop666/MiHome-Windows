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
        self.installEventFilter(self)

    def set_title(self, title: str) -> None:
        self.title_lab.setText(title)

    def eventFilter(self, obj, event) -> bool:  # noqa: N802
        et = event.type()
        if self._owner._cfg.get("locked", True):
            # 锁定时点击手柄不移动，明确提示去设置解锁
            if et == QEvent.MouseButtonPress and event.button() == Qt.LeftButton:
                from app.ui.toast import Toast
                Toast.info(self._owner,
                           "小组件已锁定位置：请在「设置 → 桌面小组件」解锁后移动",
                           2200)
                return True
            return super().eventFilter(obj, event)
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

        self._paint_bg()
        self._proxy = self._scene.addWidget(outer)
        QTimer.singleShot(0, self._refit)

    def _paint_bg(self) -> None:
        """背景与外围边框透明度一致（0% 时只剩不透明控件浮于桌面）。"""
        if self._card is None:
            return
        alpha = max(0, int(self._cfg.get("bg_alpha", 90)))
        rgba = _hex_rgba(SiColors.CARD, alpha)
        border = _hex_rgba(SiColors.LINE, max(alpha, 1))
        self._card.setStyleSheet(
            f"QFrame#widgetCard {{ background: {rgba};"
            f" border: 1px solid {border};"
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
        lay.setSpacing(4)

        # 「开关」行与下方调节模块同款式（SURFACE 圆角功能卡）
        head_card = QFrame()
        head_card.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        head_card.setStyleSheet(
            f"QFrame {{ background: {SiColors.SURFACE};"
            f" border: none; border-radius: 10px; }}")
        head = QHBoxLayout(head_card)
        head.setContentsMargins(10, 7, 10, 7)
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
        lay.addWidget(head_card)

        # 控件自选：cfg.device_ops[did] 为空列表=只留开关行，None=自动常用
        ops_map = self._cfg.get("device_ops") or {}
        op_names = ops_map.get(did)
        popup = QuickOpsPopup(self._service, self._jobs,
                              self._fake_device(dev, did),
                              parent=host, inline=True, show_header=False,
                              op_names=op_names)
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

    def _content_sig(self, cfg: dict) -> tuple:
        """内容结构指纹：dids/设备元信息/每设备控件选择 变化才重建。"""
        return (tuple(cfg.get("dids", [])),
                tuple(sorted((cfg.get("devices") or {}).items())),
                tuple(sorted((cfg.get("device_ops") or {}).items())))

    def apply_config(self, cfg: dict) -> None:
        old_title = _auto_title(self._cfg)
        old_sig = self._content_sig(self._cfg)
        changed_scale = (cfg.get("scale") != self._cfg.get("scale"))
        self._cfg = dict(cfg)
        self._devices_meta = dict(cfg.get("devices") or {})
        topmost = bool(cfg.get("topmost", True))
        has = bool(self.windowFlags() & Qt.WindowType.WindowStaysOnTopHint)
        if topmost != has:
            self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, topmost)
            self.show()
        # 背景透明度：卡片底色与外围边框同透明度变化，控件保持不透明
        if "bg_alpha" in cfg:
            self._paint_bg()
        # 内容（设备列表/名称/控件选择）变化：整卡重建，避免残留 did 数字
        if self._content_sig(self._cfg) != old_sig:
            self._rebuild_content()
        if changed_scale:
            self._refit()
        if self._handle is not None:
            new_title = _auto_title(self._cfg)
            if new_title != old_title:
                self._handle.set_title(new_title)
        self.move(cfg.get("x", self.x()), cfg.get("y", self.y()))

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
