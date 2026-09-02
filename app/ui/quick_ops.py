# SPDX-License-Identifier: GPL-3.0-or-later
# MiHome-Windows: 米家设备的 Windows 桌面控制端
# Copyright (C) 2026 MiHome-Windows contributors
"""设备卡片的快捷操作弹层（Qt.Popup，点击卡片上「调节」按钮呼出）。

在卡片上直接调节常用参数（亮度/色温/音量等滑块、小枚举切换），
不必进入详情工作台。控件在每次呼出时按当前调色板现建（取色即新），
因此主题切换后重新呼出即为新配色，无需 retheme 注册。

实现要点：
- 数据（spec 推导的可调项 + 当前值批量回读）经 JobExecutor 后台获取，
  拿到后才渲染行控件；无可用项时提示后自动收起。
- 每个控件用闭包持有自己的取值/回显状态（互不串扰）；滑块松手才提交
  （write_quick_value），失败 Toast 提示。
- 弹层自身直接承载内容布局（不再包一层 root），保证 adjustSize 有效；
  show 延迟到本事件循环之后：在按钮的 mouse 事件里立刻 show Popup，
  紧随其后的 MouseRelease 会被 Qt 当作「点击弹层外部」而秒关弹层。
"""

import shiboken6

from PySide6.QtCore import QPoint, Qt, QTimer, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from app.core.jobs import JobExecutor
from app.core.models import DeviceInfo
from app.core.service import MijiaService
from app.ui.si_theme import SiColors

_PANEL_W = 292
_PANEL_MAX_H = 400


def _short_desc(desc: str) -> str:
    """'Brightness / 亮度' -> '亮度'（与详情工作台一致取中文尾段）。"""
    if "/" in desc:
        return desc.split("/")[-1].strip()
    return desc.strip()


def _decimals_of(step) -> int:
    try:
        text = f"{float(step):g}"
    except (TypeError, ValueError):
        return 0
    return len(text.split(".")[1]) if "." in text else 0


class QuickOpsPopup(QFrame):
    """一套自取数/自渲染的可调控件。

    - 默认弹层形态（Qt.Popup，用完 deleteLater）用于卡片快捷操作；
    - inline=True 时不做弹窗（无窗口标志/无面板底色），直接嵌进宿主
      布局，供托盘快捷窗口行内展开等场景复用；
    - show_header=False 时省略设备名/房间标题行（标题由宿主提供）。
    """

    empty = Signal()  # 无可用调节项（inline 场景宿主据此收起/提示）

    def __init__(self, service: MijiaService, jobs: JobExecutor,
                 device: DeviceInfo, parent=None,
                 inline: bool = False, show_header: bool = True,
                 op_names: list[str] | None = None):
        """op_names=None 用默认常用项（≤2 滑块+≤2 枚举）；否则按名筛选。"""
        super().__init__(parent)
        self._service = service
        self._jobs = jobs
        self._device = device
        self._did = device.did
        self._online = device.online
        self._inline = inline
        self._op_names = op_names
        self._anchor: QPoint | None = None
        self._values: dict[str, object] = {}

        if not inline:
            self.setWindowFlags(
                Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint)
            self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
            self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
            self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
            self.setStyleSheet(
                f"QFrame#quickPanel {{ background: {SiColors.WINDOW_BG};"
                f" border: 1px solid {SiColors.LINE}; border-radius: 12px; }}")
        # 弹层自身承载内容布局（边框圆角由背景绘制承担）
        self._lay = QVBoxLayout(self)
        self._lay.setContentsMargins(14, 12, 14, 12) if not inline \
            else self._lay.setContentsMargins(2, 4, 2, 4)
        self._lay.setSpacing(6)
        if not inline:
            self.setFixedWidth(_PANEL_W)

        if show_header:
            title = QLabel(_short_desc(self._device.name))
            title.setFont(QFont("Microsoft YaHei UI", 11, QFont.Weight.DemiBold))
            title.setStyleSheet(
                f"color: {SiColors.TEXT_PRIMARY}; background: transparent;")
            sub = QLabel(self._device.room_name
                         + (" · 离线" if not self._online else ""))
            sub.setStyleSheet(
                f"color: {SiColors.TEXT_SECONDARY}; background: transparent;"
                f" font-size: 8pt;")
            self._lay.addWidget(title)
            self._lay.addWidget(sub)

        self._hint = QLabel("正在读取可调项…")
        self._hint.setStyleSheet(
            f"color: {SiColors.TEXT_SECONDARY}; background: transparent;"
            f" font-size: 9pt;")
        self._lay.addWidget(self._hint)

        self._jobs.submit(
            self._fetch,
            on_success=self._render,
            on_error=self._load_failed,
        )

    # ---------- 后台取数 ----------

    def _fetch(self):
        all_defs = self._service.quick_op_candidates(self._did)
        defs = self._subset(all_defs)
        names = [d.name for d in defs]
        values: dict[str, object] = {}
        if names:
            try:
                values = self._service.read_quick_values(self._did, names) or {}
            except Exception:
                pass  # 读不到值仍可调（从下限起步），不阻塞面板
        return defs, values

    def _subset(self, all_defs) -> list:
        """按 op_names 自选过滤；None 时取默认常用精简集。"""
        if self._op_names is None:
            sliders = [d for d in all_defs if d.kind == "slider"]
            enums = [d for d in all_defs if d.kind == "enum"]
            return (sliders[:2] + enums[:2])[:4]
        by_name = {d.name: d for d in all_defs}
        return [by_name[n] for n in self._op_names if n in by_name]

    def _load_failed(self, error: Exception) -> None:
        if not shiboken6.isValid(self):
            return
        from app.ui.toast import Toast
        Toast.info(self, f"加载快捷操作失败：{error}", 3000)
        self.close()

    # ---------- 渲染 ----------

    def _render(self, payload) -> None:
        if not shiboken6.isValid(self):
            return
        defs, values = payload
        if not defs:
            if self._inline:
                # 内嵌场景由宿主决定收起/提示，自行只发信号不弹窗
                self.empty.emit()
                self.deleteLater()
                return
            from app.ui.toast import Toast
            Toast.info(self, f"「{self._device.name}」暂无快捷可调项", 2200)
            self.close()
            return
        self._hint.hide()
        self._values = dict(values or {})
        for op in defs:
            self._lay.addWidget(self._build_op_row(op))
        if not self._inline:
            self.adjustSize()
            if self.height() > _PANEL_MAX_H:
                self.setFixedHeight(_PANEL_MAX_H)
        self.setEnabled(self._online)
        self._place()

    def _build_op_row(self, op) -> QWidget:
        # 行卡片化：独立底 + 圆角，区分于弹层/行底色
        host = QFrame()
        host.setObjectName("quickOpCard")
        host.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        host.setStyleSheet(
            f"QFrame#quickOpCard {{ background: {SiColors.SURFACE};"
            f" border: none; border-radius: 10px; }}")
        lay = QVBoxLayout(host)
        lay.setContentsMargins(10, 6, 10, 8)
        lay.setSpacing(4)

        head = QHBoxLayout()
        head.setSpacing(6)
        lab = QLabel(_short_desc(op.desc))
        lab.setFont(QFont("Microsoft YaHei UI", 9, QFont.Weight.Medium))
        lab.setStyleSheet(f"color: {SiColors.TEXT_PRIMARY}; background: transparent;")
        head.addWidget(lab)
        head.addStretch(1)
        val_label = QLabel("—")
        val_label.setStyleSheet(
            f"color: {SiColors.TEXT_SECONDARY}; background: transparent; font-size: 9pt;")
        head.addWidget(val_label)
        lay.addLayout(head)

        if op.kind == "slider":
            ctrl = self._make_slider_row(op, val_label)
        else:
            ctrl = self._make_enum_row(op)
        lay.addWidget(ctrl)
        return host

    # ---------- 滑块（闭包持有自身回显，避免多行串扰） ----------

    def _make_slider_row(self, op, val_label: QLabel) -> QSlider:
        low, high = op.range[0], op.range[1]
        step = op.range[2] if len(op.range) >= 3 else 1
        decimals = 0 if op.type != "float" else _decimals_of(step)
        scale = 10 ** decimals if decimals else 1

        slider = QSlider(Qt.Horizontal)
        slider.setFixedHeight(22)
        slider.setCursor(Qt.PointingHandCursor)
        slider.setRange(int(round(low * scale)), int(round(high * scale)))
        slider.setStyleSheet(self._slider_qss())

        def _show(v: int) -> None:
            val_label.setText(f"{v / scale:g}")

        slider.valueChanged.connect(_show)
        slider.sliderReleased.connect(
            lambda s=slider: self._commit_value(
                op.name, s.value() / scale,
                on_success=lambda v: val_label.setText(f"{v:g}")))

        raw = self._values.get(op.name)
        if isinstance(raw, (int, float)) and not isinstance(raw, bool):
            slider.setValue(int(round(float(raw) * scale)))
        else:
            slider.setValue(int(round(low * scale)))
        _show(slider.value())
        return slider

    def _slider_qss(self) -> str:
        return (
            f"QSlider::groove:horizontal {{ height: 4px; background: {SiColors.SURFACE};"
            f" border-radius: 2px; }}"
            f"QSlider::sub-page:horizontal {{ background: {SiColors.THEME}; border-radius: 2px; }}"
            f"QSlider::add-page:horizontal {{ background: {SiColors.SURFACE}; border-radius: 2px; }}"
            f"QSlider::handle:horizontal {{ width: 15px; height: 15px; background: {SiColors.THUMB};"
            f" border-radius: 7px; margin: -6px 0; }}"
            f"QSlider::handle:horizontal:disabled {{ background: {SiColors.OFFLINE_SUB}; }}"
        )

    # ---------- 枚举 ----------

    def _make_enum_row(self, op) -> QWidget:
        options = op.value_list or []
        grid = QGridLayout()
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(6)
        grid.setVerticalSpacing(6)
        buttons: list[QPushButton] = []
        for index, item in enumerate(options):
            label = (item.get("desc_zh_cn")
                     or item.get("description") or str(item["value"]))
            btn = QPushButton(str(label))
            btn.setCursor(Qt.PointingHandCursor)
            btn.setFixedHeight(26)
            btn.setFont(QFont("Microsoft YaHei UI", 8))
            btn.setStyleSheet(self._enum_qss(False))
            btn.clicked.connect(
                lambda _, v=item["value"], b=btn: self._pick_enum(op.name, v, b))
            buttons.append(btn)
            grid.addWidget(btn, index // 3, index % 3)
        current = self._values.get(op.name)
        for btn, item in zip(buttons, options):
            if item["value"] == current:
                self._highlight_enum(btn, True)
        return self._wrap_grid(grid)

    @staticmethod
    def _wrap_grid(grid) -> QWidget:
        host = QWidget()
        host.setStyleSheet("background: transparent;")
        host.setLayout(grid)
        return host

    def _enum_qss(self, active: bool) -> str:
        if active:
            return (
                f"QPushButton {{ background: {SiColors.THEME}; border: 1px solid {SiColors.THEME};"
                f" border-radius: 7px; color: {SiColors.ON_THEME_TEXT}; font-weight: 600; }}")
        return (
            f"QPushButton {{ background: {SiColors.SURFACE}; border: 1px solid {SiColors.LINE};"
            f" border-radius: 7px; color: {SiColors.TEXT_PRIMARY}; }}"
            f"QPushButton:hover {{ border-color: {SiColors.THEME}; }}")

    def _highlight_enum(self, btn: QPushButton, active: bool) -> None:
        btn.setStyleSheet(self._enum_qss(active))

    def _pick_enum(self, name: str, value, btn: QPushButton) -> None:
        self._highlight_enum(btn, True)
        self._commit_value(name, value)

    # ---------- 提交（统一入口；name 必传，避免跨控件串扰） ----------

    def _commit_value(self, name: str, value, on_success=None) -> None:
        if not name or not shiboken6.isValid(self):
            return
        self.setEnabled(False)
        did = self._did

        def _write():
            self._service.write_quick_value(did, name, value)
            return value

        self._jobs.submit(
            _write,
            on_success=lambda v: self._on_written(name, v, on_success),
            on_error=lambda e: self._on_write_error(e),
        )

    def _on_written(self, name: str, value, on_success) -> None:
        if not shiboken6.isValid(self):
            return
        self._values[name] = value
        if on_success is not None:
            on_success()
        self.setEnabled(True)

    def _on_write_error(self, error: Exception) -> None:
        if not shiboken6.isValid(self):
            return
        self.setEnabled(True)
        from app.ui.toast import Toast
        Toast.info(self, f"设置失败：{error}", 3500)

    # ---------- 定位与显示 ----------

    def popup_near(self, anchor_global: QPoint) -> None:
        """在锚点右下方弹出；延迟到鼠标释放后再 show，避免秒关。"""
        if self._inline:
            return
        self._anchor = anchor_global
        QTimer.singleShot(0, self._place)

    def _place(self) -> None:
        """按当前几何把窗口放到锚点附近并收进屏幕（内容就绪后再调一次）。"""
        if (not shiboken6.isValid(self) or self._inline
                or self._anchor is None):
            return
        from PySide6.QtGui import QGuiApplication
        screen = QGuiApplication.primaryScreen()
        geo = screen.availableGeometry() if screen is not None else None
        x = self._anchor.x() + 4
        y = self._anchor.y() + 8
        if geo is not None:
            x = max(geo.left() + 8, min(x, geo.right() - self.width() - 8))
            y = max(geo.top() + 8, min(y, geo.bottom() - self.height() - 8))
        self.move(x, y)
        self.show()
        self.raise_()
