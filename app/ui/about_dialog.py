# SPDX-License-Identifier: GPL-3.0-or-later
# MiHome-Windows: 米家设备的 Windows 桌面控制端
# Copyright (C) 2026 MiHome-Windows contributors
"""关于对话框：项目信息、修改版说明、功能简介与上游依赖致谢。"""

from PySide6.QtCore import QSize, QUrl, Qt
from PySide6.QtGui import QDesktopServices, QFont
from PySide6.QtWidgets import QLabel, QPushButton, QSizePolicy, QVBoxLayout

import qtawesome as qta

from app import __version__
from app.ui.overlay_dialog import OverlayDialog
from app.ui.si_theme import SiColors
from app.ui.toast import Toast

# 本分支（本地修改版）仓库；上游原版见下方致谢与介绍文案
GITHUB_URL = "https://github.com/iop666/MiHome-Windows"
UPSTREAM_URL = "https://github.com/huanyuejue/MiHome-Windows"
MIJIA_API_URL = "https://github.com/Do1e/mijia-api"


class AboutDialog(OverlayDialog):
    """关于：遮罩 + 居中面板，与设置页同款观感。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("关于")

        panel = self._panel
        panel.setFixedSize(500, 600)

        lay = QVBoxLayout(panel)
        lay.setContentsMargins(24, 18, 24, 14)
        lay.setSpacing(9)

        # ---- 标题 + 版本 ----
        self._title_label = QLabel("米家 - MiHome for Windows")
        self._title_label.setFont(QFont("Microsoft YaHei UI", 14, QFont.Weight.DemiBold))
        self._title_label.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        lay.addWidget(self._title_label)

        self._version_label = QLabel(f"版本 v{__version__} · 本地修改版")
        self._version_label.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        lay.addWidget(self._version_label)

        # ---- 修改版说明 ----
        self._fork_label = QLabel("修改版")
        self._fork_label.setFont(QFont("Microsoft YaHei UI", 11, QFont.Weight.DemiBold))
        self._fork_label.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        lay.addWidget(self._fork_label)

        self._fork_desc_label = QLabel(
            f'本版基于上游原版 <a href="{UPSTREAM_URL}">huanyuejue/MiHome-Windows</a> '
            "二次开发而来：保留原版全部能力（扫码登录、设备列表、详情工作台、"
            "托盘、小爱语音、深浅主题等），并在其之上做了界面调整与功能扩展。"
            "主要差异见 README「与原版的差异」一节，简要包括：桌面小组件"
            "（桌面常驻多设备控件、可单独固定浅/深外观、显示/隐藏、逐台自选控件）、"
            "托盘增强（常显调节、调节值与开关的跨界面实时同步、"
            "图标颜色可选、右键重启）、主界面米家浅色风与设备产品图、"
            "卡片宽度可选等。")
        self._fork_desc_label.setWordWrap(True)
        self._fork_desc_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextBrowserInteraction)
        self._fork_desc_label.setOpenExternalLinks(True)
        lay.addWidget(self._fork_desc_label)
        lay.addSpacing(8)

        # ---- 功能简介 ----
        self._intro_label = QLabel(
            "米家设备的 Windows 桌面控制端：扫码登录米家账号后，在本地窗口中"
            "查看与控制家里的米家设备——设备卡片快速开关、详情工作台、系统"
            "托盘快捷控制、桌面小组件、小爱语音指令与深浅色主题。")
        self._intro_label.setWordWrap(True)
        lay.addWidget(self._intro_label)
        lay.addSpacing(10)

        # ---- 上游依赖：mijiaAPI / 原版项目 ----
        self._dep_title_label = QLabel("上游致谢")
        dep_title_font = QFont("Microsoft YaHei UI", 10, QFont.Weight.DemiBold)
        self._dep_title_label.setFont(dep_title_font)
        self._dep_title_label.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        lay.addWidget(self._dep_title_label)

        self._dep_label = QLabel(
            f'· 界面与交互基于 <a href="{UPSTREAM_URL}">huanyuejue/'
            f'MiHome-Windows</a>（GPL-3.0）修改；<br>'
            f'· 米家接入基于 <a href="{MIJIA_API_URL}">mijiaAPI</a>——'
            "米家 API 的 Python 封装，扫码登录、设备列表、属性读写与动作执行"
            "均由它完成。")
        self._dep_label.setWordWrap(True)
        self._dep_label.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self._dep_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextBrowserInteraction)
        self._dep_label.setOpenExternalLinks(True)
        lay.addWidget(self._dep_label)

        lay.addStretch(1)

        # ---- 底部：检测更新 + GitHub 入口（上下堆叠）----
        btn_col = QVBoxLayout()
        btn_col.setSpacing(10)
        self._update_btn = QPushButton(" 检测更新（上游 Releases）")
        self._update_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._update_btn.setIcon(qta.icon("mdi.update", color=SiColors.TEXT_PRIMARY))
        self._update_btn.setIconSize(QSize(20, 20))
        self._update_btn.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Fixed)
        self._update_btn.clicked.connect(self._check_update)
        self._checking = False
        btn_col.addWidget(self._update_btn, alignment=Qt.AlignHCenter)

        self._github_btn = QPushButton(" 本修改版仓库 (iop666/MiHome-Windows)")
        self._github_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._github_btn.setIcon(qta.icon("mdi.github", color=SiColors.TEXT_PRIMARY))
        self._github_btn.setIconSize(QSize(20, 20))
        self._github_btn.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Fixed)
        self._github_btn.clicked.connect(
            lambda: QDesktopServices.openUrl(QUrl(GITHUB_URL)))
        btn_col.addWidget(self._github_btn, alignment=Qt.AlignHCenter)
        lay.addLayout(btn_col)

        self._apply_styles()

    def _check_update(self) -> None:
        # 请求在途时忽略重复点击，避免叠发多个网络请求
        if self._checking:
            return
        self._checking = True
        self._update_btn.setEnabled(False)
        self._update_btn.setText(" 检查中…")
        icon_color = SiColors.TEXT_SECONDARY

        def _restore() -> None:
            self._checking = False
            if self._update_btn is not None:
                self._update_btn.setEnabled(True)
                self._update_btn.setText(" 检测更新（上游 Releases）")
                self._update_btn.setIcon(
                    qta.icon("mdi.update", color=SiColors.TEXT_PRIMARY))

        def _finish(info, error) -> None:
            checker.deleteLater()
            _restore()
            if error is not None:
                Toast.info(self, f"检查更新失败：{error}", 4000)
                return
            from app import __version__
            from app.core.update_checker import is_newer
            if info is None or not is_newer(info.tag, __version__):
                Toast.info(self, "当前已是最新版本", 2500)
                return
            from app.ui.update_flow import prompt_new_version
            prompt_new_version(self, info)

        from app.core.update_checker import UpdateChecker
        checker = UpdateChecker(self)
        checker.check_finished.connect(_finish)
        # 检查中文案用次要色弱化，配合禁用态传达「进行中」
        self._update_btn.setIcon(qta.icon("mdi.update", color=icon_color))
        checker.check()

    def _apply_styles(self) -> None:
        """主题相关内联样式：构造与 retheme 共用。"""
        self._title_label.setStyleSheet(
            f"color: {SiColors.TEXT_PRIMARY}; background: transparent;")
        self._version_label.setStyleSheet(
            f"color: {SiColors.TEXT_SECONDARY}; background: transparent; font-size: 9pt;")
        self._fork_label.setStyleSheet(
            f"color: {SiColors.THEME}; background: transparent; font-size: 11pt;")
        self._fork_desc_label.setStyleSheet(
            f"color: {SiColors.TEXT_SECONDARY}; background: transparent; font-size: 9pt;"
            f" a {{ color: {SiColors.THEME}; }}")
        self._intro_label.setStyleSheet(
            f"color: {SiColors.TEXT_SECONDARY}; background: transparent; font-size: 10pt;")
        self._dep_title_label.setStyleSheet(
            f"color: {SiColors.TEXT_PRIMARY}; background: transparent;")
        self._dep_label.setStyleSheet(
            f"color: {SiColors.TEXT_SECONDARY}; background: transparent; font-size: 10pt;"
            f" a {{ color: {SiColors.THEME}; }}")
        btn_style = (
            f"QPushButton {{ background: {SiColors.SURFACE}; border: none;"
            f" border-radius: 8px; padding: 8px 18px; color: {SiColors.TEXT_PRIMARY}; }}"
            f"QPushButton:hover {{ background: {SiColors.BTN_HOVER}; }}"
            f"QPushButton:disabled {{ color: {SiColors.TEXT_FAINT}; }}")
        self._update_btn.setStyleSheet(btn_style)
        self._update_btn.setIcon(
            qta.icon("mdi.update", color=SiColors.TEXT_PRIMARY))
        self._github_btn.setStyleSheet(btn_style)
        self._github_btn.setIcon(qta.icon("mdi.github", color=SiColors.TEXT_PRIMARY))

    def retheme(self) -> None:
        """主题切换：重设面板底色与全部内联样式。"""
        super().retheme()
        self._apply_styles()

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._place_overlay()
        # 面板居中放置
        x = (self.width() - self._panel.width()) // 2
        y = (self.height() - self._panel.height()) // 2
        self._panel.move(x, y)

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        # 一律铺满可用屏幕：面板不被主窗口客户区裁剪，可完整显示
        from PySide6.QtGui import QGuiApplication
        screen = QGuiApplication.primaryScreen()
        if screen is not None:
            self.setGeometry(screen.availableGeometry())
        self.raise_()
        self._fade_in()
