# -*- coding: utf-8 -*-
"""End-to-end: fake admin edits in, built pages out. Run: python test_build_admin.py

Replaces admin_sync.load with a fixture (no network), runs the real build into site/,
asserts every kind of edit landed on the page it belongs to, then runs check.py on
the result. Rebuild with `python build.py` afterwards to get the normal site back.
"""
import io
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SITE = os.path.join(HERE, "site")
sys.path.insert(0, HERE)

import admin_sync

DATA = json.load(io.open(os.path.join(HERE, "data.json"), encoding="utf-8"))
IMG = json.load(io.open(os.path.join(HERE, "images.json"), encoding="utf-8"))["images"]
doors = [p for p in DATA["products"].values() if any(u in IMG for u in p["images"])]
floors = [f for f in DATA["darnox"] if any(u in IMG for u in f["images"])]
PRICED, HIDDEN, ASK = doors[0], doors[1], doors[2]
FLOOR_HIDE = floors[0]
root_cat = sorted(DATA["cat_labels"])[0]
album = "Входни врати"
SB = "https://fake.supabase.co"
PH = {"s": "products/x-600.webp", "l": "products/x-1200.webp", "w": 1200, "h": 900}
PJ = {"s": "projects/y-600.webp", "l": "projects/y-1200.webp", "w": 1200, "h": 1600}


def fake_load():
    cfg = {"url": SB, "key": "k"}
    fix = {
        "overrides": {
            "door:" + PRICED["id"]: {"product_key": "door:" + PRICED["id"], "price": 460.5,
                                     "old_price": 562.0, "hidden": False, "badge": "sale"},
            "door:" + HIDDEN["id"]: {"product_key": "door:" + HIDDEN["id"], "price": None,
                                     "old_price": None, "hidden": True, "badge": None},
            "door:" + ASK["id"]: {"product_key": "door:" + ASK["id"], "price": 0.0,
                                  "old_price": None, "hidden": False, "badge": None},
            "floor:" + FLOOR_HIDE["id"]: {"product_key": "floor:" + FLOOR_HIDE["id"], "price": None,
                                          "old_price": None, "hidden": True, "badge": None},
        },
        "products": [
            {"id": "0f0f0f0f-aaaa-bbbb-cccc-000000000001", "section": "door", "category": root_cat,
             "name": "Тестова врата Сигма", "brand": None, "description": "Ръчно добавена.",
             "price": 249.0, "old_price": None, "sizes": ["80/200", "90/200"], "images": [PH],
             "badge": "new", "hidden": False},
            {"id": "0f0f0f0f-aaaa-bbbb-cccc-000000000002", "section": "nastilki", "category": None,
             "name": "Тестов ламинат Омега 8mm AC4", "brand": "Kronotex", "description": None,
             "price": 30.0, "old_price": None, "sizes": [], "images": [PH], "badge": None, "hidden": False},
        ],
        "photos": [{"id": "p1", "album": album, "photo": PJ},
                   {"id": "p2", "album": "Тераси", "photo": PJ}],
        "settings": {"announcement": "Промоция <b>до 30.10</b>", "phone": "+359 888 111 222"},
    }
    images = {}
    for pr in fix["products"]:
        urls = []
        for ph in pr["images"]:
            url, row = admin_sync.manifest_row(cfg, ph)
            images[url] = row
            urls.append(url)
        pr["images"] = urls
    for ph in fix["photos"]:
        ph["url"], row = admin_sync.manifest_row(cfg, ph["photo"])
        images[ph["url"]] = row
    fix["images"] = images
    return fix


admin_sync.load = fake_load
admin_sync.config = lambda: {"url": SB, "key": "sb_publishable_test"}
import build            # noqa: E402  (module-level build runs against the fixture)
build.main()

fails = []


def page(url):
    p = os.path.join(SITE, url.strip("/"), "index.html")
    return io.open(p, encoding="utf-8").read() if os.path.exists(p) else None


def expect(cond, msg):
    if not cond:
        fails.append(msg)


rec = {r["id"]: r for r in build.CATALOGUE}
# 1. her price, sale price and badge
html = page(rec[PRICED["id"]]["url"])
expect(html and "460,50 €" in html and "(900,66 лв.)" in html, "her euro price not shown exactly as typed")
expect(html and 'class="was"' in html and "562,00 €" in html, "old price not struck through")
expect(html and "badge-sale" in html, "sale badge missing on product page")
expect(html and "price-note" not in html, "confirmed price still carries the draft notice")
# size ladder moved with the base price
if rec[PRICED["id"]].get("size_opts"):
    expect(all(abs(s["price"] - (460.5 * build.BGN_PER_EUR + s["delta"])) < 0.01 for s in rec[PRICED["id"]]["size_opts"]),
           "size options did not move with her base price")
# 2. hidden door: no page, no link anywhere
hid_url = rec[HIDDEN["id"]]["url"]
expect(page(hid_url) is None, "hidden door still has a page")
home = page("/")
cat_pages = [page(build.TREE[p]["url"]) or "" for p in build.TREE]
expect(not any(hid_url in c for c in cat_pages), "hidden door still linked from a category")
# 3. price 0 -> По запитване, no draft notice
html = page(rec[ASK["id"]]["url"])
expect(html and "По запитване" in html and "price-note" not in html, "price 0 did not become По запитване")
# 4. hidden floor gone
expect(page(rec[FLOOR_HIDE["id"]]["url"]) is None, "hidden floor still has a page")
# 5. her door + floor products
mine_door = [r for r in build.ALL_DOORS if r.get("admin")]
expect(len(mine_door) == 1, "her door not in the catalogue")
if mine_door:
    html = page(mine_door[0]["url"])
    expect(html and SB + "/storage/v1/object/public/media/products/x-1200.webp" in html, "her door photo not linked from Supabase")
    expect(html and "badge-new" in html and "Размери" in html and "80/200, 90/200" in html, "her door badge/sizes missing")
    expect(html and "darnox.com" not in html and "ngdoors.bg." not in html, "her door claims a supplier source")
    parent = page(build.TREE[root_cat]["url"]) or ""
    expect(mine_door[0]["url"] in parent or any(mine_door[0]["url"] in c for c in cat_pages), "her door not listed in its category")
mine_floor = [r for r in build.FLOORS if r.get("admin")]
expect(len(mine_floor) == 1 and page(mine_floor[0]["url"]), "her floor item has no page")
expect(mine_floor and "Kronotex" in (page("/nastilki/") or ""), "her floor item not listed on /nastilki/")
# 6. project photos: first in an existing album, and a new album appears
alb = [a for a in build.ALBUMS if a["label"] == album][0]
expect(alb["photos"][0].endswith("projects/y-1200.webp"), "her photo is not first in its album")
expect(page("/proekti/terasi/") is not None, "new album page not written")
# 7. settings: announcement escaped, phone replaced everywhere
expect(home and "Промоция &lt;b&gt;до 30.10&lt;/b&gt;" in home, "announcement missing or not escaped")
expect(home and "tel:+359888111222" in home and "+359 898 441 552" not in home, "phone setting not applied")
# 8. contact form wired to Supabase, panel present and private
k = page("/kontakti/")
expect(k and 'data-sb-url="https://fake.supabase.co"' in k, "contact form not wired to Supabase")
expect(os.path.exists(os.path.join(SITE, "admin", "index.html")), "admin panel not built")
cat = json.load(io.open(os.path.join(SITE, "admin", "catalogue.json"), encoding="utf-8"))
expect(len(cat["items"]) >= 490 and cat["supabase_url"] == SB, "admin catalogue incomplete")
expect(any(i["key"] == "door:" + HIDDEN["id"] for i in cat["items"]), "hidden door missing from the panel (she could not unhide it)")
expect(all(not i["key"].startswith("door:n") for i in cat["items"]), "her own products leaked into the override list")
robots = io.open(os.path.join(SITE, "robots.txt"), encoding="utf-8").read()
smap = io.open(os.path.join(SITE, "sitemap.xml"), encoding="utf-8").read()
expect("Disallow: /admin/" in robots and "/admin/" not in smap, "admin not kept out of search")

# Every euro amount she can type must print back as itself: 0,01 € to 20 000 €.
bad = [c for c in range(1, 2000001, 13)
       if build.money(c / 100.0 * build.BGN_PER_EUR).split(" €")[0].split(">")[-1]
       != ("%.2f" % (c / 100.0)).replace(".", ",")]
expect(not bad, "%d euro amounts do not survive the round trip, e.g. %s" % (len(bad), bad[:3]))

import check      # noqa: E402
rc = check.main()
expect(rc == 0, "check.py failed on the admin-edited build")

for f in fails:
    print("FAIL  " + f)
print("test_build_admin: %s" % ("ALL PASS" if not fails else "%d FAIL" % len(fails)))
sys.exit(1 if fails else 0)
