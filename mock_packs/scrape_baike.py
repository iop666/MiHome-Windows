# SPDX-License-Identifier: GPL-3.0-or-later
"""从米家百科(home.mi.com/webapp/content/baike)抓取真实设备目录。

流程：
1. productCategories/V1 分页拉全部品类（pageSize 12 / pageIndex 递增）；
2. 每个品类调 products/byCategory/V1?ptId=<id> 拉该类全部产品；
3. 汇总去重（按 model）→ baike_catalog.json。

每个产品字段：name/model/brand/category(ptId+name)/realIcon。
运行：python mock_packs/scrape_baike.py
"""
import json
import time
from pathlib import Path

import requests

OUT = Path(__file__).resolve().parent / "baike_catalog.json"
BASE = "https://home.mi.com/cgi-op/api/v1/baike"
HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                   "AppleWebKit/537.36 Chrome/126 Safari/537.36"),
    "Referer": "https://home.mi.com/webapp/content/baike/index.html",
}
S = requests.Session()
S.headers.update(HEADERS)


def get(path, **params):
    r = S.get(BASE + path, params=params, timeout=30)
    r.raise_for_status()
    return r.json()


def fetch_categories():
    cats = []
    page = 1
    while page <= 40:
        data = get("/productCategories/V1", pageSize=12, pageIndex=page)
        lst = (data.get("data") or {}).get("list") or []
        if not lst:
            break
        for c in lst:
            cats.append({"ptId": c.get("ptId"), "name": c.get("name")})
        if len(lst) < 12:
            break
        page += 1
        time.sleep(0.2)
    return cats


def fetch_category_products(ptid):
    data = get("/products/byCategory/V1", ptId=ptid)
    d = data.get("data") or {}
    return d.get("productSimpleVoList") or []


def main():
    cats = fetch_categories()
    print("categories:", len(cats))
    seen = {}
    failed = []
    for c in cats:
        try:
            items = fetch_category_products(c["ptId"])
        except Exception as exc:  # noqa: BLE001
            print("cat fail", c, exc)
            failed.append(c)
            continue
        for it in items:
            model = it.get("model")
            name = it.get("name")
            if not model or not name:
                continue
            rec = seen.setdefault(model, {
                "model": model, "name": name,
                "brand": it.get("brand") or "",
                "category": c["name"], "ptId": c["ptId"],
                "realIcon": it.get("realIcon") or ""})
            if not rec["realIcon"] and it.get("realIcon"):
                rec["realIcon"] = it["realIcon"]
        print(f"cat {c['name']}: {len(items)}")
        time.sleep(0.15)
    all_items = sorted(seen.values(), key=lambda x: x["category"])
    OUT.write_text(json.dumps(all_items, ensure_ascii=False, indent=0),
                   encoding="utf-8")
    print("total unique products:", len(all_items))
    print("failed cats:", len(failed))
    from collections import Counter
    print("brands top:", Counter(i.get("brand") for i in all_items).most_common(25))


if __name__ == "__main__":
    main()
