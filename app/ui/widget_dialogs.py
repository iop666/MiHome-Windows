# SPDX-License-Identifier: GPL-3.0-or-later
# MiHome-Windows: 米家设备的 Windows 桌面控制端
# Copyright (C) 2026 MiHome-Windows contributors
"""新建桌面小组件时选择设备的对话框（支持多选）。"""

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from app.core.models import DeviceInfo
from app.ui.si_theme import SiColors


class DevicePickDialog(QDialog):
    """多选设备 → 作为一个小组件内容。"""

    def __init__(self, devices: list[DeviceInfo], parent=None):
        super().__init__(parent)
        self.setWindowTitle("添加桌面小组件")
        self.setModal(True)
        self.setMinimumSize(340, 420)
        self.setStyleSheet(f"QDialog {{ background: {SiColors.WINDOW_BG}; }}")
        self._boxes: list[tuple[str, QCheckBox]] = []

        lay = QVBoxLayout(self)
        lay.setContentsMargins(18, 16, 18, 14)
        lay.setSpacing(10)
        title = QLabel("选择要固定到小组件的设备（可多选）")
        title.setFont(QFont("Microsoft YaHei UI", 12, QFont.Weight.DemiBold))
        title.setStyleSheet(f"color: {SiColors.TEXT_PRIMARY}; background: transparent;")
        lay.addWidget(title)
        hint = QLabel("一个小组件可含多台设备；选 1 台最常用（如台灯2）即可快速开关与调节。")
        hint.setWordWrap(True)
        hint.setStyleSheet(
            f"color: {SiColors.TEXT_SECONDARY}; background: transparent; font-size: 8pt;")
        lay.addWidget(hint)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")
        host = QWidget()
        host.setStyleSheet("background: transparent;")
        box_lay = QVBoxLayout(host)
        box_lay.setContentsMargins(2, 4, 4, 0)
        box_lay.setSpacing(6)
        ordered = sorted(devices, key=lambda d: (0 if d.online else 1, d.name))
        for dev in ordered:
            box = QCheckBox(f"{dev.name}  ·  {dev.room_name}"
                            + ("" if dev.online else "（离线）"))
            box.setChecked(dev.online and len(devices) <= 6 and dev.online)
            box.setCursor(Qt.PointingHandCursor)
            box.setStyleSheet(
                f"QCheckBox {{ color: {SiColors.TEXT_PRIMARY}; background: transparent;"
                f" font-size: 9pt; padding: 6px 8px; }}"
                f"QCheckBox::indicator {{ width: 15px; height: 15px; }}")
            box_lay.addWidget(box)
            self._boxes.append((dev.did, box))
        box_lay.addStretch(1)
        scroll.setWidget(host)
        lay.addWidget(scroll, stretch=1)

        row = QHBoxLayout()
        row.addStretch(1)
        cancel = QPushButton("取消")
        cancel.setCursor(Qt.PointingHandCursor)
        cancel.clicked.connect(self.reject)
        cancel.setStyleSheet(
            f"QPushButton {{ background: {SiColors.SURFACE}; border: none;"
            f" border-radius: 8px; padding: 6px 16px; color: {SiColors.TEXT_PRIMARY}; }}")
        row.addWidget(cancel)
        ok = QPushButton("创建")
        ok.setCursor(Qt.PointingHandCursor)
        ok.clicked.connect(self.accept)
        ok.setStyleSheet(
            f"QPushButton {{ background: {SiColors.THEME}; color: {SiColors.ON_THEME_TEXT};"
            f" border: none; border-radius: 8px; padding: 6px 18px; font-weight: 600; }}")
        row.addWidget(ok)
        lay.addLayout(row)

    def selected_dids(self) -> list[str]:
        return [did for did, box in self._boxes if box.isChecked()]
