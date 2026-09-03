# SPDX-License-Identifier: GPL-3.0-or-later
# MiHome-Windows: 米家设备的 Windows 桌面控制端
# Copyright (C) 2026 MiHome-Windows contributors
"""新建桌面小组件时选择设备的对话框（支持多选）。"""

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
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
        self.setWindowTitle("添加小组件")
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

class WidgetOpsDialog(QDialog):
    """选择小组件里某台设备展示哪些调节控件（未保存 = 自动常用）。"""

    def __init__(self, service, jobs, cfg: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("选择小组件控件")
        self.setModal(True)
        self.setMinimumSize(340, 400)
        self.setStyleSheet(f"QDialog {{ background: {SiColors.WINDOW_BG}; }}")
        self._service = service
        self._jobs = jobs
        self._cfg = dict(cfg)
        dids = [str(d) for d in cfg.get("dids", [])]
        meta = cfg.get("devices") or {}
        self._did_labels = [
            (d, (meta.get(d) or {}).get("name") or d) for d in dids]
        self._ops_map = dict(cfg.get("device_ops") or {})
        self._boxes: dict[str, QCheckBox] = {}

        lay = QVBoxLayout(self)
        lay.setContentsMargins(18, 16, 18, 14)
        lay.setSpacing(8)
        title = QLabel("选择展示的调节控件")
        title.setFont(QFont("Microsoft YaHei UI", 12, QFont.Weight.DemiBold))
        title.setStyleSheet(f"color: {SiColors.TEXT_PRIMARY}; background: transparent;")
        lay.addWidget(title)
        hint = QLabel("勾选这台设备要展示的控件；不勾选任何项 = 只保留开关行；"
                      "「恢复默认」= 自动常用项。多台设备请用下方下拉切换。")
        hint.setWordWrap(True)
        hint.setStyleSheet(
            f"color: {SiColors.TEXT_SECONDARY}; background: transparent; font-size: 8pt;")
        lay.addWidget(hint)

        top = QHBoxLayout()
        self._device_combo = QComboBox()
        for did, label in self._did_labels:
            self._device_combo.addItem(label, did)
        self._device_combo.setFixedHeight(30)
        self._device_combo.currentIndexChanged.connect(self._load_device)
        top.addWidget(self._device_combo, 1)
        self._default_btn = QPushButton("恢复默认")
        self._default_btn.setCursor(Qt.PointingHandCursor)
        self._default_btn.setFixedHeight(28)
        self._default_btn.clicked.connect(self._reset_default)
        top.addWidget(self._default_btn)
        lay.addLayout(top)

        self._note = QLabel()
        self._note.setWordWrap(True)
        self._note.setStyleSheet(
            f"color: {SiColors.TEXT_MUTED}; background: transparent; font-size: 8pt;")
        lay.addWidget(self._note)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")
        host = QWidget()
        host.setStyleSheet("background: transparent;")
        self._box_lay = QVBoxLayout(host)
        self._box_lay.setContentsMargins(2, 2, 4, 0)
        self._box_lay.setSpacing(4)
        scroll.setWidget(host)
        lay.addWidget(scroll, stretch=1)

        btns = QHBoxLayout()
        btns.addStretch(1)
        cancel = QPushButton("取消")
        cancel.setCursor(Qt.PointingHandCursor)
        cancel.clicked.connect(self.reject)
        cancel.setStyleSheet(
            f"QPushButton {{ background: {SiColors.SURFACE}; border: none;"
            f" border-radius: 8px; padding: 6px 16px; color: {SiColors.TEXT_PRIMARY}; }}")
        btns.addWidget(cancel)
        ok = QPushButton("保存")
        ok.setCursor(Qt.PointingHandCursor)
        ok.clicked.connect(self.accept)
        ok.setStyleSheet(
            f"QPushButton {{ background: {SiColors.THEME}; color: {SiColors.ON_THEME_TEXT};"
            f" border: none; border-radius: 8px; padding: 6px 18px; font-weight: 600; }}")
        btns.addWidget(ok)
        lay.addLayout(btns)
        self._load_device(0)

    # ---------- 加载某台设备候选 ----------

    def _clear_boxes(self):
        while self._box_lay.count():
            item = self._box_lay.takeAt(0)
            if w := item.widget():
                w.deleteLater()
        self._boxes.clear()

    def _load_device(self, index: int) -> None:
        did = self._device_combo.itemData(index)
        if not did:
            return
        self._clear_boxes()
        selected = self._ops_map.get(did)  # None=自动
        if selected is None:
            self._note.setText("当前设备：自动常用（亮度/色温等）；可按需改勾选。")
        else:
            self._note.setText("当前设备：已自选；不勾选任何项将只保留开关行。")
        checked = set(selected or [])

        def _on_defs(defs):
            for op in defs:
                box = QCheckBox(str(op.desc).split("/")[-1].strip())
                box.setToolTip(op.name)
                box.setChecked(op.name in checked)
                box.setCursor(Qt.PointingHandCursor)
                box.setStyleSheet(
                    f"QCheckBox {{ color: {SiColors.TEXT_PRIMARY}; background: transparent;"
                    f" font-size: 9pt; padding: 5px 8px; }}"
                    f"QCheckBox::indicator {{ width: 15px; height: 15px; }}")
                self._box_lay.addWidget(box)
                self._boxes[op.name] = box
            self._box_lay.addStretch(1)

        self._jobs.submit(
            lambda d=did: self._service.quick_op_candidates(d),
            on_success=_on_defs,
            on_error=lambda e: self._note.setText(f"读取失败：{e}"))

    def _reset_default(self) -> None:
        did = self._device_combo.currentData()
        if not did:
            return
        self._ops_map.pop(did, None)
        self._load_device(self._device_combo.currentIndex())

    # ---------- 结果 ----------

    def result_map(self) -> dict:
        did = self._device_combo.currentData()
        if did:
            self._ops_map[did] = [name for name, b in self._boxes.items()
                                  if b.isChecked()]
        return dict(self._ops_map)
