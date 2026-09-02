# SPDX-License-Identifier: GPL-3.0-or-later
# MiHome-Windows: 米家设备的 Windows 桌面控制端
# Copyright (C) 2026 MiHome-Windows contributors
"""真实设备联调安全保护（SafetyGuard）。

默认完全关闭，不影响正常使用。仅当环境变量 MIWU_SAFE_DEVICE 被显式设置
时启用（与 MiWu 小组件同一约定）：

- 值可为 did（纯数字=精确匹配）或名称/型号片段；
- 名称匹配对**空白不敏感**，且经 service 层把云端英文默认名解析为
  本地化显示名（spec 中文产品名）后再比一次——用户视角的
  「台灯2」能命中云端原名 "Mijia LED Desk Lamp 2"；
- 匹配结果会解析为 allowed_dids 白名单：解析完成后，写校验只认白名单
  did，不再依赖名称形态，避免「列表能显示但写入被误拒」。

启用后的效果：
- 设备列表只保留匹配设备（其余设备不可见，自然不可操作）；
- service 层对白名单之外的 did 的一切写入/动作执行硬拒绝（即使 UI 被
  绕过也拦截）；
- 场景（米家手动场景）整体禁用。

用法：跑 GUI 前设置
    $env:MIWU_SAFE_DEVICE="台灯2"      # 或 did：$env:MIWU_SAFE_DEVICE="942167279"
后启动程序。
"""

import os
import re

_ENV = "MIWU_SAFE_DEVICE"


def _norm(text: str) -> str:
    """空白不敏感的小写归一（含全角空格），用于包含匹配。"""
    return re.sub(r"\s+", "", str(text).lower())


class SafetyGuard:
    """进程级单例守卫。

    matches()/matches_did() 语义：
    - did 精确模式（value 为纯数字）：只认 did == value；
    - 名称/型号模式：did 已进入 allowed_dids（service 解析的本地化
      白名单）即放行；否则按 name/model 的归一化包含匹配兜底。
    """

    def __init__(self):
        value = os.environ.get(_ENV, "").strip()
        self._value = value
        self._enabled = bool(value)
        # 纯数字视为 did 精确匹配；其余按名称/型号的包含匹配
        self._did_exact = value if value.isdigit() else None
        self._needle = "" if self._did_exact else _norm(value)
        # service 解析出的允许操作 did 白名单（名称模式时使用）
        self.allowed_dids: set[str] = set()

    @property
    def enabled(self) -> bool:
        return self._enabled

    @property
    def value(self) -> str:
        return self._value

    @property
    def did_exact(self) -> str | None:
        return self._did_exact

    def set_allowed_dids(self, dids: set[str]) -> None:
        """由 service 在列表/索引刷新时写入解析结果（名称模式）。"""
        self.allowed_dids = set(str(d) for d in dids)

    def contains(self, text: str) -> bool:
        """归一化包含匹配：needle in text（空白/大小写不敏感）。"""
        if not self._needle:
            return False
        return self._needle in _norm(text)

    def matches_did(self, did: str) -> bool:
        """是否允许操作该 did（白名单/精确匹配生效后即放行）。"""
        if not self._enabled:
            return True
        if self._did_exact is not None:
            return str(did) == self._did_exact
        return str(did) in self.allowed_dids

    def matches(self, did: str, name: str = "", model: str = "") -> bool:
        if not self._enabled:
            return True
        if self._did_exact is not None:
            return str(did) == self._did_exact
        if str(did) in self.allowed_dids:
            return True
        if not self._needle:
            return False
        return self.contains(name) or self.contains(model)

    def assert_can_operate(self, did: str, name: str = "", model: str = "") -> None:
        """不匹配时抛出带中文说明的异常，供 service 层硬拒绝。"""
        if not self._enabled:
            return
        if not self.matches(did, name, model):
            label = self._value
            raise GuardRejected(
                f"安全模式（{_ENV}）已启用：仅允许操作与「{label}」匹配的设备，"
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
