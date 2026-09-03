# 下载 mock_home.json 里全部产品图到 mock_icons/<model>.png（本地离线图标包）
# 运行：.venv\Scripts\python.exe mock_packs\download_icons.py
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import requests

HERE = Path(__file__).resolve().parent
OUT = HERE / "mock_icons"
PACK = HERE / "mock_home.json"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
_MAGIC = (b"\x89PNG\r\n\x1a\n", b"\xff\xd8\xff\xe0", b"\xff\xd8\xff\xe1")


def fetch(model: str, url: str) -> tuple[str, bool]:
    if not url:
        return model, False
    path = OUT / f"{model}.png"
    if path.is_file() and path.stat().st_size > 0:
        return model, True
    try:
        r = requests.get(url, timeout=25, headers=HEADERS)
        if r.status_code == 200 and r.content[:8] in _MAGIC:
            path.write_bytes(r.content)
            return model, True
    except Exception:
        pass
    return model, False


def main():
    pack = json.loads(PACK.read_text(encoding="utf-8"))
    icons = pack.get("model_icons") or {}
    OUT.mkdir(exist_ok=True)
    items = list(icons.items())
    ok = 0
    with ThreadPoolExecutor(max_workers=8) as pool:
        for _, success in pool.map(lambda kv: fetch(*kv), items):
            ok += 1 if success else 0
    print(f"icons ok {ok}/{len(items)} -> {OUT}")
    # 移除与当前型号不再匹配的旧文件
    keep = {m for m in icons}
    for f in OUT.glob("*.png"):
        if f.stem not in keep:
            f.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
