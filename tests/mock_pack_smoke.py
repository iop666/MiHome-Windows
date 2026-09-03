# SPDX-License-Identifier: GPL-3.0-or-later
"""虚拟测试家庭冒烟测试（离线，无 Qt 依赖）。

校验 mock_packs/mock_home.json 的数量/房间/类别/品牌覆盖与
MockMijiaService 的列表/开关/读数/详情/快捷项行为。
运行：python -m tests.mock_pack_smoke
"""
import json
from collections import Counter
from pathlib import Path

_PACK = Path(__file__).resolve().parent.parent / "mock_packs" / "mock_home.json"

# 生活场景覆盖面：每组内命中任一关键词即可（真实产品命名差异大）
REQUIRED_GROUPS = [
    ["吸顶", "灯"], ["筒灯"], ["灯带"], ["台灯"], ["床头"], ["落地", "吊扇"],
    ["温湿"], ["人体"], ["门窗", "门磁"], ["烟雾"], ["燃气", "气感"],
    ["水浸", "漏水"], ["体温"], ["门锁", "指纹"], ["净水"], ["净化"],
    ["摄像", "看护", "监控"], ["插座"], ["网关", "中枢"], ["窗帘"],
    ["路由"], ["加湿"], ["除湿"], ["音箱", "音响"], ["开关", "面板"],
    ["空调"], ["浴霸"], ["排风", "换气"], ["马桶"], ["热水器"], ["晾衣"],
    ["扫地", "扫拖"], ["洗地"], ["饭煲", "电饭"], ["饮水", "净水"],
    ["水壶", "电水壶"], ["破壁"], ["咖啡"], ["烤箱", "炸锅"], ["微波"],
    ["油烟"], ["电磁炉", "电陶炉"], ["体脂", "体重", "血压"], ["按摩"],
    ["吹风"], ["牙刷"], ["床垫", "电热毯", "智能床"], ["香薰", "香氛"],
    ["喂食", "宠物"], ["植物", "浇灌"], ["电视", "投影"], ["冰箱"],
    ["洗衣机"], ["遥控"], ["夜灯", "床头"],
]

ROOMS = ("客厅", "餐厅", "阳台", "卧室1", "卧室2", "书房", "厕所1", "厕所2")

if __name__ == "__main__":
    from app.core.mock_devices import MockMijiaService

    pack = json.loads(_PACK.read_text(encoding="utf-8"))
    svc = MockMijiaService(pack)
    devs = svc.list_devices()
    assert len(devs) >= 400, f"设备数不足: {len(devs)}"

    by_room = Counter(d.room_name for d in devs)
    assert set(by_room) == set(ROOMS), (set(by_room), ROOMS)
    for room in ROOMS:
        assert by_room[room] >= 30, (room, by_room[room])

    names = [d.name for d in devs]
    missing = [g for g in REQUIRED_GROUPS
               if not any(any(t in n for t in g) for n in names)]
    assert not missing, f"缺少场景类别: {missing}"

    # 摆位合理性抽查
    water = [d for d in devs if any(t in d.name for t in ("水浸", "漏水"))]
    assert all(d.room_name in ("厕所1", "厕所2", "阳台") for d in water), water
    assert any("晾衣" in d.name and d.room_name == "阳台" for d in devs)
    assert any("燃气" in d.name and d.room_name == "餐厅" for d in devs)
    assert any("浴霸" in d.name and d.room_name.startswith("厕所") for d in devs)

    # 品牌多样性 & 产品图地址覆盖（真实型号 + CDN 图标）
    models_used = {d.model for d in devs}
    icons = pack.get("model_icons") or {}
    with_icon = sum(1 for d in devs if d.model in icons)
    assert len(models_used) >= 80, f"型号太少: {len(models_used)}"
    assert with_icon / len(devs) >= 0.7, f"图标覆盖率不足: {with_icon / len(devs):.0%}"
    assert len(set(d.name.split("·")[0] for d in devs)) == len(ROOMS)

    # 开关语义
    lamp = next(d for d in devs if "吸顶" in d.name)
    cam = next(d for d in devs if any(t in d.name for t in ("摄像", "看护")))
    assert svc.power_state(lamp.did) is not None
    assert svc.power_state(cam.did) is None
    before = svc.power_state(lamp.did)
    svc.toggle_power(lamp.did)
    assert svc.power_state(lamp.did) is not before
    svc.set_power_state(lamp.did, True)

    # 读数 / 详情 / 快捷项
    ht = next(d for d in devs if "温湿" in d.name)
    assert svc.read_metrics([ht.did])[ht.did], svc.read_metrics([ht.did])
    op_names = {o.name for o in svc.quick_op_candidates(lamp.did)}
    assert "brightness" in op_names or "color-temperature" in op_names
    detail = svc.device_detail(lamp.did)
    assert any(p.name == "on" for p in detail.props)

    print(f"MOCK HOME SMOKE PASS: {len(devs)} devices, "
          f"{len(models_used)} models, icons {with_icon}/{len(devs)}, "
          f"{dict(by_room)}")
