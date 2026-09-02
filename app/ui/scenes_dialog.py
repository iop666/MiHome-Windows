# SPDX-License-Identifier: GPL-3.0-or-later
# MiHome-Windows: 米家设备的 Windows 桌面控制端
# Copyright (C) 2026 MiHome-Windows contributors
"""米家手动场景：查看各家庭场景并一键执行。

数据来自 mijiaAPI 的 get_scenes_list/run_scene（手动场景，需在米家 App
「智能 → + → 手动控制」里创建）。安全模式（MIWU_SAFE_DEVICE）下场景
整体禁用：列表显示说明、执行请求在 service 层同样硬拒绝。
"""

import shiboken6

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from app.core.jobs import JobExecutor
from app.core.models import SceneInfo
from app.core.safety import get_guard
from app.core.service import MijiaService
from app.ui.overlay_dialog import OverlayDialog
from app.ui.si_theme import SiColors
from app.ui.toast import Toast


class ScenesDialog(OverlayDialog):
    """遮罩居中面板：场景按家庭分组展示，逐条「执行」。"""

    def __init__(self, service: MijiaService, jobs: JobExecutor, parent=None):
        super().__init__(parent)
        self._service = service
        self._jobs = jobs
        self._guard = get_guard()
        self.setWindowTitle("米家场景")

        panel = self._panel
        panel.setFixedSize(460, 520)

        lay = QVBoxLayout(panel)
        lay.setContentsMargins(20, 16, 20, 16)
        lay.setSpacing(10)

        head = QHBoxLayout()
        title = QLabel("米家场景")
        title.setFont(QFont("Microsoft YaHei UI", 13, QFont.Weight.DemiBold))
        title.setStyleSheet(f"color: {SiColors.TEXT_PRIMARY}; background: transparent;")
        head.addWidget(title)
        head.addStretch(1)
        head.addWidget(self._make_close_button())
        lay.addLayout(head)

        self._sub = QLabel()
        self._sub.setStyleSheet(
            f"color: {SiColors.TEXT_SECONDARY}; background: transparent; font-size: 9pt;")
        lay.addWidget(self._sub)

        self._hint = QLabel()
        self._hint.setWordWrap(True)
        self._hint.setStyleSheet(
            f"color: {SiColors.TEXT_SECONDARY}; background: transparent; font-size: 9pt;")
        self._hint.hide()
        lay.addWidget(self._hint)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QScrollArea.NoFrame)
        self._scroll.setStyleSheet(
            "QScrollArea { background: transparent; border: none; }"
            f"QScrollBar:vertical {{ background: transparent; width: 6px; margin: 0; }}"
            f"QScrollBar::handle:vertical {{ background: {SiColors.SCROLLBAR};"
            f" border-radius: 3px; min-height: 30px; }}")
        self._host = QWidget()
        self._host.setStyleSheet("background: transparent;")
        self._list_lay = QVBoxLayout(self._host)
        self._list_lay.setContentsMargins(0, 2, 4, 0)
        self._list_lay.setSpacing(8)
        self._scroll.setWidget(self._host)
        lay.addWidget(self._scroll, stretch=1)

        self._empty_lab = QLabel("暂无场景")
        self._empty_lab.setAlignment(Qt.AlignCenter)
        self._empty_lab.setStyleSheet(
            f"color: {SiColors.TEXT_SECONDARY}; background: transparent; font-size: 10pt;")
        lay.addWidget(self._empty_lab)

        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        refresh = QPushButton("刷新")
        refresh.setCursor(Qt.PointingHandCursor)
        refresh.setStyleSheet(
            f"QPushButton {{ background: {SiColors.SURFACE}; border: none; border-radius: 8px;"
            f" padding: 6px 16px; color: {SiColors.TEXT_PRIMARY}; }}"
            f"QPushButton:hover {{ background: {SiColors.BTN_HOVER}; }}")
        refresh.clicked.connect(self._load)
        btn_row.addWidget(refresh)
        lay.addLayout(btn_row)

        if self._guard.enabled:
            self._hint.setText(
                "安全模式（MIWU_SAFE_DEVICE）已启用：场景执行已禁用，"
                "本列表不展示。清除该环境变量后重启即可正常使用场景。")
            self._hint.show()
            self._empty_lab.hide()
            self._scroll.hide()
            self._sub.setText("场景已禁用")
            return
        self._load()

    # ---------- 数据 ----------

    def _load(self) -> None:
        self._sub.setText("正在获取场景…")
        self._empty_lab.hide()
        self._scroll.hide()
        self._jobs.submit(
            self._service.list_scenes,
            on_success=self._render,
            on_error=self._load_failed,
        )

    def _load_failed(self, error: Exception) -> None:
        if not shiboken6.isValid(self):
            return
        self._sub.setText("获取失败")
        self._hint.setText(f"拉取场景列表失败：{error}")
        self._hint.show()

    def _render(self, scenes: list[SceneInfo]) -> None:
        if not shiboken6.isValid(self):
            return
        while self._list_lay.count():
            item = self._list_lay.takeAt(0)
            if w := item.widget():
                w.deleteLater()
        if not scenes:
            self._empty_lab.setText("暂无手动场景\n（可在米家 App「智能 → + → 手动控制」中创建）")
            self._empty_lab.show()
            self._sub.setText("共 0 个场景")
            return
        # 家庭分组：组名小标题 + 场景行
        last_home = None
        for scene in scenes:
            if scene.home_name != last_home:
                last_home = scene.home_name
                group = QLabel(scene.home_name)
                group.setStyleSheet(
                    f"color: {SiColors.TEXT_MUTED}; background: transparent; font-size: 8pt;")
                self._list_lay.addWidget(group)
            self._list_lay.addWidget(self._make_row(scene))
        self._list_lay.addStretch(1)
        self._scroll.show()
        self._sub.setText(f"共 {len(scenes)} 个场景 · 点击「执行」触发")

    def _make_row(self, scene: SceneInfo) -> QFrame:
        row = QFrame()
        row.setObjectName("sceneRow")
        row.setAttribute(Qt.WA_StyledBackground, True)
        row.setStyleSheet(
            f"QFrame#sceneRow {{ background: {SiColors.CARD}; border: 1px solid {SiColors.LINE};"
            f" border-radius: 10px; }}"
            f"QFrame#sceneRow:hover {{ background: {SiColors.CARD_HOVER}; }}")
        lay = QHBoxLayout(row)
        lay.setContentsMargins(14, 10, 14, 10)
        lay.setSpacing(10)

        texts = QVBoxLayout()
        texts.setContentsMargins(0, 0, 0, 0)
        texts.setSpacing(2)
        name = QLabel(scene.name)
        name.setStyleSheet(
            f"color: {SiColors.TEXT_PRIMARY}; background: transparent; font-size: 10pt;")
        texts.addWidget(name)
        home = QLabel(scene.home_name)
        home.setStyleSheet(
            f"color: {SiColors.TEXT_MUTED}; background: transparent; font-size: 8pt;")
        texts.addWidget(home)
        lay.addLayout(texts, stretch=1)

        run_btn = QPushButton("执行")
        run_btn.setFixedSize(64, 30)
        run_btn.setCursor(Qt.PointingHandCursor)
        run_btn.setStyleSheet(
            f"QPushButton {{ background: {SiColors.THEME}; color: {SiColors.ON_THEME_TEXT};"
            f" border: none; border-radius: 8px; font-size: 9pt; font-weight: 600; }}"
            f"QPushButton:hover {{ background: {SiColors.THEME_HOVER}; }}")
        run_btn.clicked.connect(lambda: self._run_scene(scene, run_btn))
        lay.addWidget(run_btn)
        return row

    def _run_scene(self, scene: SceneInfo, btn: QPushButton) -> None:
        if self._guard.enabled:
            Toast.info(self, "安全模式已禁用场景执行", 3000)
            return
        ret = QMessageBox.question(
            self, "执行场景",
            f"确认执行场景「{scene.name}」？\n"
            "执行会按该场景设定操作其中的设备。",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if ret != QMessageBox.Yes:
            return
        btn.setEnabled(False)
        self._jobs.submit(
            lambda: self._service.run_scene(scene.scene_id, scene.home_id),
            on_success=lambda _: self._scene_done(scene, btn, None),
            on_error=lambda e: self._scene_done(scene, btn, e),
        )

    def _scene_done(self, scene: SceneInfo, btn: QPushButton, error) -> None:
        if not shiboken6.isValid(self):
            return
        btn.setEnabled(True)
        if error is not None:
            Toast.info(self, f"执行失败：{error}", 4000)
        else:
            Toast.info(self, f"已执行场景「{scene.name}」", 3000)

    # ---------- 布局 ----------

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._place_overlay()
        pw, ph = self._panel.width(), self._panel.height()
        self._panel.move((self.width() - pw) // 2, (self.height() - ph) // 2)

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        if self._fill_parent_window():
            self.raise_()
            self._fade_in()
            return
        from PySide6.QtGui import QGuiApplication
        screen = QGuiApplication.primaryScreen()
        if screen is not None:
            self.setGeometry(screen.availableGeometry())
        self.raise_()
        self._fade_in()
