# SPDX-License-Identifier: GPL-3.0-or-later
"""虚拟测试家庭冒烟测试（离线，无 Qt 依赖）。

校验 mock_packs/mock_home.json 的数量/房间/类别覆盖，以及
MockMijiaService 的列表/开关/读数/详情/快捷项行为。
运行：python -m tests.mock_pack_smoke
"""
import json
from collections import Counter
from pathlib import Path

_PACK = Path(__file__).resolve().parent.parent / "mock_packs" / "mock_home.json"

# 必需覆盖的类别（按设备名特征词匹配）
REQUIRED_KINDS = [
    "吸顶灯", "筒灯", "灯带", "灯泡", "床头灯", "台灯", "落地灯",
    "温湿度计", "人体传感器", "门窗传感器", "烟雾传感器", "体温计",
    "水浸传感器", "门锁", "空气净化器", "摄像机", "智能插座", "智能网关",
    "窗帘电机", "路由器", "加湿器", "除湿机", "小爱音箱", "智能开关",
    "燃气传感器", "空调", "智能浴霸", "排风扇", "晾衣架", "智能马桶",
    "扫地机器人", "电风扇", "电视", "冰箱", "洗衣机", "智能门铃",
]

if __name__ == "__main__":
    from app.core.mock_devices import MockMijiaService

    pack = json.loads(_PACK.read_text(encoding="utf-8"))
    svc = MockMijiaService(pack)
    devs = svc.list_devices()
    assert len(devs) >= 400, f"设备数不足: {len(devs)}"

    by_room = Counter(d.room_name for d in devs)
    rooms = set(pack["rooms"])
    assert set(by_room) == rooms, (set(by_room), rooms)
    for room in ("客厅", "餐厅", "阳台", "卧室1", "卧室2", "书房",
                 "厕所1", "厕所2"):
        assert by_room[room] >= 30, (room, by_room[room])

    names = [d.name for d in devs]
    missing = [k for k in REQUIRED_KINDS if not any(k in n for n in names)]
    assert not missing, f"缺少类别: {missing}"

    # 摆位合理性抽查：水浸在厕所（阳台防倒灌也合理）、晾衣架/洗衣机
    # 在阳台、燃气传感器放在餐厅（贴近厨房）
    water = [d for d in devs if "水浸传感器" in d.name]
    assert all(d.room_name in ("厕所1", "厕所2", "阳台") for d in water), water
    assert any("晾衣架" in d.name and d.room_name == "阳台" for d in devs)
    assert any("燃气传感器" in d.name and d.room_name == "餐厅" for d in devs)

    # 开关语义：灯可开关；摄像机无开关；状态翻转
    lamp = next(d for d in devs if d.name == "客厅吸顶灯1")
    cam = next(d for d in devs if "摄像机" in d.name)
    assert svc.power_state(lamp.did) is not None
    assert svc.power_state(cam.did) is None
    before = svc.power_state(lamp.did)
    svc.toggle_power(lamp.did)
    assert svc.power_state(lamp.did) is not before

    # 读数：温湿度计有副标题，摄像机没有
    ht = next(d for d in devs if "温湿度计" in d.name)
    assert svc.read_metrics([ht.did])[ht.did], svc.read_metrics([ht.did])

    # 详情与快捷项：灯出 亮度/色温 滑块
    detail = svc.device_detail(lamp.did)
    op_names = {o.name for o in svc.quick_op_candidates(lamp.did)}
    assert "brightness" in op_names and "color-temperature" in op_names
    svc.set_power_state(lamp.did, True)
    assert svc.power_state(lamp.did) is True

    # 模型种类足够多样（>40 种），确保卡片/详情样式能覆盖到不同形态
    assert len({d.model for d in devs}) >= 40
    print(f"MOCK HOME SMOKE PASS: {len(devs)} devices, "
          f"{len({d.model for d in devs})} models, "
          f"{dict(by_room)}")
