# SPDX-License-Identifier: GPL-3.0-or-later
"""新增能力的离屏冒烟测试（无网络、无账号、不写运行数据）。

覆盖：SafetyGuard 过滤/硬拒绝语义、工作台智能默认键与参数化动作卡、
卡片快捷操作弹层渲染。运行：python -m tests.feature_smoke
"""
import os

os.environ["QT_QPA_PLATFORM"] = "offscreen"

# 安全模式测试先于任何 get_guard() 调用设置环境变量
os.environ["MIWU_SAFE_DEVICE"] = "942167279"

from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QLineEdit,
    QPushButton,
    QSlider,
    QSpinBox,
)

app = QApplication([])

# ---------- 1. SafetyGuard 语义 ----------
from app.core.safety import SafetyGuard, GuardRejected

guard = SafetyGuard()
assert guard.enabled
assert guard.matches("942167279", "台灯2", "xiaomi.light.lamp31")
assert guard.matches_did("942167279")
assert not guard.matches("000000001", "其他设备", "other.model")
try:
    guard.assert_can_operate("000000001", "其他设备", "other.model")
    raise SystemExit("guard 未拒绝非匹配设备")
except GuardRejected:
    pass
guard.assert_can_operate("942167279", "台灯2", "xiaomi.light.lamp31")
print("1. SafetyGuard 语义 OK")

del os.environ["MIWU_SAFE_DEVICE"]
guard_free = SafetyGuard()
assert not guard_free.enabled and guard_free.matches("anything")
print("2. 未启用时放行 OK")

# 2b. 名称模式：云端英文名经白名单解析放行；空白不敏感
from app.core.safety import _norm
g2 = SafetyGuard()
g2._enabled = True
g2._did_exact = None
g2._value = "台灯2"
g2._needle = _norm("台灯2")
assert g2.contains("Mijia LED Desk Lamp 2") is False  # 英文名不直配
assert g2.contains("米家台灯 2") is True              # 空白不敏感
g2.set_allowed_dids({"942167279"})
assert g2.matches_did("942167279")
assert g2.matches("942167279", "Mijia LED Desk Lamp 2", "xiaomi.light.lamp31")
g2.assert_can_operate("942167279", "Mijia LED Desk Lamp 2", "xiaomi.light.lamp31")
try:
    g2.assert_can_operate("2149401425", "Mijia Refrigerator", "midjd.fridge.bx27l")
    raise SystemExit("白名单外设备未被拒绝")
except GuardRejected:
    pass
print("2b. 名称模式 + 白名单解析 OK")

# 场景对话框（安全模式禁用态）需要在 get_guard() 首次调用前设置环境
os.environ["MIWU_SAFE_DEVICE"] = "942167279"

# ---------- 3. 工作台智能默认键 ----------
from app.core.models import ActionInfo, DeviceDetail, PropInfo
from app.ui.workbench_panel import WorkbenchPanel

panel = WorkbenchPanel(None, None)  # 仅构造骨架，不用真 service/jobs

lamp_props = [
    PropInfo(name="on", desc="开关 / 电源", type="bool",
             readable=True, writable=True, range=None, value_list=None),
    PropInfo(name="brightness", desc="Brightness / 亮度", type="int",
             readable=True, writable=True, range=(1, 100, 1)),
    PropInfo(name="color-temperature", desc="Color Temperature / 色温", type="int",
             readable=True, writable=True, range=(2700, 5100, 1)),
    PropInfo(name="mode", desc="Mode / 模式", type="int",
             readable=True, writable=True, range=None,
             value_list=[{"value": 0, "description": "Eye Care"},
                         {"value": 1, "description": "Reading"}]),
]
detail = DeviceDetail(did="0", name="台灯2", model="xiaomi.light.lamp31",
                      props=lamp_props, actions=[])
panel._build_module_defs(detail)
keys = panel._default_keys()
assert "on" in keys, keys
assert "brightness" in keys, keys
assert "color-temperature" in keys, keys
assert "mode" not in keys, keys  # 枚举模式不进智能默认
print("3. 工作台智能默认键 OK:", keys)

# ---------- 4. 参数化动作卡 ----------
from app.core.models import ActionArg

recorded = {}


def fake_run_action(name, value):
    recorded["name"] = name
    recorded["value"] = value


panel._run_action = fake_run_action  # type: ignore
panel._action_args_map = {}
panel._detail = detail
act = ActionInfo(name="pet-food-out", desc="喂食")
card = panel._build_param_action_card(act, [
    ActionArg(name="amount", desc="Food Amount", type="int",
              range=(1, 10, 1)),
])
spin = card.findChildren(QSpinBox)
assert spin, "参数化动作卡缺少数值输入"
spin[0].setValue(3)
exec_btn = [b for b in card.findChildren(QPushButton) if b.text() == "执行"]
assert exec_btn, "缺少执行按钮"
exec_btn[0].click()
app.processEvents()
assert recorded == {"name": "pet-food-out", "value": [3]}, recorded

act_text = ActionInfo(name="play-radio", desc="播放电台")
card_text = panel._build_text_action_card(act_text)
edits = card_text.findChildren(QLineEdit)
assert edits
edits[0].setText("音乐电台")
b2 = [b for b in card_text.findChildren(QPushButton) if b.text() == "执行"][0]
recorded.clear()
b2.click()
app.processEvents()
assert recorded == {"name": "play-radio", "value": "音乐电台"}, recorded
print("4. 参数化动作卡 / 文本动作卡 OK")

# ---------- 5. 快捷操作弹层（fake service） ----------
from app.ui.quick_ops import QuickOpsPopup


class _FakeJobs:
    def submit(self, fn, on_success=None, on_error=None):
        try:
            result = fn()
        except Exception as exc:  # noqa: BLE001
            if on_error is not None:
                on_error(exc)
        else:
            if on_success is not None:
                on_success(result)


class _FakeService:
    def quick_op_defs(self, did):
        return self.quick_op_candidates(did)

    def quick_op_candidates(self, did):
        from app.core.models import QuickOpInfo
        return [
            QuickOpInfo(name="brightness", desc="亮度", type="int",
                        kind="slider", range=(1, 100, 1)),
            QuickOpInfo(name="color-temperature", desc="色温", type="int",
                        kind="slider", range=(2700, 5100, 1)),
        ]

    def read_quick_values(self, did, names):
        return {"brightness": 60, "color-temperature": 4000}

    def write_quick_value(self, did, name, value):
        self.last_write = (name, value)


from app.core.models import DeviceInfo

device = DeviceInfo(did="942167279", name="台灯2", model="xiaomi.light.lamp31",
                    home_name="我的家庭", room_name="卧室", online=True)
fake_svc = _FakeService()
popup = QuickOpsPopup(fake_svc, _FakeJobs(), device)  # type: ignore
sliders = popup.findChildren(QSlider)
assert len(sliders) == 2, f"期望 2 个滑块，实际 {len(sliders)}"
# 初始值回填
assert sliders[0].value() == 60, sliders[0].value()
assert sliders[1].value() == 4000, sliders[1].value()
print("5. 快捷操作弹层渲染 + 回填 OK")

# 5b. inline 模式 + 自选 op_names 过滤
from PySide6.QtWidgets import QVBoxLayout as _QVBoxLayout, QWidget as _QWidget

host_w = _QWidget()
host_lay = _QVBoxLayout(host_w)
inline_pop = QuickOpsPopup(fake_svc, _FakeJobs(), device,  # type: ignore
                           parent=host_w, inline=True, show_header=False)
host_lay.addWidget(inline_pop)
host_w.show()
app.processEvents()
assert len(inline_pop.findChildren(QSlider)) == 2
only_ct = QuickOpsPopup(fake_svc, _FakeJobs(), device,  # type: ignore
                        parent=host_w, inline=True, show_header=False,
                        op_names=["color-temperature"])
app.processEvents()
assert len(only_ct.findChildren(QSlider)) == 1, "op_names 过滤失效"
print("5b. inline 复用 + 自选过滤 OK")

# 5c. 滑块提交回执（回归：on_success 曾缺 'v' 参数抛 TypeError）
fake_svc.last_write = None
popup._commit_value("brightness", 80,
                    on_success=lambda v: None)  # 模拟松手提交
app.processEvents()
assert fake_svc.last_write == ("brightness", 80), fake_svc.last_write
assert popup.isEnabled(), "提交完成后应恢复可用"
print("5c. 滑块提交回执 OK")

# ---------- 6. 场景对话框（安全模式禁用态） ----------
from app.core.safety import get_guard
assert get_guard().enabled  # 上面已重置 MIWU_SAFE_DEVICE，首调即启用
from app.ui.scenes_dialog import ScenesDialog

dlg = ScenesDialog(None, None)  # type: ignore   # guard 分支不触网
assert dlg._guard.enabled
assert not dlg._scroll.isVisibleTo(dlg), "安全模式应隐藏场景列表"
print("6. 场景对话框安全模式分支 OK")

# ---------- 7. 桌面小组件（无标题栏/无 did 数字/开关回填/锁定提示） ----------
from app.ui.desktop_widget import DesktopWidget
from app.ui.power_button import PowerButton
from app.ui.toast import Toast
from PySide6.QtWidgets import QLabel as _QLabel


class _WidgetMgr:
    def devices_lookup(self):
        return {}

    def move_done(self, *args):
        pass

    def broadcast_power(self, *args):
        pass


class _WidgetSvc(_FakeService):
    def power_states(self, dids):
        return {d: True for d in dids}

    def toggle_power(self, did):
        return False


_wcfg = {"id": "w1", "dids": ["942167279"],
         "devices": {"942167279": {"name": "台灯2", "room": "卧室",
                                   "online": True}},
         "scale": 100, "locked": True, "topmost": True, "bg_alpha": 90,
         "device_ops": {"942167279": []}, "x": 10, "y": 10}
_win = DesktopWidget(_WidgetMgr(), _WidgetSvc(), _FakeJobs(), _wcfg)
app.processEvents()
assert not hasattr(_win, "_handle"), "顶部标题栏手柄应已移除"
texts = [l.text() for l in _win._content.findChildren(_QLabel)]
assert not any("942167279" in t for t in texts), f"控件里残留 did 数字: {texts}"
assert "942167279" in _win._power_btns
_pbtn = _win._power_btns["942167279"]
assert _pbtn.width() >= 36, f"开关圆钮未放大到 36: {_pbtn.width()}"
# 初始未知 -> 回读后应显示真实开状态（1.1 回归：开着却显示关）
assert _pbtn.state() is None
_win._refresh_power_states()
app.processEvents()
assert _pbtn.state() is True, f"回读后开关状态未更新: {_pbtn.state()}"
# 锁定提示两行且钳制在小组件宽度内（1.2 回归：超出边框显示不全）
Toast.lock_hint(_win)
app.processEvents()
_hint = Toast._current
assert _hint is not None and _hint.width() <= _win.width(), \
    f"锁定提示超出小组件宽度: {_hint.width()} > {_win.width()}"
if _hint is not None:
    _hint.deleteLater()
app.processEvents()
_win.apply_config({**_wcfg, "locked": False})  # 解锁不应崩
_win.close()
print("7. 桌面小组件：无标题栏/无 did/开关回填/提示适配 OK")

popup.close()
panel.deleteLater()
print("FEATURE SMOKE PASS")
