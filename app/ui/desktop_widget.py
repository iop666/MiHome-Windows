# SPDX-License-Identifier: GPL-3.0-or-later
# MiHome-Windows: 米家设备的 Windows 桌面控制端
# Copyright (C) 2026 MiHome-Windows contributors
"""桌面小组件窗口：多设备常驻桌面，支持缩放/置顶/锁位/背景透明度。

实现要点：
- 顶层无边框 Tool 窗口（不占任务栏/Alt+Tab）；
- 内容经 QGraphicsProxyWidget 承载，scale/100 倍缩放（1% 步进由
  设置页整数步进调节），交互（滑块/按钮）可经代理正常操作；
- 顶部细手柄在「未锁定」时可拖拽移动，松手回调 Manager 落盘坐标；
  locked=True 时不可拖动；
- bg_alpha 以窗口整体透明度呈现（0 全透～100 不透），可透出桌面。
"""

from PySide6.QtCore import QEvent, QPoint, Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QFrame,
    QGraphicsProxyWidget,
    QGraphicsScene,
    QGraphicsView,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.core.jobs import JobExecutor
from app.core.service import MijiaService
from app.ui.power_button import PowerButton
from app.ui.quick_ops import QuickOpsPopup
from app.ui.si_theme import SiColors

_DESIGN_W = 252
_HANDLE_H = 24


class _HandleBar(QFrame):
    """小组件拖拽手柄：未锁定时整条可拖动窗口。"""

    def __init__(self, owner: "DesktopWidget", locked: bool):
        super().__init__()
        self._owner = owner
        self._press = None
        self.setObjectName("widgetHandle")
        self.setFixedHeight(_HANDLE_H)
        self.setCursor(Qt.CursorShape.OpenHandCursor if not locked
                       else Qt.CursorShape.ArrowCursor)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(8, 0, 8, 0)
        lay.setSpacing(4)
        icon = QLabel("◈")
        icon.setStyleSheet(f"color: {SiColors.THEME}; background: transparent;")
        lay.addWidget(icon)
        title = QLabel("米家小组件")
        title.setFont(QFont("Microsoft YaHei UI", 8, QFont.Weight.DemiBold))
        title.setStyleSheet(f"color: {SiColors.TEXT_SECONDARY}; background: transparent;")
        lay.addWidget(title)
        lay.addStretch(1)
        if locked:
            lock = QLabel("🔒")
            lock.setToolTip("已锁定位置：在「设置 → 桌面小组件」解锁后可拖动")
            lock.setStyleSheet("color: transparent; background: transparent;")
            lay.addWidget(lock)
        self.setStyleSheet(
            f"QFrame#widgetHandle {{ background: transparent; border: none; }}")
        self.installEventFilter(self)

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


class DesktopWidget(QWidget):
    def __init__(self, manager, service: MijiaService, jobs: JobExecutor,
                 cfg: dict):
        super().__init__(None)
        self._manager = manager
        self._service = service
        self._jobs = jobs
        self._cfg = dict(cfg)
        self._drag_press: QPoint | None = None
        self._devices_meta = dict(cfg.get("devices") or {})

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
        card = self._build_card()
        self._content = card
        self._proxy = self._scene.addWidget(card)
        self._apply_scale_size()

    def _build_card(self) -> QWidget:
        card = QWidget()
        card.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        card.setStyleSheet(
            f"QWidget {{ background: {SiColors.CARD}; border-radius: 14px; }}")
        card.setFixedWidth(_DESIGN_W)
        lay = QVBoxLayout(card)
        lay.setContentsMargins(4, 4, 4, 8)
        lay.setSpacing(4)
        lay.addWidget(_HandleBar(self, self._cfg.get("locked", True)))
        devices = self._manager.devices_lookup() if hasattr(self._manager,
                                                            "devices_lookup") else {}
        dids = [d for d in self._cfg.get("dids", [])]
        for did in dids:
            block = self._build_device_block(did, devices.get(did))
            if block is not None:
                lay.addWidget(block)
        return card

    def _build_device_block(self, did: str, dev):
        meta = self._devices_meta.get(did) or {}
        name = (dev.name if dev is not None
                else meta.get("name") or did)
        room = (dev.room_name if dev is not None
                else meta.get("room") or "")
        online = bool(dev.online if dev is not None else meta.get("online", True))

        host = QWidget()
        host.setStyleSheet("background: transparent;")
        lay = QVBoxLayout(host)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(2)

        head = QHBoxLayout()
        head.setSpacing(6)
        name_lab = QLabel(f"{name}  ·  {room}".rstrip(" ·"))
        name_lab.setFont(QFont("Microsoft YaHei UI", 9, QFont.Weight.DemiBold))
        name_lab.setStyleSheet(
            f"color: {SiColors.TEXT_PRIMARY if online else SiColors.OFFLINE_TEXT};"
            " background: transparent;")
        head.addWidget(name_lab, 1)
        head.addStretch(0)
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

        # 行内调节（自动常用/自选子集同托盘语义；无可用项时 QuickOpsPopup
        # 内嵌模式自行发 empty 并自我删除，名称行保留）
        popup = QuickOpsPopup(self._service, self._jobs,
                              self._fake_device(dev, did),
                              parent=host, inline=True, show_header=False)
        lay.addWidget(popup)
        return host

    @staticmethod
    def _fake_device(dev, did: str):
        """QuickOpsPopup 只需要 device.did/name/room/online/device.model。"""
        if dev is not None:
            return dev
        from app.core.models import DeviceInfo
        return DeviceInfo(did=did, name=did, model="",
                          home_name="", room_name="", online=True)

    # ---------- 配置应用 ----------

    def apply_config(self, cfg: dict) -> None:
        changed_scale = (cfg.get("scale") != self._cfg.get("scale"))
        self._cfg = dict(cfg)
        self._devices_meta = dict(cfg.get("devices") or {})
        # 置顶标记
        topmost = bool(cfg.get("topmost", True))
        has = bool(self.windowFlags() & Qt.WindowType.WindowStaysOnTopHint)
        if topmost != has:
            self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, topmost)
            self.show()
        # 透明度
        alpha = max(10, int(cfg.get("bg_alpha", 90)))
        self.setWindowOpacity(alpha / 100.0)
        if changed_scale:
            self._apply_scale_size()
        # 拖动可用性由手柄内部读取 cfg；此处仅移动窗口位置
        self.move(cfg.get("x", self.x()), cfg.get("y", self.y()))

    def _apply_scale_size(self) -> None:
        if self._proxy is None or self._content is None:
            return
        scale = self._cfg.get("scale", 100) / 100.0
        self._content.adjustSize()
        w = self._content.width() or _DESIGN_W
        h = self._content.height() or 120
        self._proxy.setScale(scale)
        self._view.setFixedSize(max(40, round(w * scale)),
                                max(24, round(h * scale)))
        self.adjustSize()

    def _notify_moved(self) -> None:
        self._manager.move_done(self._cfg["id"], self.x(), self.y())
