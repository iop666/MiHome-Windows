# SPDX-License-Identifier: GPL-3.0-or-later
# MiHome-Windows: 米家设备的 Windows 桌面控制端
# Copyright (C) 2026 MiHome-Windows contributors
"""托盘设备「调节项」勾选对话框。

列出设备全部可紧凑调节的候选项（spec 推导），按需勾选后在托盘快捷
窗口的行内展开中展示；不勾选直接保存 = 不提供调节；「恢复默认」删除
自选记录 = 回到自动常用项（与卡片快捷面板一致）。
"""

import shiboken6

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from app.core import tray_ops_store
from app.core.jobs import JobExecutor
from app.core.models import DeviceInfo
from app.core.service import MijiaService
from app.ui.si_theme import SiColors
from app.ui.toast import Toast


def _short_desc(desc: str) -> str:
    if "/" in desc:
        return desc.split("/")[-1].strip()
    return desc.strip()


class TrayOpsDialog(QDialog):
    """选择该设备在托盘行内展开时提供哪些调节项。"""

    def __init__(self, service: MijiaService, jobs: JobExecutor,
                 device: DeviceInfo, parent=None):
        super().__init__(parent)
        self._service = service
        self._jobs = jobs
        self._device = device
        self.setWindowTitle(f"调节项 · {device.name}")
        self.setModal(True)
        self.setMinimumSize(360, 460)
        self.setStyleSheet(
            f"QDialog {{ background: {SiColors.WINDOW_BG}; }}")

        lay = QVBoxLayout(self)
        lay.setContentsMargins(18, 16, 18, 14)
        lay.setSpacing(10)

        title = QLabel(f"选择「{_short_desc(device.name)}」的托盘调节项")
        title.setFont(QFont("Microsoft YaHei UI", 12, QFont.Weight.DemiBold))
        title.setStyleSheet(f"color: {SiColors.TEXT_PRIMARY}; background: transparent;")
        lay.addWidget(title)
        sub = QLabel(
            "勾选后会在托盘快捷窗口该设备行内展开；全不勾选 = 不提供调节，"
            "「恢复默认」回到自动常用项（亮度/色温等）。")
        sub.setWordWrap(True)
        sub.setStyleSheet(
            f"color: {SiColors.TEXT_SECONDARY}; background: transparent; font-size: 8pt;")
        lay.addWidget(sub)

        self._hint = QLabel("正在读取可调项…")
        self._hint.setStyleSheet(
            f"color: {SiColors.TEXT_SECONDARY}; background: transparent; font-size: 9pt;")
        lay.addWidget(self._hint)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QScrollArea.NoFrame)
        self._scroll.setStyleSheet(
            "QScrollArea { background: transparent; border: none; }"
            f"QScrollBar:vertical {{ background: transparent; width: 6px; margin: 0; }}"
            f"QScrollBar::handle:vertical {{ background: {SiColors.SCROLLBAR};"
            f" border-radius: 3px; min-height: 30px; }}")
        host = QWidget()
        host.setStyleSheet("background: transparent;")
        self._box_lay = QVBoxLayout(host)
        self._box_lay.setContentsMargins(2, 4, 4, 0)
        self._box_lay.setSpacing(6)
        self._scroll.setWidget(host)
        lay.addWidget(self._scroll, stretch=1)

        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        reset = QPushButton("恢复默认")
        reset.setCursor(Qt.PointingHandCursor)
        reset.setStyleSheet(
            f"QPushButton {{ background: {SiColors.SURFACE}; border: none;"
            f" border-radius: 8px; padding: 6px 14px; color: {SiColors.TEXT_PRIMARY}; }}"
            f"QPushButton:hover {{ background: {SiColors.BTN_HOVER}; }}")
        reset.clicked.connect(self._reset_default)
        btn_row.addWidget(reset)
        cancel = QPushButton("取消")
        cancel.setCursor(Qt.PointingHandCursor)
        cancel.setStyleSheet(
            f"QPushButton {{ background: {SiColors.SURFACE}; border: none;"
            f" border-radius: 8px; padding: 6px 16px; color: {SiColors.TEXT_PRIMARY}; }}"
            f"QPushButton:hover {{ background: {SiColors.BTN_HOVER}; }}")
        cancel.clicked.connect(self.reject)
        btn_row.addWidget(cancel)
        save = QPushButton("保存")
        save.setCursor(Qt.PointingHandCursor)
        save.setStyleSheet(
            f"QPushButton {{ background: {SiColors.THEME}; color: {SiColors.ON_THEME_TEXT};"
            f" border: none; border-radius: 8px; padding: 6px 18px; font-weight: 600; }}"
            f"QPushButton:hover {{ background: {SiColors.THEME_HOVER}; }}")
        save.clicked.connect(self._save)
        btn_row.addWidget(save)
        lay.addLayout(btn_row)

        self._boxes: dict[str, QCheckBox] = {}
        self._stored = tray_ops_store.selected(device.did)
        self._jobs.submit(
            lambda: self._service.quick_op_candidates(device.did),
            on_success=self._render,
            on_error=self._load_failed,
        )

    # ---------- 数据 ----------

    def _default_names(self, defs) -> set[str]:
        sliders = [d for d in defs if d.kind == "slider"]
        enums = [d for d in defs if d.kind == "enum"]
        return {d.name for d in (sliders[:2] + enums[:2])[:4]}

    def _render(self, defs) -> None:
        if not shiboken6.isValid(self):
            return
        if not defs:
            self._hint.setText("该设备没有可选的调节项")
            return
        self._hint.hide()
        if self._stored is None:
            checked = self._default_names(defs)
        else:
            checked = set(self._stored)
        for op in defs:
            box = QCheckBox(_short_desc(op.desc))
            box.setToolTip(op.name)
            box.setChecked(op.name in checked)
            box.setCursor(Qt.PointingHandCursor)
            box.setStyleSheet(
                f"QCheckBox {{ color: {SiColors.TEXT_PRIMARY}; background: transparent;"
                f" font-size: 9pt; padding: 6px 8px; }}"
                f"QCheckBox::indicator {{ width: 15px; height: 15px; }}")
            self._box_lay.addWidget(box)
            self._boxes[op.name] = box
        self._box_lay.addStretch(1)

    def _load_failed(self, error: Exception) -> None:
        if not shiboken6.isValid(self):
            return
        self._hint.setText(f"读取失败：{error}")
        self._hint.setStyleSheet(
            f"color: {SiColors.ERROR_TEXT}; background: transparent; font-size: 9pt;")

    # ---------- 动作 ----------

    def _save(self) -> None:
        picked = [name for name, box in self._boxes.items() if box.isChecked()]
        tray_ops_store.save(self._device.did, picked)
        Toast.info(self, f"已更新「{self._device.name}」的托盘调节项", 2500)
        self.accept()

    def _reset_default(self) -> None:
        tray_ops_store.clear(self._device.did)
        Toast.info(self, "已恢复默认调节项", 2000)
        self.accept()
