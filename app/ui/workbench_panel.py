# SPDX-License-Identifier: GPL-3.0-or-later
# MiHome-Windows: 米家设备的 Windows 桌面控制端
# Copyright (C) 2026 MiHome-Windows contributors
"""设备详情工作台：可自定义的模块化控制台。

空状态引导添加，网格承载已选模块，更多菜单提供增删改，
侧滑抽屉展示全量功能清单。配置按 did 持久化到 workbench.json。
"""

import shiboken6
from typing import Any, Callable

from PySide6.QtCore import QParallelAnimationGroup, QPropertyAnimation, QTimer, Qt, Signal
from PySide6.QtCore import QEasingCurve
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from app.core import device_names, workbench_store
from app.core.models import DeviceDetail, DeviceInfo, PropInfo, enum_option_text
from app.core.service import MijiaService, format_metrics_text
from app.ui.add_drawer import AddDrawer
from app.ui.prop_widgets import (
    GroupSection,
    build_prop_section,
    group_props,
    is_primary_slider,
)
from app.ui.si_theme import SiColors, apply_combo_qss, themed_label
from app.ui.workbench_item import WorkbenchItemWrapper


class _SpinCircle(QWidget):
    """简易旋转弧形加载指示器。"""

    def __init__(self, size: int = 36, parent=None):
        super().__init__(parent)
        self.setFixedSize(size, size)
        self._angle = 0
        self._timer = QTimer(self)
        self._timer.setTimerType(Qt.TimerType.CoarseTimer)
        self._timer.timeout.connect(self._rotate)

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        if not self._timer.isActive():
            self._timer.start(16)

    def hideEvent(self, event) -> None:  # noqa: N802
        self._timer.stop()
        super().hideEvent(event)

    def _rotate(self):
        if not shiboken6.isValid(self):
            self._timer.stop()
            return
        self._angle = (self._angle + 6) % 360
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        s = min(self.width(), self.height())
        pen = QPen(QColor(SiColors.THEME), max(2, s // 12), Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
        p.setPen(pen)
        m = s // 2
        r = m - s // 12
        p.drawArc(m - r, m - r, r * 2, r * 2, self._angle * 16, 270 * 16)
        p.end()


class WorkbenchPanel(QWidget):
    metrics_updated = Signal(str, str)
    renamed = Signal(str, str)  # (did, 新显示名)：重命名/恢复默认后广播

    def __init__(self, service: MijiaService, jobs, parent=None,
                 on_value_written=None):
        super().__init__(parent)
        self._service = service
        self._jobs = jobs
        # 写属性成功后的回调（did, name, value）：宿主注入，用于把新值
        # 同步给托盘展开行/桌面小组件等其它入口
        self._value_written_cb = on_value_written
        self._current_did: str | None = None
        self._current_online: bool = True
        self._detail: DeviceDetail | None = None
        self._sections: dict[str, QWidget] = {}
        self._module_defs: list[tuple[str, str, str]] = []
        self._module_builders: dict[str, Callable[[], QWidget]] = {}
        self._active_keys: list[str] = []
        self._wrappers: dict[str, WorkbenchItemWrapper] = {}
        self._mode = "normal"
        self._drawer: AddDrawer | None = None
        # 重排动画进行中标志：动画期间布局被禁用，再入会以错误几何结算
        self._reordering = False
        self._reorder_group: QParallelAnimationGroup | None = None
        self._current_groups: list[tuple[str, list[PropInfo], PropInfo | None]] = []
        # 模块分类表（智能默认键用）：key -> on/group-on/group/slider/other/action
        self._module_kinds: dict[str, str] = {}
        self._group_master_on: set[str] = set()
        # 动作参数映射（action_args_map 后台取回后写入，渲染动作卡时读取）
        self._action_args_map: dict[str, list] = {}
        # 写后静默与乐观值：避免设备未落盘前的旧值把 UI 弹回
        self._cooldown: dict[str, float] = {}
        self._last_written: dict[str, Any] = {}
        self._last_written_time: dict[str, float] = {}

        root = QVBoxLayout(self)
        root.setContentsMargins(20, 16, 20, 16)
        root.setSpacing(12)

        # 离线条
        self._offline_bar = QFrame()
        self._offline_bar.setStyleSheet(
            f"QFrame {{ background: {SiColors.WARN_BG}; border: 1px solid {SiColors.WARN_BORDER}; border-radius: 8px; }}")
        ob_lay = QHBoxLayout(self._offline_bar)
        ob_lay.setContentsMargins(12, 6, 12, 6)
        lab = QLabel("设备离线，控制不可用")
        lab.setStyleSheet(f"color: {SiColors.WARN_TEXT}; background: transparent; font-size: 9pt;")
        ob_lay.addWidget(lab)
        ob_lay.addStretch(1)
        self._offline_bar.hide()
        root.addWidget(self._offline_bar)

        header = QHBoxLayout()
        title_box = QVBoxLayout()
        self._title_label = QLabel("未选择设备")
        self._title_label.setObjectName("panelTitle")
        self._model_label = QLabel("选择一台设备开始控制")
        self._model_label.setObjectName("panelSubtitle")
        title_box.addWidget(self._title_label)
        title_box.addWidget(self._model_label)
        header.addLayout(title_box)
        header.addStretch(1)
        # 设备名操作：重命名 / 恢复默认（位于「刷新/编辑功能」左侧）
        self._rename_btn = QPushButton("重命名")
        self._rename_btn.setFixedSize(76, 32)
        self._rename_btn.setCursor(Qt.PointingHandCursor)
        self._rename_btn.clicked.connect(self._on_rename_clicked)
        self._rename_btn.hide()
        header.addWidget(self._rename_btn)
        self._reset_name_btn = QPushButton("恢复默认")
        self._reset_name_btn.setFixedSize(88, 32)
        self._reset_name_btn.setCursor(Qt.PointingHandCursor)
        self._reset_name_btn.clicked.connect(self._on_reset_name_clicked)
        self._reset_name_btn.hide()
        header.addWidget(self._reset_name_btn)
        self._refresh_btn = QPushButton("刷新")
        self._refresh_btn.setFixedSize(64, 32)
        self._refresh_btn.setCursor(Qt.PointingHandCursor)
        self._refresh_btn.clicked.connect(lambda: self._reload_readings(force=True))
        self._refresh_btn.hide()
        header.addWidget(self._refresh_btn)
        self._edit_btn = QPushButton("编辑功能")
        self._edit_btn.setFixedSize(80, 32)
        self._edit_btn.setCursor(Qt.PointingHandCursor)
        self._edit_btn.clicked.connect(self._toggle_manage)
        self._edit_btn.hide()
        header.addWidget(self._edit_btn)
        self._apply_header_button_styles()
        root.addLayout(header)

        # 加载态：设备信息 + 旋转弧形 + 提示，垂直居中
        self._loading = QFrame()
        self._loading.setStyleSheet("QFrame { background: transparent; }")
        load_lay = QVBoxLayout(self._loading)
        load_lay.setAlignment(Qt.AlignCenter)
        load_lay.setSpacing(16)

        self._load_name = QLabel()
        self._load_name.setAlignment(Qt.AlignCenter)
        self._load_name.setStyleSheet(
            f"color: {SiColors.TEXT_PRIMARY}; font-size: 16pt; font-weight: bold; background: transparent;")
        load_lay.addWidget(self._load_name, alignment=Qt.AlignCenter)

        self._load_room = QLabel()
        self._load_room.setAlignment(Qt.AlignCenter)
        self._load_room.setStyleSheet(
            f"color: {SiColors.TEXT_SECONDARY}; font-size: 10pt; background: transparent;")
        load_lay.addWidget(self._load_room, alignment=Qt.AlignCenter)

        self._spinner = _SpinCircle(36)
        load_lay.addWidget(self._spinner, alignment=Qt.AlignCenter)

        self._load_hint = QLabel("正在获取设备信息…")
        self._load_hint.setAlignment(Qt.AlignCenter)
        self._load_hint.setStyleSheet(
            f"color: {SiColors.TEXT_SECONDARY}; font-size: 9pt; background: transparent;")
        load_lay.addWidget(self._load_hint, alignment=Qt.AlignCenter)

        self._loading.hide()
        root.addWidget(self._loading, stretch=1)

        # 瀑布流网格：两列自适应填满，避免强制 2 列留白
        body = QScrollArea()
        body.setWidgetResizable(True)
        body.setFrameShape(QScrollArea.NoFrame)
        container = QWidget()
        container.setStyleSheet(f"background: {SiColors.WINDOW_BG};")
        outer = QHBoxLayout(container)
        outer.setContentsMargins(0, 0, 8, 0)
        outer.setSpacing(14)
        self._left_col = QVBoxLayout()
        self._left_col.setContentsMargins(0, 0, 0, 0)
        self._left_col.setSpacing(14)
        self._right_col = QVBoxLayout()
        self._right_col.setContentsMargins(0, 0, 0, 0)
        self._right_col.setSpacing(14)
        outer.addLayout(self._left_col, stretch=1)
        outer.addLayout(self._right_col, stretch=1)
        # 兼容旧代码：_grid 指向 container 布局，用于清理
        self._grid = outer
        self._left_h = 0
        self._right_h = 0
        body.setWidget(container)
        root.addWidget(body, stretch=1)

        # 空状态
        self._empty = QFrame()
        self._empty.setStyleSheet("QFrame { background: transparent; }")
        el = QVBoxLayout(self._empty)
        el.setContentsMargins(20, 40, 20, 40)
        el.setSpacing(12)
        icon = QLabel("◫")
        icon.setAlignment(Qt.AlignCenter)
        icon.setStyleSheet(f"color: {SiColors.OFFLINE_SUB}; font-size: 28pt; background: transparent;")
        el.addWidget(icon)
        self._empty_title = QLabel("此设备控制面板还是空的")
        self._empty_title.setAlignment(Qt.AlignCenter)
        self._empty_title.setStyleSheet(f"color: {SiColors.TEXT_PRIMARY}; font-size: 11pt; background: transparent;")
        el.addWidget(self._empty_title)
        self._empty_desc = QLabel("点击下方按钮添加控制功能")
        self._empty_desc.setAlignment(Qt.AlignCenter)
        self._empty_desc.setStyleSheet(f"color: {SiColors.TEXT_SECONDARY}; font-size: 9pt; background: transparent;")
        el.addWidget(self._empty_desc)
        el.addSpacing(12)
        self._empty_add_btn = QPushButton("添加功能")
        self._empty_add_btn.setCursor(Qt.PointingHandCursor)
        self._empty_add_btn.setFixedHeight(40)
        self._empty_add_btn.setStyleSheet(
            f"QPushButton {{ background: {SiColors.THEME}; color: #0b0b0e; border: none; border-radius: 12px; font-size: 10pt; font-weight: 600; padding: 0 24px; }}"
            f"QPushButton:hover {{ background: {SiColors.THEME_HOVER}; }}")
        self._empty_add_btn.clicked.connect(self._open_drawer)
        el.addWidget(self._empty_add_btn, alignment=Qt.AlignCenter)
        el.addStretch(1)
        root.addWidget(self._empty)

        # 底部添加按钮仅在管理模式下显示
        self._footer_add_btn = QPushButton("+ 添加功能")
        self._footer_add_btn.setCursor(Qt.PointingHandCursor)
        self._footer_add_btn.setFixedHeight(40)
        self._footer_add_btn.setStyleSheet(
            f"QPushButton {{ background: {SiColors.CARD}; border: 1px solid #3dbba4; border-radius: 12px; color: #3dbba4; font-size: 10pt; }}"
            f"QPushButton:hover {{ background: {SiColors.CARD_HOVER}; }}")
        self._footer_add_btn.clicked.connect(self._open_drawer)
        self._footer_add_btn.hide()
        root.addWidget(self._footer_add_btn)

        self._body = body
        self._container = container
        self.setAcceptDrops(True)
        container.setAcceptDrops(True)

    # ---------- 加载 ----------

    def show_device(self, did: str, online: bool = True, device: DeviceInfo | None = None) -> None:
        self._current_did = did
        self._current_online = online
        self._detail = None
        self._clear_workbench()
        name = device.name if device else "设备"
        room = device.room_name if device else ""
        self._title_label.setText(name)
        self._model_label.setText(room)
        self._title_label.hide()
        self._model_label.hide()
        self._load_name.setText(name)
        self._load_room.setText(room)
        self._load_hint.setText("正在获取设备信息…")
        self._update_offline_bar()
        self._refresh_btn.hide()
        self._edit_btn.hide()
        self._loading.show()
        self._jobs.submit(
            lambda: self._service.device_detail(did),
            on_success=self._on_detail_loaded,
            on_error=self._show_error,
        )

    def _on_detail_loaded(self, detail: DeviceDetail) -> None:
        if not shiboken6.isValid(self) or detail.did != self._current_did:
            return
        self._loading.hide()
        self._detail = detail
        self._title_label.setText(detail.name)
        self._model_label.setText(detail.model)
        self._title_label.show()
        self._model_label.show()
        self._build_module_defs(detail)
        keys = workbench_store.load(detail.did)
        # 首次进入：智能预置常用功能（开关 + 高频滑块等，见 _default_keys）
        if keys is None:
            pre = self._default_keys()
            if pre:
                keys = pre
                workbench_store.save(detail.did, keys)
            else:
                keys = []
        # 过滤已不存在的 key
        valid = {k for k, _, _ in self._module_defs}
        keys = [k for k in keys if k in valid]
        self._active_keys = keys
        # 动作参数需在渲染前就绪（决定动作卡形态：无参按钮/文本/参数化）
        self._action_args_map = {}
        if detail.actions:
            self._load_hint.setText("正在获取功能参数…")
            self._loading.show()
            self._jobs.submit(
                lambda: self._service.action_args_map(detail.did),
                on_success=self._on_action_args_ready,
                on_error=lambda exc: self._on_action_args_ready({}),
            )
        else:
            self._finish_show()

    def _on_action_args_ready(self, amap) -> None:
        if not shiboken6.isValid(self):
            return
        self._action_args_map = amap or {}
        self._finish_show()

    def _finish_show(self) -> None:
        if not shiboken6.isValid(self):
            return
        self._loading.hide()
        self._title_label.show()
        self._model_label.show()
        self._render_workbench()
        self._refresh_btn.show()
        self._edit_btn.show()
        self._rename_btn.show()
        # 已有本地覆盖名时给出「恢复默认」
        self._reset_name_btn.setVisible(
            device_names.get(self._current_did) is not None)

    # ---------- 设备重命名 / 恢复默认（本地显示名覆盖） ----------

    def _on_rename_clicked(self) -> None:
        did = self._current_did
        if not did:
            return
        current = self._title_label.text() or ""
        text, ok = QInputDialog.getText(
            self, "重命名设备", "给这台设备起个新名称：", text=current)
        name = (text or "").strip()
        if not ok or not name or name == current:
            return
        # 首次重命名时以当前名为“原始默认名”，之后可一键恢复
        device_names.set_name(did, name)
        self._title_label.setText(name)
        self._reset_name_btn.show()
        self.renamed.emit(did, name)

    def _on_reset_name_clicked(self) -> None:
        did = self._current_did
        if not did:
            return
        entry = device_names.get(did)
        if not entry:
            self._reset_name_btn.hide()
            return
        orig = entry.get("orig") or self._title_label.text() or did
        device_names.remove(did)
        self._title_label.setText(orig)
        self._reset_name_btn.hide()
        self.renamed.emit(did, orig)

    def _default_keys(self) -> list[str]:
        """首次进入的智能默认：主开关 + 高频调节滑块（亮度/色温等）。

        依据 _build_module_defs 期间的分类表（_module_kinds /
        _group_master_on）按 spec 顺序挑选，兼顾「灯=开关+亮度+色温」；
        无上述形态时回退旧逻辑（组合卡 → 标题含开关）。
        """
        picked: list[str] = []
        for key, _, _ in self._module_defs:
            kind = self._module_kinds.get(key, "other")
            is_master_group = (kind == "group" and key in self._group_master_on)
            if kind in ("on", "slider") or is_master_group:
                picked.append(key)
        if picked:
            return picked
        for key, _, _ in self._module_defs:
            if key.startswith("group:"):
                return [key]
        for key, title, _ in self._module_defs:
            if "开关" in title:
                return [key]
        return []

    @staticmethod
    def _cn_title(raw: str) -> str:
        """默认仅显示中文：'Brightness / 亮度' -> '亮度'"""
        if "/" in raw:
            return raw.split("/")[-1].strip()
        return raw.strip()

    @staticmethod
    def _is_on_name(name: str) -> bool:
        return name == "on" or name.startswith("on-") or name.startswith("on_")

    def _classify_prop(self, prop: PropInfo) -> str:
        """单属性模块分类（智能默认键用）：on / slider / other。"""
        if self._is_on_name(prop.name):
            return "on"
        if (prop.writable and prop.type in ("int", "uint", "float")
                and prop.range and is_primary_slider(prop)):
            return "slider"
        return "other"

    def _build_module_defs(self, detail: DeviceDetail) -> None:
        self._module_defs.clear()
        self._module_builders.clear()
        self._current_groups.clear()
        self._module_kinds.clear()
        self._group_master_on.clear()

        def _desc_for_prop(p: PropInfo) -> str:
            # 区分可读只读与不可读，避免把 rw="" 的空卡当可展示项误导添加
            if p.writable:
                rw_tag = "可写"
            elif p.readable:
                rw_tag = "只读"
            else:
                rw_tag = "不可读"
            parts = [rw_tag, p.type]
            if p.range:
                parts.append(f"范围 {p.range[0]}-{p.range[1]}")
            if p.value_list:
                parts.append(f"{len(p.value_list)} 选项")
            if not p.readable and not p.writable:
                parts.append("不支持操作/读取")
            return " · ".join(parts)

        # 保存分组信息供 _default_keys 使用
        groups = group_props(detail.props)
        self._current_groups = groups

        for gkey, members, master in groups:
            if master is not None:
                key = f"group:{gkey}"
                title = self._cn_title(master.desc or gkey)
                desc = f"组合 · {len(members)} 项"
                self._module_defs.append((key, title, desc))
                self._module_kinds[key] = "group"
                if self._is_on_name(master.name):
                    self._group_master_on.add(key)
                # 捕获
                def _mk_group(km=gkey, mem=members, ma=master):
                    # 仅展示中文
                    cn_master = PropInfo(
                        name=ma.name, desc=self._cn_title(ma.desc), type=ma.type,
                        readable=ma.readable, writable=ma.writable,
                        range=ma.range, value_list=ma.value_list)
                    cn_members = [
                        PropInfo(name=p.name, desc=self._cn_title(p.desc), type=p.type,
                                 readable=p.readable, writable=p.writable,
                                 range=p.range, value_list=p.value_list)
                        for p in mem if p is not ma
                    ] + [cn_master]
                    # 用中文标题的 master 覆盖
                    sec = GroupSection(km, cn_members, cn_master,
                        write=lambda prop, value: self._write(prop, prop.name, value))
                    sec.set_master_write(lambda state, m=cn_master: self._write(m, m.name, state))
                    self._sections[ma.name] = sec
                    for p in mem:
                        if p is not ma:
                            # 刷新链路用原始 prop 名，但 section 已注册 master 名即可
                            pass
                    return sec
                self._module_builders[key] = _mk_group
            else:
                for m in members:
                    key = m.name
                    cn = self._cn_title(m.desc)
                    # 重名卡片加后缀区分（如两个“静音”）
                    existing_titles = {t for _, t, _ in self._module_defs}
                    if cn in existing_titles:
                        cn = f"{cn} ({m.name})"
                    self._module_defs.append((key, cn, _desc_for_prop(m)))
                    self._module_kinds[key] = self._classify_prop(m)
                    def _mk_single(pm=m, cn2=cn):
                        cn_prop = PropInfo(
                            name=pm.name, desc=cn2, type=pm.type,
                            readable=pm.readable, writable=pm.writable,
                            range=pm.range, value_list=pm.value_list)
                        sec = build_prop_section(cn_prop,
                            write=lambda value, name=pm.name, p=pm: self._write(p, name, value))
                        self._sections[pm.name] = sec
                        return sec
                    self._module_builders[key] = _mk_single

        # 每个动作独立成卡，不再聚合为“更多操作”
        # 文本通道动作走既有 _in 语义；其余动作若 spec 给出参数定义则
        # 渲染参数化卡片（_action_args_map 渲染前已就绪）
        _TEXT_FAMILY = {"execute-text-directive", "play-text", "play-music",
                        "play-radio"}
        for act in detail.actions:
            key = f"action:{act.name}"
            title = self._cn_title(act.desc)
            existing = {t for _, t, _ in self._module_defs}
            if title in existing:
                title = f"{title} ({act.name})"
            desc = f"动作 · {act.name}"
            self._module_defs.append((key, title, desc))
            self._module_kinds[key] = "action"

            def _mk_single_action(a=act, _needs_text=(act.name in _TEXT_FAMILY)):
                if _needs_text:
                    return self._build_text_action_card(a)
                args = self._action_args_map.get(a.name)  # 渲染时取值（已就绪）
                if args:
                    return self._build_param_action_card(a, args)
                return self._build_plain_action_card(a)
            self._module_builders[key] = _mk_single_action

    # ---------- 动作卡片构建 ----------

    def _build_plain_action_card(self, a) -> QFrame:
        card = QFrame()
        card.setObjectName("propCard")
        card.setAttribute(Qt.WA_StyledBackground, True)
        card.prop = PropInfo(name=a.name, desc=a.desc, type="action",
                             readable=False, writable=False)
        card.refresh_value = lambda v: None  # type: ignore
        lay = QHBoxLayout(card)
        lay.setContentsMargins(20, 14, 20, 14)
        lay.setSpacing(12)
        lab = themed_label(self._cn_title(a.desc), SiColors.TEXT_PRIMARY)
        lab.setFont(QFont("Microsoft YaHei UI", 11, QFont.Weight.DemiBold))
        lay.addWidget(lab)
        lay.addStretch(1)
        btn = self._make_exec_button(a.name, None)
        lay.addWidget(btn)
        return card

    def _build_text_action_card(self, a) -> QFrame:
        card = QFrame()
        card.setObjectName("propCard")
        card.setAttribute(Qt.WA_StyledBackground, True)
        card.prop = PropInfo(name=a.name, desc=a.desc, type="action",
                             readable=False, writable=False)
        card.refresh_value = lambda v: None  # type: ignore
        lay = QVBoxLayout(card)
        lay.setContentsMargins(20, 12, 20, 12)
        lay.setSpacing(8)
        lab = themed_label(self._cn_title(a.desc), SiColors.TEXT_PRIMARY)
        lab.setFont(QFont("Microsoft YaHei UI", 11, QFont.Weight.DemiBold))
        lay.addWidget(lab)
        row = QHBoxLayout()
        row.setSpacing(8)
        from PySide6.QtWidgets import QLineEdit
        edit = QLineEdit()
        ph = ("输入要执行的指令…" if a.name == "execute-text-directive"
              else "输入文本…")
        edit.setPlaceholderText(ph)
        edit.setFixedHeight(32)
        edit.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        edit.setStyleSheet(
            f"QLineEdit {{ background: {SiColors.WINDOW_BG}; border: 1px solid {SiColors.LINE}; border-radius: 8px; "
            f"padding: 6px 10px; color: {SiColors.TEXT_PRIMARY}; selection-background-color: #3dbba4; font-size: 10pt; }}"
            "QLineEdit:focus { border-color: #3dbba4; }"
        )
        row.addWidget(edit, 1)

        def _do_exec():
            txt = edit.text().strip()
            if not txt:
                edit.setFocus()
                from app.ui.toast import Toast
                Toast.info(self, "请输入文本", 2000)
                return
            self._run_action(a.name, txt)
        btn = QPushButton("执行")
        btn.setFixedSize(64, 32)
        btn.setCursor(Qt.PointingHandCursor)
        btn.setStyleSheet(
            f"QPushButton {{ background: {SiColors.THEME}; color: {SiColors.ON_THEME_TEXT}; border: none;"
            f" border-radius: 8px; font-size: 9pt; font-weight: 600; }}"
            f"QPushButton:hover {{ background: {SiColors.THEME_HOVER}; }}")
        btn.clicked.connect(lambda: _do_exec())
        edit.returnPressed.connect(_do_exec)
        row.addWidget(btn)
        lay.addLayout(row)
        return card

    def _build_param_action_card(self, a, args) -> QFrame:
        """带参动作卡片：每个参数一行控件 + 「执行」按列表顺序收集提交。

        形参顺序即 spec 动作 in 的引用顺序；控件取值与动作参数类型对齐。
        """
        card = QFrame()
        card.setObjectName("propCard")
        card.setAttribute(Qt.WA_StyledBackground, True)
        card.prop = PropInfo(name=a.name, desc=a.desc, type="action",
                             readable=False, writable=False)
        card.refresh_value = lambda v: None  # type: ignore
        lay = QVBoxLayout(card)
        lay.setContentsMargins(20, 12, 20, 12)
        lay.setSpacing(6)

        head = QHBoxLayout()
        lab = themed_label(self._cn_title(a.desc), SiColors.TEXT_PRIMARY)
        lab.setFont(QFont("Microsoft YaHei UI", 11, QFont.Weight.DemiBold))
        head.addWidget(lab)
        head.addStretch(1)
        btn = QPushButton("执行")
        btn.setFixedSize(64, 30)
        btn.setCursor(Qt.PointingHandCursor)
        btn.setStyleSheet(
            f"QPushButton {{ background: {SiColors.THEME}; color: {SiColors.ON_THEME_TEXT}; border: none;"
            f" border-radius: 8px; font-size: 9pt; font-weight: 600; }}"
            f"QPushButton:hover {{ background: {SiColors.THEME_HOVER}; }}")
        head.addWidget(btn)
        lay.addLayout(head)

        controls: list = []
        children: list = []
        for arg in args:
            ctrl = self._build_arg_control(arg)
            controls.append(ctrl)
            row = QWidget()
            row.setStyleSheet("background: transparent;")
            rl = QHBoxLayout(row)
            rl.setContentsMargins(0, 0, 0, 0)
            rl.setSpacing(8)
            name_lab = themed_label(arg.desc or arg.name, SiColors.TEXT_SECONDARY)
            name_lab.setFont(QFont("Microsoft YaHei UI", 9))
            rl.addWidget(name_lab)
            rl.addStretch(1)
            rl.addWidget(ctrl)
            children.append(row)
            lay.addWidget(row)
        # 标记为组合形态：WorkbenchItemWrapper 据此自适应高度
        card._children = children

        def _collect():
            values = []
            for ctrl in controls:
                value = ctrl._collect_value()
                if value is None or value == "":
                    from app.ui.toast import Toast
                    Toast.info(self, "请填写完整参数", 2000)
                    return
                values.append(value)
            self._run_action(a.name, values)
        btn.clicked.connect(lambda: _collect())
        return card

    def _build_arg_control(self, arg):
        """按参数类型构造取值控件；控件携带 _collect_value() 供执行时取值。"""
        from PySide6.QtWidgets import QComboBox, QDoubleSpinBox, QLineEdit, QSpinBox

        low_high = arg.range or (None, None)

        def _num_range(default_hi: int):
            low = int(low_high[0]) if low_high[0] is not None else -2147483648
            hi = int(low_high[1]) if low_high[1] is not None else default_hi
            return low, hi

        if arg.type == "bool":
            combo = QComboBox()
            combo.addItems(["开启", "关闭"])
            combo._collect_value = lambda c=combo: c.currentIndex() == 0  # type: ignore
            apply_combo_qss(combo)
            combo.setFixedHeight(30)
            combo.setFixedWidth(110)
            combo.setCursor(Qt.PointingHandCursor)
            return combo
        if arg.type in ("int", "uint"):
            low, hi = _num_range(2_000_000_000 if arg.type == "uint" else 2_000_000_000)
            spin = QSpinBox()
            spin.setRange(low, hi)
            spin.setValue(low if low_high[0] is not None else 0)
            spin._collect_value = spin.value  # type: ignore
            self._style_spin(spin)
            return spin
        if arg.type == "float":
            spin = QDoubleSpinBox()
            low = float(low_high[0]) if low_high[0] is not None else -1e9
            hi = float(low_high[1]) if low_high[1] is not None else 1e9
            spin.setDecimals(2)
            spin.setRange(low, hi)
            spin._collect_value = spin.value  # type: ignore
            self._style_spin(spin)
            return spin
        if arg.value_list:
            combo = QComboBox()
            combo._opt_values = [item["value"] for item in arg.value_list]  # type: ignore
            combo.addItems([
                enum_option_text(item) for item in arg.value_list])
            combo._collect_value = (  # type: ignore
                lambda c=combo: c._opt_values[c.currentIndex()])
            apply_combo_qss(combo)
            combo.setFixedHeight(30)
            combo.setCursor(Qt.PointingHandCursor)
            return combo
        # string 等一律文本框
        edit = QLineEdit()
        edit.setFixedHeight(30)
        edit.setStyleSheet(
            f"QLineEdit {{ background: {SiColors.WINDOW_BG}; border: 1px solid {SiColors.LINE};"
            f" border-radius: 7px; padding: 4px 8px; color: {SiColors.TEXT_PRIMARY}; }}"
            "QLineEdit:focus { border-color: #3dbba4; }")
        edit._collect_value = edit.text  # type: ignore
        return edit

    @staticmethod
    def _style_spin(spin) -> None:
        spin.setFixedHeight(30)
        spin.setCursor(Qt.PointingHandCursor)
        spin.setStyleSheet(
            f"QSpinBox, QDoubleSpinBox {{ background: {SiColors.SURFACE};"
            f" border: 1px solid {SiColors.LINE}; border-radius: 7px;"
            f" padding: 2px 6px; color: {SiColors.TEXT_PRIMARY}; }}"
            "QSpinBox:focus, QDoubleSpinBox:focus { border-color: #3dbba4; }")

    def _make_exec_button(self, action_name: str, value) -> QPushButton:
        btn = QPushButton("执行")
        btn.setFixedSize(64, 32)
        btn.setCursor(Qt.PointingHandCursor)
        btn.setStyleSheet(
            f"QPushButton {{ background: {SiColors.THEME}; color: {SiColors.ON_THEME_TEXT};"
            f" border: none; border-radius: 8px; font-size: 9pt; font-weight: 600; }}"
            f"QPushButton:hover {{ background: {SiColors.THEME_HOVER}; }}")
        btn.clicked.connect(
            lambda _, n=action_name, v=value: self._run_action(n, v))
        return btn

    def _render_workbench(self) -> None:
        self._clear_grid()
        if not self._active_keys:
            # 属性与动作皆空的设备（如部分 BLE 类产品）没有可控制的
            # 功能，给出明确提示并隐藏“添加功能”入口
            no_funcs = bool(self._detail) and not self._detail.props and not self._detail.actions
            self._empty_title.setText(
                "该设备无公开的可控制功能"
                if no_funcs else "此设备控制面板还是空的")
            self._empty_desc.setText(
                "该设备未发布功能规格（常见于蓝牙类产品），无法提供控制面板"
                if no_funcs else "点击下方按钮添加控制功能")
            self._empty_add_btn.setVisible(not no_funcs)
            self._empty.show()
            self._body.hide()
            self._footer_add_btn.hide()
            return
        self._empty.hide()
        self._body.show()
        self._footer_add_btn.setVisible(self._mode == "manage")
        self._left_h = 0
        self._right_h = 0
        for key in list(self._active_keys):
            builder = self._module_builders.get(key)
            if builder is None:
                continue
            inner = builder()
            wrapper = WorkbenchItemWrapper(key, inner)
            wrapper.request_delete.connect(self._on_delete)
            wrapper.request_move.connect(self._on_move)
            wrapper.set_mode(self._mode)
            if not self._current_online:
                wrapper.set_offline(True)
                inner.setEnabled(False)
            self._wrappers[key] = wrapper
            # 瀑布流分栏高度估算（与重排动画共用同一公式）
            h = wrapper.estimated_height()
            if self._left_h <= self._right_h:
                self._left_col.addWidget(wrapper)
                self._left_h += h + 14
            else:
                self._right_col.addWidget(wrapper)
                self._right_h += h + 14
        self._left_col.addStretch(1)
        self._right_col.addStretch(1)
        # 批量回读
        self._reload_readings()

    def _clear_workbench(self) -> None:
        self._clear_grid()
        self._empty.hide()
        self._footer_add_btn.hide()
        self._body.hide()
        self._refresh_btn.hide()

    def _clear_grid(self) -> None:
        # 重排动画进行中切换设备时，先停掉动画：动画目标 wrapper 随即
        # 被 deleteLater，带着已删除对象跑几何动画会崩。
        # 注意 stop() 中途停止不发 finished（自然结束才发），状态须手动复位
        group = self._reorder_group
        if group is not None:
            self._reorder_group = None
            try:
                group.stop()
            except Exception:
                pass
            self._reordering = False
            self._container.layout().setEnabled(True)
            group.deleteLater()
        self._sections.clear()
        self._wrappers.clear()
        for lay in (self._left_col, self._right_col):
            while lay.count():
                item = lay.takeAt(0)
                if w := item.widget():
                    w.deleteLater()
                elif item.layout():
                    # 跳过 stretch
                    pass

    def _update_offline_bar(self) -> None:
        self._offline_bar.setVisible(not self._current_online)

    # ---------- 抽屉 ----------

    def _open_drawer(self) -> None:
        if self._detail is None:
            return
        if self._drawer is not None and shiboken6.isValid(self._drawer):
            self._drawer.reject()
            self._drawer.deleteLater()
        self._drawer = AddDrawer(self.window())
        self._drawer.set_modules(self._module_defs, set(self._active_keys))
        self._drawer.add_module.connect(self._on_toggle_from_drawer)
        self._drawer.exec()
        self._drawer.deleteLater()
        self._drawer = None

    def _on_toggle_from_drawer(self, key: str) -> None:
        if self._current_did is None:
            return
        if key in self._active_keys:
            self._on_delete(key)
            if self._drawer is not None:
                # 移除后卡片恢复为未添加样式
                if card := self._drawer._cards.get(key):
                    card.set_added(False)
        else:
            self._on_add(key)

    def _on_add(self, key: str) -> None:
        if key in self._active_keys or self._current_did is None:
            return
        self._active_keys.append(key)
        workbench_store.save(self._current_did, self._active_keys)
        if self._drawer is not None:
            self._drawer.mark_added(key)
        self._render_workbench()

    def _on_delete(self, key: str) -> None:
        if key not in self._active_keys or self._current_did is None:
            return
        self._active_keys.remove(key)
        workbench_store.save(self._current_did, self._active_keys)
        self._render_workbench()

    def _on_move(self, key: str, direction: int) -> None:
        if key not in self._active_keys or self._current_did is None:
            return
        idx = self._active_keys.index(key)
        new_idx = idx + direction
        if not 0 <= new_idx < len(self._active_keys):
            return
        old_geoms = {k: w.geometry() for k, w in self._wrappers.items()}
        self._active_keys[idx], self._active_keys[new_idx] = self._active_keys[new_idx], self._active_keys[idx]
        workbench_store.save(self._current_did, self._active_keys)
        self._reorder_with_animation(old_geoms)

    # ---------- 管理模式 ----------

    def _apply_header_button_styles(self) -> None:
        styles = (
            f"QPushButton {{ background: {SiColors.SURFACE}; border: none; border-radius: 8px;"
            f" color: {SiColors.TEXT_PRIMARY}; font-size: 9pt; }}"
            f"QPushButton:hover {{ background: {SiColors.BTN_HOVER}; }}"
            f"QPushButton[active=\"true\"] {{ background: {SiColors.THEME};"
            f" color: {SiColors.ON_THEME_TEXT}; }}")
        self._refresh_btn.setStyleSheet(styles)
        self._edit_btn.setStyleSheet(styles)
        self._rename_btn.setStyleSheet(styles)
        self._reset_name_btn.setStyleSheet(styles)

    def retheme(self) -> None:
        """主题切换：刷新头部按钮与已加载的功能区块（内联样式冻结）。"""
        self._apply_header_button_styles()
        for btn in (self._refresh_btn, self._edit_btn,
                    self._rename_btn, self._reset_name_btn):
            btn.style().unpolish(btn)
            btn.style().polish(btn)
        if self._detail is not None:
            self._render_workbench()

    def _toggle_manage(self) -> None:
        self._set_mode("normal" if self._mode == "manage" else "manage")

    def _set_mode(self, mode: str) -> None:
        self._mode = mode
        is_manage = mode == "manage"
        self._edit_btn.setText("完成" if is_manage else "编辑功能")
        self._edit_btn.setProperty("active", is_manage)
        self._edit_btn.style().unpolish(self._edit_btn)
        self._edit_btn.style().polish(self._edit_btn)
        for w in self._wrappers.values():
            w.set_mode(mode)
        self._footer_add_btn.setVisible(is_manage and bool(self._active_keys))

    def _reorder_with_animation(self, old_geoms: dict) -> None:
        # 复用已有 wrapper，仅重排布局并做滑动动画
        if self._reordering:
            return
        self._reordering = True
        # 1. 移除但不删除
        for lay in (self._left_col, self._right_col):
            while lay.count():
                it = lay.takeAt(0)
                w = it.widget()
                if w is not None:
                    w.hide()
        # 2. 按新顺序以瀑布流重新加入（高度公式与 _render_workbench 一致）
        left_h = right_h = 0
        for key in list(self._active_keys):
            w = self._wrappers.get(key)
            if w is None:
                continue
            h = w.estimated_height()
            if left_h <= right_h:
                self._left_col.addWidget(w)
                left_h += h + 14
            else:
                self._right_col.addWidget(w)
                right_h += h + 14
            w.show()
        self._left_col.addStretch(1)
        self._right_col.addStretch(1)
        # 3. 强制布局计算新几何
        self._container.layout().activate()
        from PySide6.QtWidgets import QApplication as _QApp
        _QApp.processEvents()
        new_geoms = {k: w.geometry() for k, w in self._wrappers.items()}
        # 4. 禁用布局，准备动画
        self._container.layout().setEnabled(False)
        group = QParallelAnimationGroup(self)

        def _release() -> None:
            self._container.layout().setEnabled(True)
            self._container.update()
            self._reordering = False
            if self._reorder_group is group:
                self._reorder_group = None
            group.deleteLater()

        for key, w in self._wrappers.items():
            og = old_geoms.get(key)
            ng = new_geoms.get(key)
            if og is None or ng is None or og == ng:
                continue
            w.setGeometry(og)
            anim = QPropertyAnimation(w, b"geometry")
            anim.setDuration(260)
            anim.setStartValue(og)
            anim.setEndValue(ng)
            anim.setEasingCurve(QEasingCurve.OutCubic)
            group.addAnimation(anim)
        group.finished.connect(_release)
        self._reorder_group = group
        if group.animationCount() > 0:
            group.start()
        else:
            _release()

    # ---------- 拖拽排序 ----------

    def dragEnterEvent(self, event) -> None:  # noqa: N802
        if self._mode != "manage":
            event.ignore()
            return
        if event.mimeData().hasText() and event.mimeData().text() in self._active_keys:
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event) -> None:  # noqa: N802
        if self._mode == "manage" and event.mimeData().hasText():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event) -> None:  # noqa: N802
        if self._mode != "manage":
            event.ignore()
            return
        from_key = event.mimeData().text()
        if from_key not in self._active_keys:
            event.ignore()
            return
        # 找到落点下的目标卡片
        pos = self._container.mapFrom(self, event.position().toPoint())
        target = None
        for key, wrapper in self._wrappers.items():
            if wrapper.geometry().contains(pos):
                target = key
                break
        # 记录旧几何用于滑动动画
        old_geoms = {k: w.geometry() for k, w in self._wrappers.items()}
        if target is None or target == from_key:
            # 拖到空白处 -> 移到末尾
            if from_key in self._active_keys:
                self._active_keys.remove(from_key)
                self._active_keys.append(from_key)
                workbench_store.save(self._current_did, self._active_keys)
                self._reorder_with_animation(old_geoms)
            event.acceptProposedAction()
            return
        # 插入到目标之前
        self._active_keys.remove(from_key)
        idx = self._active_keys.index(target)
        self._active_keys.insert(idx, from_key)
        workbench_store.save(self._current_did, self._active_keys)
        self._reorder_with_animation(old_geoms)
        event.acceptProposedAction()

    # ---------- 读写（复用 DevicePanel 逻辑） ----------

    def _write(self, prop, name: str, value: Any) -> None:
        did = self._current_did
        if did is None:
            return
        import time
        now = time.time()
        # 进入静默期：3 秒内忽略旧值回填，乐观保留用户刚写入的值
        self._cooldown[name] = now + 3.0
        self._last_written[name] = value
        self._last_written_time[name] = now
        self._jobs.submit(
            lambda: self._service.write_prop(did, name, value),
            on_success=lambda _: self._after_value_written(did, name, value, prop),
            on_error=self._show_error,
        )

    def _after_value_written(self, did: str, name: str, value: Any, prop) -> None:
        """写值成功：3 秒后回读校准 + 通知宿主广播新值到其它入口。"""
        QTimer.singleShot(3000, lambda: self._read_single(prop, name))
        cb = getattr(self, "_value_written_cb", None)
        if cb is not None:
            try:
                cb(did, name, value)
            except Exception:
                pass

    def _read_single(self, prop, name: str) -> None:
        if not prop.readable:
            return
        did = self._current_did
        sec = self._sections.get(name)
        if did is None or sec is None:
            return
        self._jobs.submit(
            lambda: self._service.read_prop(did, name),
            on_success=lambda v: self._apply_reading(sec, v),
            on_error=lambda _: None,
        )

    def _reload_readings(self, force: bool = False) -> None:
        did = self._current_did
        if did is None:
            return
        names = []
        seen = set()
        for name, sec in self._sections.items():
            if name in seen or not sec.prop.readable:
                continue
            seen.add(name)
            names.append(name)
        if not names:
            return
        if force:
            # 手动刷新仅清除静默，不清除乐观值，避免云端旧值把刚写的弹回
            for n in names:
                self._cooldown.pop(n, None)
        self._jobs.submit(
            lambda: self._service.read_props(did, names),
            on_success=lambda v: self._apply_readings(v, force=force),
            on_error=lambda _: None,
        )

    def _apply_readings(self, values: dict[str, Any], force: bool = False) -> None:
        for name, value in values.items():
            sec = self._sections.get(name)
            if sec is not None:
                self._apply_reading(sec, value, force=force)
        self._emit_metrics(values)

    def _emit_metrics(self, values: dict[str, Any]) -> None:
        temp = values.get("temperature")
        hum = values.get("relative-humidity")
        if hum is None:
            hum = values.get("humidity")
        if temp is None and hum is None:
            return
        # 格式化与卡片副标题共用同一实现（service 层），避免两处启发式漂移
        text = format_metrics_text(temp, hum)
        if text and self._current_did:
            self.metrics_updated.emit(self._current_did, text)

    def _apply_reading(self, section: QWidget, value: Any, force: bool = False) -> None:
        if not shiboken6.isValid(self) or not shiboken6.isValid(section):
            return
        import time
        name = section.prop.name
        now = time.time()
        if not force:
            cd = self._cooldown.get(name, 0)
            if cd and now < cd:
                return
            lw = self._last_written.get(name, None)
            lwt = self._last_written_time.get(name, 0)
            if lw is not None and now < lwt + 10 and value != lw:
                return
        if section.prop.name in self._sections:
            section.refresh_value(value)

    def _run_action(self, name: str, value=None) -> None:
        did = self._current_did
        if did is None:
            return
        # 文本类动作已在卡片上提供输入框，不再弹二次对话框
        needs_text = name in ("execute-text-directive", "play-text", "play-music", "play-radio")
        if needs_text and (value is None or (isinstance(value, str) and not value.strip())):
            from app.ui.toast import Toast
            Toast.info(self, "请输入文本", 2000)
            return
        run_value = value
        if isinstance(value, str) and name in ("execute-text-directive", "play-text"):
            run_value = [value]
        self._jobs.submit(
            lambda: self._service.run_action(did, name, run_value) if run_value is not None else self._service.run_action(did, name),
            on_success=lambda _: None,
            on_error=lambda e: self._handle_action_error(e, name),
        )

    def _handle_action_error(self, error: Exception, name: str) -> None:
        msg = str(error)
        if "-704220025" in msg or "参数个数不匹配" in msg:
            from app.ui.toast import Toast
            Toast.info(self, f"{name} 参数错误，请检查输入", 2500)
            return
        self._show_error(error)

    def _show_error(self, error: Exception) -> None:
        if not shiboken6.isValid(self):
            return
        self._loading.hide()
        self._title_label.show()
        self._model_label.show()
        self._load_hint.setText(f"加载失败：{error}")
        self._load_hint.setStyleSheet(
            f"color: {SiColors.ERROR_TEXT}; font-size: 9pt; background: transparent;")
        self._loading.show()


