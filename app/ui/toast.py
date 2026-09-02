# SPDX-License-Identifier: GPL-3.0-or-later
# MiHome-Windows: 米家设备的 Windows 桌面控制端
# Copyright (C) 2026 MiHome-Windows contributors
"""轻量通知浮层：右下角滑现、停留后淡出。

用于"刷新完成，新增 X 台"这类无需用户确认的结果反馈，不打断
当前操作；同一时刻只保留最新一条，新消息直接替换旧消息。

对面板很窄的宿主（如桌面小组件）提供 lock_hint()：两行短文本、
宽度钳制在宿主内、不超出边框，避免单行长文案被窗口边界裁掉。
"""

import shiboken6
from PySide6.QtCore import QPropertyAnimation, Qt, QTimer
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QFrame, QGraphicsOpacityEffect, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from app.ui.si_theme import SiColors


class Toast(QFrame):
    _current: "Toast | None" = None

    @classmethod
    def info(cls, parent: QWidget, text: str, duration_ms: int = 4000) -> None:
        if cls._current is not None and shiboken6.isValid(cls._current):
            cls._current.deleteLater()
        toast = cls(parent, text)
        cls._current = toast
        toast._popup(duration_ms)

    @classmethod
    def lock_hint(cls, parent: QWidget, duration_ms: int = 2400) -> None:
        """小组件锁定时点击空白区的提示：两行、钳制在宿主宽度内。

        第一行加粗主提示，第二行常规说明（去设置解锁），字号略小并
        限制在宿主内换行——小组件本身很窄，单行长文案会溢出被裁。
        """
        if cls._current is not None and shiboken6.isValid(cls._current):
            cls._current.deleteLater()
        toast = cls(
            parent, "",
            lines=[("小组件位置已锁定", True),
                   ("请在「设置 → 小组件」中解锁。", False)])
        cls._current = toast
        toast._popup(duration_ms, fit_host=True)

    def __init__(self, parent: QWidget, text: str,
                 lines: list[tuple[str, bool]] | None = None):
        super().__init__(parent)
        self.setObjectName("toastCard")
        if lines is None:
            lines = [(text, False)]
        self._lines = lines
        lay = QHBoxLayout(self)
        lay.setContentsMargins(18, 12, 18, 12)
        self._lay = lay
        if len(lines) > 1:
            # 多行形态：纵向排布，每行独立配色（首行加粗）
            text_col = QVBoxLayout()
            text_col.setContentsMargins(0, 0, 0, 0)
            text_col.setSpacing(2)
            for index, (line_text, bold) in enumerate(lines):
                label = QLabel(line_text)
                label.setWordWrap(True)
                label.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
                if index == 0:
                    label.setFont(
                        QFont("Microsoft YaHei UI", 9, QFont.Weight.DemiBold))
                    label.setStyleSheet(
                        f"color: {SiColors.TEXT_PRIMARY}; background: transparent;")
                else:
                    label.setFont(QFont("Microsoft YaHei UI", 9))
                    label.setStyleSheet(
                        f"color: {SiColors.TEXT_SECONDARY}; background: transparent;")
                text_col.addWidget(label)
                setattr(self, f"_line_{index}", label)
            self._lay.addLayout(text_col)
        else:
            label = QLabel(text)
            label.setFont(QFont("Microsoft YaHei UI", 10))
            label.setStyleSheet(
                f"color: {SiColors.TEXT_PRIMARY}; background: transparent;")
            self._lay.addWidget(label)

    def _popup(self, duration_ms: int, fit_host: bool = False) -> None:
        self.adjustSize()
        host = self.parentWidget()
        if fit_host and host is not None and shiboken6.isValid(host):
            # 窄宿主（桌面小组件）：宽度钳制在宿主内，放不下时换行
            avail = max(120, host.width() - 16)
            w = min(self.width(), avail)
            if w < self.width():
                self.setFixedWidth(w)
                lay = self.layout()
                if lay is not None:
                    lay.activate()
                    self.adjustSize()
            x = max(4, (host.width() - self.width()) // 2)
            y = max(4, host.height() - self.height() - 12)
            self.move(x, y)
        else:
            x = max(16, host.width() - self.width() - 20)
            y = max(16, host.height() - self.height() - 16)
            # 宿主右下角有语音悬浮球时通知上移，间距与输入框保持一致
            fab = getattr(host, "_voice_fab", None)
            if fab is not None and shiboken6.isValid(fab) and fab.isVisible():
                y -= fab.height() + 12 + 10
            self.move(x, y)
        self.show()
        self.raise_()
        QTimer.singleShot(duration_ms, self._fade_out)

    def _fade_out(self) -> None:
        if not shiboken6.isValid(self):
            return
        effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(effect)
        anim = QPropertyAnimation(effect, b"opacity", self)
        anim.setDuration(400)
        anim.setStartValue(1.0)
        anim.setEndValue(0.0)
        anim.finished.connect(self.deleteLater)
        anim.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)
