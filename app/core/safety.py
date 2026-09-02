# SPDX-License-Identifier: GPL-3.0-or-later
# MiHome-Windows: 米家设备的 Windows 桌面控制端
# Copyright (C) 2026 MiHome-Windows contributors
"""真实设备联调安全保护（SafetyGuard）。

默认完全关闭，不影响正常使用。仅当环境变量 MIWU_SAFE_DEVICE 被显式设置
时启用（与 MiWu 小组件同一约定，值可以是 did、名称片段或型号）：

- 设备列表只保留匹配的设备（其余设备不可见，自然不可操作）；
- service 层对未匹配设备的一切写入/动作执行硬拒绝（即使 UI 被绕过也拦截）；
- 场景（米家手动场景）整体禁用。

用于「真机联调只允许操作台灯2」这类红线场景：跑 GUI 前设置
    $env:MIWU_SAFE_DEVICE="台灯2"
后启动程序，界面只会出现台灯2，且任何对其它设备的控制请求都会被拒绝。
"""

import os

_ENV = "MIWU_SAFE_DEVICE"


class SafetyGuard:
    """进程级只读的单例守卫；匹配以「任一命中」为准。"""

    def __init__(self):
        value = os.environ.get(_ENV, "").strip()
        self._value = value
        self._enabled = bool(value)
        # 纯数字视为 did 精确匹配；其余按名称/型号的包含匹配
        self._did_exact = value if value.isdigit() else None
        self._needle = value.lower() if not value.isdigit() else ""

    @property
    def enabled(self) -> bool:
        return self._enabled

    @property
    def value(self) -> str:
        return self._value

    def matches_did(self, did: str) -> bool:
        """是否允许操作该设备（did/名称/型号任一命中）。"""
        if not self._enabled:
            return True
        if self._did_exact is not None:
            return str(did) == self._did_exact
        return False  # 名称/型号匹配需要额外信息，走 matches()

    def matches(self, did: str, name: str = "", model: str = "") -> bool:
        if not self._enabled:
            return True
        if self._did_exact is not None:
            return str(did) == self._did_exact
        if not self._needle:
            return False
        return (self._needle in str(name).lower()
                or self._needle in str(model).lower())

    def assert_can_operate(self, did: str, name: str = "", model: str = "") -> None:
        """不匹配时抛出带中文说明的异常，供 service 层硬拒绝。"""
        if not self._enabled:
            return
        if not self.matches(did, name, model):
            label = self._value if not self._did_exact else f"设备 {self._did_exact}"
            raise GuardRejected(
                f"安全模式（MIWU_SAFE_DEVICE）已启用：仅允许操作 {label}，"
                f"已拦截对设备 {did} 的控制请求")


class GuardRejected(Exception):
    """安全模式下的硬拒绝。界面层照常按错误提示展示即可。"""


_guard: SafetyGuard | None = None


def get_guard() -> SafetyGuard:
    """进程级守卫单例；环境变量在首次访问时读取。"""
    global _guard
    if _guard is None:
        _guard = SafetyGuard()
    return _guard
