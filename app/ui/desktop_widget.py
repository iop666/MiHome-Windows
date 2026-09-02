# SPDX-License-Identifier: GPL-3.0-or-later
# MiHome-Windows: 米家设备的 Windows 桌面控制端
# Copyright (C) 2026 MiHome-Windows contributors
"""桌面小组件窗口：多设备常驻桌面，仅显示设备控件，无标题栏。

实现要点：
- 顶层无边框 Tool 窗口（不占任务栏/Alt+Tab），WA_TranslucentBackground；
- 内容经 QGraphicsProxyWidget 承载 scale/100 倍缩放（1% 步进调节），
  调节行加载完成后自动按内容收放高度（默认展示完整，不留空白）；
- 不再显示顶部标题/手柄条，内容直接以每台设备的控件行开始；
  未锁定时按住卡片空白处（非按钮/滑块的区域）即可拖动摆放，
  锁定时点击空白区弹两行提示（去设置页解锁）；
- 「背景透明度」只作用卡片底色与外围边框（rgba），控件保持不透明；
- 开关状态：构建/显示后与每 6s 轮询批量回读真实开关状态并回填，
  点击开关后同时更新本窗与同设备其他小组件，避免出现「开着却显示关」。
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
from app.ui.si_theme import SiColors, palette_for
from app.ui.toast import Toast

_DESIGN_W = 268
# 开关圆钮与主界面电源钮同尺寸，避免与下方调节行高度差过大
_POWER_BTN_SIZE = 36
# 小组件自轮询开关状态的周期（与主窗口轮询节奏一致）
_POWER_POLL_MS = 4000


def _hex_rgba(hex_color: str, alpha: int) -> str:
    """#RRGGBB + 0..100 → rgba(r,g,b,a)。"""
    h = hex_color.lstrip("#")
    if len(h) != 6:
        return hex_color
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    a = max(0, min(alpha, 100)) / 100.0
    return f"rgba({r},{g},{b},{a:g})"


def _resolve_colors(mode: str):
    """小组件取色对象：固定 light/dark 用代理，其余（跟随应用）用全局。"""
    if mode in ("light", "dark"):
        try:
            return palette_for(mode)
        except Exception:
            pass
    return SiColors


class DesktopWidget(QWidget):
    def __init__(self, manager, service: MijiaService, jobs: JobExecutor,
                 cfg: dict):
        super().__init__(None)
        self._manager = manager
        self._service = service
        self._jobs = jobs
        self._cfg = dict(cfg)
        self._devices_meta = dict(cfg.get("devices") or {})
        # 小组件外观：app=跟随应用主题；light/dark=本组件固定明暗
        self._theme_mode = str(cfg.get("theme_mode") or "app")
        self._col = _resolve_colors(self._theme_mode)
        self._card: QWidget | None = None
        # did -> 电源钮（就地刷新状态用）；did -> 最近一次已知开关状态
        self._power_btns: dict[str, PowerButton] = {}
        self._power_known: dict[str, bool | None] = {}
        # did -> 行内调节弹层（展开时同步/轮询其滑块与枚举的真实值）
        self._op_popups: dict[str, object] = {}
        # 未锁定时按住空白拖动；None = 未在拖动
        self._drag_offset: QPoint | None = None
        self._press_pos: QPoint | None = None

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

        # 显示期间轮询真实开关状态（小组件独立于主窗口轮询）
        self._power_timer = QTimer(self)
        self._power_timer.setInterval(_POWER_POLL_MS)
        self._power_timer.timeout.connect(self._refresh_power_states)

        self._proxy: QGraphicsProxyWidget | None = None
        self._content: QWidget | None = None
        self._rebuild_content()
        self.apply_config(self._cfg)

    # ---------- 窗口显隐与轮询 ----------

    def showEvent(self, event) -> None:  # noqa: N802 (Qt 命名约定)
        super().showEvent(event)
        self._power_timer.start()
        QTimer.singleShot(120, self._refresh_power_states)

    def hideEvent(self, event) -> None:  # noqa: N802 (Qt 命名约定)
        self._power_timer.stop()
        super().hideEvent(event)

    # ---------- 构建内容 ----------

    def _rebuild_content(self) -> None:
        if self._content is not None:
            self._scene.removeItem(self._proxy)
            self._content.deleteLater()
            self._content = None
            self._proxy = None
        self._power_btns.clear()
        self._op_popups.clear()
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
        # 四周边距对称（含每台设备的 host 边距）：控件到卡片四边的留白
        # 等距，避免上下窄左右宽的失衡观感
        lay.setContentsMargins(6, 6, 6, 6)
        lay.setSpacing(6)

        devices = (self._manager.devices_lookup()
                   if hasattr(self._manager, "devices_lookup") else {})
        for did in [d for d in self._cfg.get("dids", [])]:
            block = self._build_device_block(did, devices.get(did))
            if block is not None:
                lay.addWidget(block)

        self._paint_bg()
        self._apply_drag_cursor()
        self._proxy = self._scene.addWidget(outer)
        # 卡片本体与内容树最外层都接收未被控件消费的鼠标事件：
        # 空白处拖动 / 锁定时点击弹两行提示（事件先在 card 停下）
        self._card.installEventFilter(self)
        outer.installEventFilter(self)
        QTimer.singleShot(0, self._refit)

    def _paint_bg(self) -> None:
        """背景与外围边框透明度一致（0% 时只剩不透明控件浮于桌面）。"""
        if self._card is None:
            return
        alpha = max(0, int(self._cfg.get("bg_alpha", 90)))
        rgba = _hex_rgba(self._col.CARD, alpha)
        border = _hex_rgba(self._col.LINE, max(alpha, 1))
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
        lay.setContentsMargins(6, 6, 6, 6)
        lay.setSpacing(4)

        # 「开关」行与下方调节模块同款式（SURFACE 圆角功能卡）
        head_card = QFrame()
        head_card.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        head_card.setStyleSheet(
            f"QFrame {{ background: {self._col.SURFACE};"
            f" border: none; border-radius: 10px; }}")
        head = QHBoxLayout(head_card)
        head.setContentsMargins(10, 7, 10, 7)
        head.setSpacing(6)
        name_lab = QLabel(f"{name}  ·  {room}".rstrip(" ·"))
        name_lab.setFont(
            QFont("Microsoft YaHei UI", 9, QFont.Weight.DemiBold))
        name_lab.setStyleSheet(
            f"color: {self._col.TEXT_PRIMARY if online else self._col.OFFLINE_TEXT};"
            " background: transparent;")
        head.addWidget(name_lab, 1)
        btn = PowerButton(_POWER_BTN_SIZE, icon_size=24, colors=self._col)
        btn.set_online(online)
        # 重建/回填时立即用最近已知状态（未确认前保持未知态）
        known = self._power_known.get(did)
        if known is not None:
            btn.set_state(known)
        self._power_btns[did] = btn

        def _toggle(checked=False, d=did, b=btn):
            b.set_busy(True)
            self._jobs.submit(
                lambda: self._service.toggle_power(d),
                on_success=lambda ns, bb=b: self._on_toggle_done(d, ns, bb),
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
                              op_names=op_names, colors=self._col)
        # 行内调节项：登记引用（周期回读/别处写入后就地刷新）
        self._op_popups[did] = popup
        popup._change_cb = lambda d, n, v: self._on_quick_value_written(d, n, v)
        # 调节项异步长出后按内容收放窗口高度；无可用项收起后同样校正
        popup.loaded.connect(lambda: QTimer.singleShot(0, self._refit))
        popup.empty.connect(lambda: QTimer.singleShot(0, self._refit))
        lay.addWidget(popup)
        return host

    @staticmethod
    def _fake_device(dev, did: str):
        if dev is not None:
            return dev
        from app.core.models import DeviceInfo
        return DeviceInfo(did=did, name=did, model="",
                          home_name="", room_name="", online=True)

    # ---------- 开关状态：回读 / 轮询 / 同步 ----------

    def _refresh_power_states(self) -> None:
        """批量回读本窗各设备开关状态并就地刷新（不重建，杜绝闪烁）。"""
        dids: list[str] = []
        meta = self._cfg.get("devices") or {}
        for did, btn in self._power_btns.items():
            if not btn.isEnabled():
                continue  # 离线设备不读（云端缓存值不可信）
            if bool((meta.get(did) or {}).get("online", True)):
                dids.append(did)
        if dids:
            self._jobs.submit(
                lambda: self._service.power_states(dids),
                on_success=self._apply_power_states,
                on_error=lambda _: None,
            )
        # 调节项真实值（亮度/色温等）同样随周期回读刷新
        self._refresh_quick_values()

    def _refresh_quick_values(self) -> None:
        """展开的调节行定期回读当前真实值，捕捉设备端/别处改动。"""
        import shiboken6

        for did, popup in list(self._op_popups.items()):
            if popup is None or not shiboken6.isValid(popup):
                continue
            try:
                popup.refresh_from_cloud()
            except Exception:
                continue

    def _on_quick_value_written(self, did: str, name: str, value) -> None:
        """本窗写值成功：广播给其它小组件 + 主窗口/托盘（保持展开状态一致）。"""
        manager = getattr(self, "_manager", None)
        if manager is not None and hasattr(manager, "broadcast_quick_value"):
            try:
                manager.broadcast_quick_value(did, name, value)
            except Exception:
                pass

    def apply_quick_value(self, did: str, name: str, value) -> None:
        """外部值变化（托盘/主界面写值、周期回读）后就地刷新对应行。"""
        popup = self._op_popups.get(did)
        if popup is None:
            return
        try:
            popup.update_value(name, value)
        except Exception:
            pass

    def _apply_power_states(self, states: dict) -> None:
        for did, state in (states or {}).items():
            self._apply_power_state(did, state)

    def _apply_power_state(self, did: str, state: bool | None) -> None:
        if state is None:
            return
        self._power_known[did] = state
        btn = self._power_btns.get(did)
        if btn is not None:
            btn.set_state(state)

    def _on_toggle_done(self, did: str, state: bool, btn) -> None:
        """本窗点击开关成功：回填状态并广播（其它小组件 + 主窗口卡片/托盘）。"""
        self._power_known[did] = state
        btn.set_state(state)
        btn.set_busy(False)
        manager = getattr(self, "_manager", None)
        if manager is None:
            return
        if hasattr(manager, "power_changed_everywhere"):
            try:
                manager.power_changed_everywhere(did, state)
                return
            except Exception:
                pass
        if hasattr(manager, "broadcast_power"):
            try:
                manager.broadcast_power(did, state)
            except Exception:
                pass

    def apply_external_power(self, did: str, state: bool | None) -> None:
        """其它入口（本窗另一实例/主窗口）改开关后由 Manager 推送过来。"""
        if state is None:
            return
        self._power_known[did] = state
        btn = self._power_btns.get(did)
        if btn is not None:
            btn.set_state(state)

    # ---------- 空白拖动 / 锁定提示 ----------

    def _apply_drag_cursor(self) -> None:
        cursor = (Qt.CursorShape.OpenHandCursor
                  if not self._cfg.get("locked", True)
                  else Qt.CursorShape.ArrowCursor)
        if self._card is not None:
            self._card.setCursor(cursor)

    def eventFilter(self, obj, event) -> bool:  # noqa: N802
        """内容树最外层：未被控件消费的鼠标事件 → 拖动 / 锁定提示。

        按钮/滑块等会自行消费鼠标事件，走到这里的都是空白区域；
        锁定时按下给两行提示并吞掉事件，解锁时按下开始拖动。
        """
        if obj not in (self._content, self._card):
            return super().eventFilter(obj, event)
        et = event.type()
        locked = self._cfg.get("locked", True)
        if et == QEvent.Type.MouseButtonPress \
                and event.button() == Qt.MouseButton.LeftButton:
            if locked:
                Toast.lock_hint(self)
                return True
            # 先记录按下点；超过小阈值才真正进入拖动，避免误触挪动
            self._press_pos = event.globalPosition().toPoint()
            self._drag_offset = None
            return True
        if et == QEvent.Type.MouseMove and self._press_pos is not None \
                and event.buttons() & Qt.MouseButton.LeftButton:
            pos = event.globalPosition().toPoint()
            if self._drag_offset is None:
                origin = self.frameGeometry().topLeft()
                if (pos - self._press_pos).manhattanLength() < 4:
                    return True
                self._drag_offset = self._press_pos - origin
            self.move(pos - self._drag_offset)
            return True
        if et == QEvent.Type.MouseButtonRelease \
                and event.button() == Qt.MouseButton.LeftButton \
                and self._drag_offset is not None:
            self._drag_offset = None
            self._press_pos = None
            self._notify_moved()
            return True
        if et == QEvent.Type.MouseButtonRelease \
                and event.button() == Qt.MouseButton.LeftButton:
            # 纯点击（未形成拖动）：复位按下记录即可
            self._press_pos = None
            return False
        return super().eventFilter(obj, event)

    # ---------- 配置应用 ----------

    def _content_sig(self, cfg: dict) -> tuple:
        """内容结构指纹：外观/设备列表/元信息/控件选择 变化才重建。

        theme_mode 也进指纹：小组件单独切明/暗时颜色取色对象变了，
        必须整卡重建取新调色板。
        """
        return ((cfg.get("theme_mode") or "app"),
                tuple(cfg.get("dids", [])),
                tuple(sorted((cfg.get("devices") or {}).items())),
                tuple(sorted((cfg.get("device_ops") or {}).items())))

    def apply_config(self, cfg: dict, force_rebuild: bool = False) -> None:
        old_sig = self._content_sig(self._cfg)
        changed_scale = (cfg.get("scale") != self._cfg.get("scale"))
        lock_changed = (cfg.get("locked", True) != self._cfg.get("locked", True))
        theme_changed = ((cfg.get("theme_mode") or "app")
                         != self._theme_mode)
        self._cfg = dict(cfg)
        self._devices_meta = dict(cfg.get("devices") or {})
        new_mode = str(cfg.get("theme_mode") or "app")
        if new_mode != self._theme_mode:
            self._theme_mode = new_mode
            self._col = _resolve_colors(new_mode)
        topmost = bool(cfg.get("topmost", True))
        has = bool(self.windowFlags() & Qt.WindowType.WindowStaysOnTopHint)
        if topmost != has:
            self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, topmost)
            self.show()
        # 背景透明度：卡片底色与外围边框同透明度变化，控件保持不透明
        if "bg_alpha" in cfg:
            self._paint_bg()
        # 内容变化 / 外观切换 / 全局主题重绘（force）：整卡重建取新调色板
        if force_rebuild or theme_changed \
                or self._content_sig(self._cfg) != old_sig:
            self._rebuild_content()
            if self.isVisible():
                # 重建后按钮是新的：立即回读一次真实开关状态
                QTimer.singleShot(200, self._refresh_power_states)
        if changed_scale:
            self._refit()
        if lock_changed:
            self._apply_drag_cursor()
            if self._cfg.get("locked", True):
                self._drag_offset = None
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
