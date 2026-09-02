# SPDX-License-Identifier: GPL-3.0-or-later
# MiHome-Windows: 米家设备的 Windows 桌面控制端
# Copyright (C) 2026 MiHome-Windows contributors
"""三态圆形电源按钮：设备卡片、托盘快捷行、详情电源行共用。

开=米家绿、关=中灰、未知=描边空心；另有离线与忙碌两个覆盖态。
配色在每次 _apply() 时从当前调色板取值，主题切换后重建控件即生效。
"""

from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import QPushButton

import qtawesome as qta

from app.ui.si_theme import SiColors


class PowerButton(QPushButton):
    """state: True 开 / False 关 / None 未知（或未确认能力）。"""

    def __init__(self, size: int, icon_size: int | None = None, parent=None):
        super().__init__(parent)
        self._size = size
        self._state: bool | None = None
        self._online = True
        self._busy = False
        self.setObjectName("powerBtn")
        side = icon_size if icon_size is not None else int(size * 0.7)
        self.setIconSize(QSize(side, side))
        self.setFixedSize(size, size)
        self.setCursor(Qt.PointingHandCursor)
        self._apply()

    def set_state(self, state: bool | None) -> None:
        self._state = state
        self._apply()

    def state(self) -> bool | None:
        return self._state

    def set_online(self, online: bool) -> None:
        self._online = online
        # 忙碌不视为离线：执行有延迟，保持可点以允许连续点击排队
        self.setEnabled(online)
        self._apply()

    def set_busy(self, busy: bool) -> None:
        self._busy = busy
        # 忙碌期间保持可点：快速连续点击逐个排队执行，不吞点击
        self.setEnabled(self._online)
        self._apply()

    def _apply(self) -> None:
        radius = self._size // 2
        if not self._online:
            self.setIcon(qta.icon('mdi.power', color=SiColors.ICON_DIM))
            self.setStyleSheet(
                f"QPushButton#powerBtn {{ background: {SiColors.SURFACE}; border: none;"
                f" border-radius: {radius}px; }}"
            )
            return
        if self._busy:
            self.setIcon(qta.icon('mdi.power', color=SiColors.ICON_DIM))
            self.setStyleSheet(
                f"QPushButton#powerBtn {{ background: {SiColors.SURFACE_PRESSED}; border: none;"
                f" border-radius: {radius}px; }}"
            )
            return
        if self._state is None:
            self.setIcon(qta.icon('mdi.circle-outline', color=SiColors.ICON_DIM))
            self.setStyleSheet(
                f"QPushButton#powerBtn {{ background: {SiColors.STATE_UNKNOWN_BG};"
                f" border: 2px solid {SiColors.STATE_UNKNOWN_BORDER}; border-radius: {radius}px; }}"
                f"QPushButton#powerBtn:hover {{ background: {SiColors.STATE_UNKNOWN_HOVER}; }}"
            )
            return
        color = SiColors.THEME if self._state else SiColors.STATE_OFF
        self.setIcon(qta.icon('mdi.power', color=SiColors.WHITE))
        self.setStyleSheet(
            f"QPushButton#powerBtn {{ background: {color}; border: none;"
            f" border-radius: {radius}px; }}"
            f"QPushButton#powerBtn:pressed {{ background: {SiColors.PRESSED}; }}"
        )

