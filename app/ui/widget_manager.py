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
        # parent 即主窗口：小组件里改开关时要反向同步主窗口卡片/托盘
        self._host = parent
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
        if field == "visible":
            # 显示/隐藏直接控制窗口显隐（不重建内容）
            if win is not None:
                if value:
                    win.show()
                else:
                    win.hide()
            self._persist()
            return
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

    def sync_device_meta(self, devices: list) -> None:
        """用主窗口最新设备信息补齐小组件显示名/房间/在线（防 did 数字）。"""
        by = {d.did: d for d in devices}
        touched = False
        for cfg in self._configs.values():
            meta = dict(cfg.get("devices") or {})
            changed = False
            for did in cfg.get("dids", []):
                dev = by.get(did)
                if dev is None:
                    continue
                cur = meta.get(did)
                if not cur or cur.get("name") != dev.name or \
                        cur.get("room") != dev.room_name or \
                        bool(cur.get("online", True)) != dev.online:
                    meta[did] = {"name": dev.name, "room": dev.room_name,
                                 "online": dev.online}
                    changed = True
            if changed:
                cfg["devices"] = meta
                touched = True
                win = self._windows.get(cfg["id"])
                if win is not None:
                    win.apply_config(cfg)
        if touched:
            self._persist()

    def broadcast_power(self, did: str, state: bool | None) -> None:
        """某入口改了一台设备开关：同步到所有含该设备的小组件窗口。

        同一设备可能出现在多个小组件里，只在来源窗口回填会留下
        其它窗口开关状态过期（开着却显示关）的观感问题。
        """
        if state is None:
            return
        for win in self._windows.values():
            if win is None:
                continue
            try:
                win.apply_external_power(did, state)
            except Exception:
                continue

    def sync_power_states(self, states: dict) -> None:
        """批量推送一批设备开关状态到全部小组件窗口（主窗口轮询结果）。"""
        if not states:
            return
        for win in self._windows.values():
            if win is None:
                continue
            try:
                for did, state in states.items():
                    if state is not None:
                        win.apply_external_power(did, state)
            except Exception:
                continue

    def broadcast_quick_value(self, did: str, name: str, value) -> None:
        """某入口写了一个可调项：同步到全部小组件行内展开的对应控件。"""
        if not name or value is None:
            return
        for win in self._windows.values():
            if win is None:
                continue
            try:
                win.apply_quick_value(did, name, value)
            except Exception:
                continue
        host = self._host
        if host is not None and hasattr(host, "apply_quick_value_external"):
            try:
                host.apply_quick_value_external(did, name, value)
            except Exception:
                pass

    def update_widget_quick_value(self, did: str, name: str, value) -> None:
        """只更新小组件窗口（托盘写值后的广播入口，避免回环）。"""
        if not name or value is None:
            return
        for win in self._windows.values():
            if win is None:
                continue
            try:
                win.apply_quick_value(did, name, value)
            except Exception:
                continue

    def power_changed_everywhere(self, did: str, state: bool | None) -> None:
        """小组件内改动开关的完整广播：其它小组件 + 主窗口卡片/托盘。"""
        if state is None:
            return
        self.broadcast_power(did, state)
        host = self._host
        if host is not None and hasattr(host, "apply_external_power_sync"):
            try:
                host.apply_external_power_sync(did, state)
            except Exception:
                pass

    def retheme(self) -> None:
        """应用主题切换后强制全部小组件重建内容（取新调色板）。"""
        for wid, cfg in list(self._configs.items()):
            win = self._windows.get(wid)
            if win is not None:
                try:
                    win.apply_config(dict(cfg), force_rebuild=True)
                except Exception:
                    continue

    def _persist(self) -> None:
        widget_store.save_all(list(self._configs.values()))
