# SPDX-License-Identifier: GPL-3.0-or-later
# MiHome-Windows: 米家设备的 Windows 桌面控制端
# Copyright (C) 2026 MiHome-Windows contributors
"""系统托盘控制器：常驻图标 + 菜单 + 快捷窗口编排。"""

from PySide6.QtCore import QSize
from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import QMenu, QSystemTrayIcon

from app.core import settings_store
from app.core.jobs import JobExecutor
from app.core.models import DeviceInfo
from app.core.service import MijiaService
from app.ui.tray.quick_window import TrayQuickWindow

# 托盘图标配色 -> 资源文件（白=默认；黑/绿 为变体；三者图形同源）
_TRAY_ICON_FILES = {
    settings_store.TRAY_ICON_WHITE: "app/ui/tray_icon.png",
    settings_store.TRAY_ICON_BLACK: "app/ui/tray_icon_light.png",
    settings_store.TRAY_ICON_GREEN: "app/ui/tray_icon_green.png",
}


class TrayController:
    """托盘图标控制器：常驻图标 + 快捷窗口 + 右键菜单。"""

    def __init__(self, service: MijiaService, jobs: JobExecutor, main_window):
        self._service = service
        self._jobs = jobs
        self._main = main_window
        self._pending_show = False
        # 快捷窗口设为独立顶层窗口，不随主窗口模态对话框被阻塞
        self._create_quick_window()

        self._tray = QSystemTrayIcon(main_window)
        self._tray.setToolTip("米家 - MiHome for Windows")
        self._tray.activated.connect(self._on_activated)

        menu = QMenu()
        menu.setObjectName("appMenu")
        act_show = QAction("显示主窗口", menu)
        act_show.triggered.connect(self._show_main)
        menu.addAction(act_show)
        act_manage = QAction("管理托盘设备", menu)
        act_manage.triggered.connect(self._emit_manage)
        menu.addAction(act_manage)
        act_settings = QAction("设置", menu)
        act_settings.triggered.connect(self._on_settings)
        menu.addAction(act_settings)
        menu.addSeparator()
        act_quit = QAction("退出", menu)
        act_quit.triggered.connect(self._quit)
        menu.addAction(act_quit)
        self._tray.setContextMenu(menu)

        # 快捷窗口的信号接线统一在 _create_quick_window 内做一次，
        # 此处重复连接曾导致每次触发弹两次对话框

        # 托盘图标常驻，无需可用性检查也尝试显示
        self._tray.show()
        # 按设置里选择的图标颜色渲染（默认白色）
        self.apply_icon_color(None)

    def apply_icon_color(self, color: str | None) -> None:
        """按设置切换托盘图标颜色并立即刷新。

        color 缺省时读取设置；white=白色（默认）/ black=黑色 /
        green=品牌绿。托盘图标配色是用户偏好，与系统任务栏明暗无关，
        设置页切换时实时调用本方法即可即时生效。
        """
        if color not in _TRAY_ICON_FILES:
            color = settings_store.get_tray_icon_color()
        icon_file = _TRAY_ICON_FILES.get(color) or _TRAY_ICON_FILES[
            settings_store.TRAY_ICON_WHITE]
        from app import resource_path
        path = str(resource_path(icon_file))
        icon = QIcon(path)
        icon.addFile(path, QSize(16, 16))
        icon.addFile(path, QSize(32, 32))
        icon.addFile(path, QSize(48, 48))
        self._tray.setIcon(icon)

    def apply_system_icon_theme(self, scheme) -> None:
        """兼容入口：系统深浅色变化不再自动改图标，尊重用户配色设置。

        早期托盘图标跟随任务栏底色（浅任务栏用深色图形），引入
        「托盘图标颜色」设置后以显式选择为准，避免系统信号覆盖用户偏好。
        """
        self.apply_icon_color(None)

    def _create_quick_window(self) -> None:
        """创建快捷窗口并接线；主题切换时整窗重建复用。"""
        self._quick = TrayQuickWindow(self._service, self._jobs, None)
        self._quick.manage_requested.connect(self._on_manage)
        self._quick.open_device_requested.connect(self._on_open_device)
        self._quick.open_main_requested.connect(self._show_main)

    def _emit_manage(self) -> None:
        # 经方法转发而非构造期绑定信号：retheme 重建窗口后菜单仍指向新窗口
        self._quick.manage_requested.emit()

    def _on_activated(self, reason) -> None:
        if reason != QSystemTrayIcon.ActivationReason.Trigger:  # 仅左键单击
            return
        quick = self._quick
        # 鼠标当前位置（即所点托盘图标处）作为「跟随鼠标位置」模式的锚点
        from PySide6.QtGui import QCursor
        anchor = QCursor.pos()
        # 正在播放呼出/隐藏动画时，终止旧动画并以带动画方式切换，避免直接 hide 丢失关闭动画
        if quick.is_animating():
            quick.abort_toggle_animation()
            if quick.isVisible() or quick.is_explicitly_visible():
                quick.hide_animated()
            else:
                quick.show_near_tray(anchor)
            return
        if quick.isVisible():
            quick.hide_animated()
        else:
            quick.show_near_tray(anchor)

    def _show_main(self) -> None:
        self._main.show()
        self._main.raise_()
        self._main.activateWindow()
        if self._main.isMinimized():
            self._main.showNormal()

    def _quit(self) -> None:
        self._tray.hide()
        # 标记为强制退出，避免 closeEvent 拦截为隐藏到托盘
        self._main.request_force_quit()
        self._main.close()
        # quitOnLastWindowClosed 为 False 时需显式退出事件循环
        from PySide6.QtWidgets import QApplication
        app = QApplication.instance()
        if app is not None:
            app.quit()

    def _on_manage(self) -> None:
        self._main.show_tray_manager()

    def _on_settings(self) -> None:
        self._main.show_settings()

    def _on_open_device(self, did: str) -> None:
        # 仅打开设备详情，不呼出主窗口，避免主窗口隐藏时卡死
        self._quick.hide()
        # 直接创建详情对话框，parent 设为 None 使其独立于主窗口显隐
        dev = next((d for d in self._main.devices() if d.did == did), None)
        if dev is None:
            return
        from app.ui.device_dialog import DeviceDetailDialog
        dlg = DeviceDetailDialog(self._service, self._jobs, dev, None)
        dlg.load()
        dlg.exec()
        dlg.deleteLater()

    def set_devices(self, devices: list[DeviceInfo], known_power: dict[str, bool | None]) -> None:
        self._quick.set_devices(devices, known_power)

    def set_metrics(self, metrics: dict[str, str | None]) -> None:
        self._quick.set_metrics(metrics)
        if self._pending_show:
            # 重建前窗口正显示着：设备填充完毕后再呼出，避免空窗口闪现
            self._pending_show = False
            self._quick.show_near_tray()

    def retheme(self) -> None:
        """主题切换：整个快捷窗口重建。

        快捷窗口的内联样式散布在窗框/音频栏/语音条/设备行/工具条
        多处，逐控件补样式总有遗漏（曾反复出现新旧色混杂残留）；
        整窗重建让全部样式天然取新调色板。设备与开关状态由主窗口
        在本调用之后立刻 set_devices 推送，显示状态在此登记。
        """
        was_visible = self._quick.isVisible() or self._quick.is_explicitly_visible()
        self._quick.abort_toggle_animation()
        self._quick.hide()
        self._quick.deleteLater()
        self._create_quick_window()
        self._pending_show = was_visible

    def hide_quick(self) -> None:
        self._quick.hide()

    def set_tray_visible(self, visible: bool) -> None:
        """按设置开关托盘图标显隐：开启时常驻图标可见，关闭时隐藏。"""
        try:
            self._tray.setVisible(visible)
        except Exception:
            pass

    def is_available(self) -> bool:
        return QSystemTrayIcon.isSystemTrayAvailable()

