# SPDX-License-Identifier: GPL-3.0-or-later
# MiHome-Windows: 米家设备的 Windows 桌面控制端
# Copyright (C) 2026 MiHome-Windows contributors
"""桌面小组件管理：增删改查 + 实例同步 + 持久化。

Manager 持有全部 DesktopWidget 实例（无父窗口顶层）；启动时按
widgets.json 恢复，设置页的任何改动经 update() 即时应用到窗口。
"""

from PySide6.QtCore import QObject, QTimer

from app.core import widget_store
from app.core.jobs import JobExecutor
from app.core.service import MijiaService
from app.ui.desktop_widget import DesktopWidget

_CASCADE_X, _CASCADE_Y = 120, 120


class WidgetManager(QObject):
    def __init__(self, service: MijiaService, jobs: JobExecutor,
                 parent=None):
        super().__init__(parent)
        self._service = service
        self._jobs = jobs
        self._windows: dict[str, DesktopWidget] = {}
        self._configs: dict[str, dict] = {}
        for cfg in widget_store.load_all():
            self._configs[cfg["id"]] = cfg
            self._windows[cfg["id"]] = self._build_window(cfg)
        # 等主循环就绪后再显示（避免启动早期布局抖动）
        QTimer.singleShot(300, self._show_all)

    # ---------- 生命周期 ----------

    def _build_window(self, cfg: dict) -> DesktopWidget:
        win = DesktopWidget(self, self._service, self._jobs, cfg)
        return win

    def _show_all(self) -> None:
        for cfg in self._configs.values():
            win = self._windows.get(cfg["id"])
            if win is not None and cfg.get("visible", True):
                win.show()

    def shutdown(self) -> None:
        """退出前落盘并隐藏全部窗口。"""
        self._persist()
        for win in list(self._windows.values()):
            win.close()
        self._windows.clear()

    # ---------- 配置访问 ----------

    def list_widgets(self) -> list[dict]:
        return [dict(c) for c in self._configs.values()]

    def get_config(self, wid: str) -> dict | None:
        cfg = self._configs.get(wid)
        return dict(cfg) if cfg else None

    # ---------- 增删 ----------

    def add(self, dids: list[str]) -> dict | None:
        """新建一个小组件（多设备）并即时显示。"""
        dids = [str(d) for d in dids if str(d)]
        if not dids:
            return None
        cfg = widget_store._normalize({
            "id": widget_store.make_id(), "dids": dids,
            "x": _CASCADE_X + len(self._configs) * 28,
            "y": _CASCADE_Y + len(self._configs) * 28,
            "scale": 100, "locked": True, "topmost": True,
            "bg_alpha": 90, "visible": True,
        })
        self._configs[cfg["id"]] = cfg
        win = self._build_window(cfg)
        self._windows[cfg["id"]] = win
        win.show()
        self._persist()
        return dict(cfg)

    def remove(self, wid: str) -> None:
        cfg = self._configs.pop(wid, None)
        win = self._windows.pop(wid, None)
        if cfg is not None or win is not None:
            self._persist()
        if win is not None:
            win.close()
            win.deleteLater()

    # ---------- 字段更新（即时生效 + 落盘） ----------

    def update(self, wid: str, field: str, value) -> None:
        cfg = self._configs.get(wid)
        win = self._windows.get(wid)
        if cfg is None:
            return
        cfg[field] = value
        if win is not None:
            win.apply_config(cfg)
        self._persist()

    def move_done(self, wid: str, x: int, y: int) -> None:
        """拖拽结束后由窗口回调保存位置（不重建窗口）。"""
        cfg = self._configs.get(wid)
        if cfg is None:
            return
        cfg["x"], cfg["y"] = int(x), int(y)
        self._persist()

    def _persist(self) -> None:
        widget_store.save_all(list(self._configs.values()))
