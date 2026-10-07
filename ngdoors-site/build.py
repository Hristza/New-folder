# -*- coding: utf-8 -*-
"""Render the NG Doors static site from data.json + images.json into site/.

Everything is plain string templating; there is no framework and no build step
beyond `python build.py`. Re-run it to refresh the catalogue.

Run:  python build.py
"""
import io
import json
import math
import os
import re
import shutil
import sys
import urllib.parse

import pricing

HERE = os.path.dirname(os.path.abspath(__file__))
SITE = os.path.join(HERE, "site")
STATIC = os.path.join(HERE, "static")

PHONE = "+359898441552"
PHONE_H = "+359 898 441 552"
EMAIL = "info@ngdoors.bg"
# Viber has no web fallback: viber.me is for public accounts, not a phone number, so this is
# the only scheme that opens a chat. It does nothing on a desktop without Viber installed,
# which is why the number itself stays visible next to every one of these links.
VIBER = "viber://chat?number=%2B" + PHONE.lstrip("+")
ADDRESS = "бул. Европа 115, 2227 Божурище"
HOURS = "Понеделник – петък, 9:00 – 18:00"
SITE_NAME = "NG Doors"
# Cloudflare Pages project "ngdoors" -> ngdoors.pages.dev (moved off Vercel 2026-09-30:
# Hobby forbids commercial sites). A wrong value here is live SEO damage: every canonical
# and sitemap <loc> uses it. Verify with `wrangler pages project list`, never from memory.
BASE_URL = "https://ngdoors.pages.dev"
BGN_PER_EUR = 1.95583   # the fixed statutory conversion rate

# ------------------------------------------------------------------ slugs
TRANS = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ж": "zh",
    "з": "z", "и": "i", "й": "y", "к": "k", "л": "l", "м": "m", "н": "n",
    "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u", "ф": "f",
    "х": "h", "ц": "ts", "ч": "ch", "ш": "sh", "щ": "sht", "ъ": "a",
    "ь": "y", "ю": "yu", "я": "ya",
}


def slug(s):
    s = (s or "").strip().lower()
    out = []
    for ch in s:
        if ch in TRANS:
            out.append(TRANS[ch])
        elif ch.isalnum() and ord(ch) < 128:
            out.append(ch)
        else:
            out.append("-")
    s = re.sub(r"-+", "-", "".join(out)).strip("-")
    return s or "x"


CYR = re.compile(r"[А-Яа-яЁёЪъЬь]")

# Latin letters that look identical to a Cyrillic one. The supplier's catalogue has
# words welded out of both alphabets — "Moдел" is Latin M+o glued to Cyrillic дел on
# 56 pages — which is invisible on screen and breaks Ctrl-F and the mailto subject.
CONFUSABLE = {"A": "А", "B": "В", "C": "С", "E": "Е", "H": "Н", "K": "К", "M": "М",
              "O": "О", "P": "Р", "T": "Т", "X": "Х", "Y": "У",
              "a": "а", "c": "с", "e": "е", "o": "о", "p": "р", "x": "х", "y": "у"}
_WORD = re.compile(r"[A-Za-zЀ-ӿ]+")


def fix_script(s):
    """Repair words that mix alphabets, leaving genuine Latin words alone.

    Only rewrites a word when it already contains Cyrillic AND every Latin letter
    in it has an identical-looking Cyrillic twin, so 'Floorpan' and 'SPC' survive
    untouched while 'Moдел' and 'добавенa' are made one alphabet again.
    """
    def repair(m):
        w = m.group(0)
        lat = [c for c in w if "A" <= c <= "Z" or "a" <= c <= "z"]
        if not lat or not CYR.search(w):
            return w
        if any(c not in CONFUSABLE for c in lat):
            return w
        return "".join(CONFUSABLE.get(c, c) for c in w)
    return _WORD.sub(repair, s or "")


def plural(n, one, many):
    """Bulgarian counts: 1 модел, 2 модела. '1 модела' is the tell of a template."""
    return "%d %s" % (n, one if n == 1 else many)


def count_note(items):
    """Item count, and the priced count only when there is one to report.

    /granitogres/ was shipping "10 артикула · 0 с обявена цена" — a counter whose
    only job on that page was to announce that nothing on it had a price.
    """
    n = plural(len(items), "артикул", "артикула")
    priced = sum(1 for f in items if f["price"] > 0)
    return "%s · %d с цена онлайн" % (n, priced) if priced else n


_PRICE_LINE = re.compile(r"^.*\bлв\.?\b.*$", re.M)


def clean_desc(rec):
    """Drop money lines from a description that sits under "По запитване".

    A page that refuses the door's price and then volunteers "дръжка 20 лв."
    two lines below reads as withholding, which is worse than showing nothing.
    """
    d = rec.get("desc") or ""
    # Money lines are now carried by the add-ons list, so they come out of the
    # prose whether or not the door has a price — two formats for the same number
    # on one page is worse than either alone.
    if "лв" in d:
        kept = [ln for ln in d.splitlines() if not _PRICE_LINE.match(ln)]
        d = "\n".join(ln for ln in kept if ln.strip()).strip()
    # 122 entrance doors ship a "description" that is only their size. It is now
    # rendered as the size picker and again in the spec table; a third copy in the
    # prose slot reads as an empty page.
    lines = [ln for ln in d.splitlines() if ln.strip()]
    if lines and all(pricing.parse_size(ln) for ln in lines):
        return ""
    return d


def nice(label):
    """Source labels are inconsistently cased ('серия DUBLIN', 'ПВЦ ВРАТИ ЗА БАНЯ').

    Shouted labels become sentence case. Latin tokens keep the manufacturer's own
    casing (STAR STEEL DOOR, LP INOX) and short all-caps Cyrillic tokens are read
    as acronyms (ПВЦ), so 'ПВЦ ВРАТИ ЗА БАНЯ' lands as 'ПВЦ врати за баня'.
    """
    label = (label or "").strip()
    if not label:
        return label
    words = label.split()
    if label == label.upper() and len(label) > 4:
        fixed = []
        for i, w in enumerate(words):
            core = re.sub(r"[^\w]", "", w, flags=re.UNICODE)
            if not CYR.search(core):
                fixed.append(w)                       # latin / numeric: leave alone
            elif len(core) <= 3 and i == 0:
                fixed.append(w)                       # leading acronym
            elif i == 0:
                fixed.append(w[0] + w[1:].lower())
            else:
                fixed.append(w.lower())
        words = fixed
    if words and words[0].lower() == "серия":
        words[0] = "Серия"
    return " ".join(words)


def esc(s):
    # fix_script here rather than at each call site: every visible string goes
    # through esc, and it only touches words that already mix both alphabets.
    return (fix_script(s or "").replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


# ------------------------------------------------------------------ data
with io.open(os.path.join(HERE, "data.json"), encoding="utf-8") as f:
    DATA = json.load(f)
with io.open(os.path.join(HERE, "images.json"), encoding="utf-8") as f:
    IMG = json.load(f)
MANIFEST = IMG["images"]
GRID_W, FULL_W = IMG["grid_w"], IMG["full_w"]

# Her edits from the admin panel. Uploaded photos land in the manifest like any
# catalogue photo, so every function below treats them the same way.
import admin_sync
assert admin_sync.SIZES == (GRID_W, FULL_W), "admin photos must encode at the catalogue widths"
ADMIN = admin_sync.load()
MANIFEST.update(ADMIN["images"])
# Keep products available when the owner removes their last photograph.
NO_PHOTO = "/assets/no-photo.svg"
MANIFEST[NO_PHOTO] = {"key": "no-photo", "w": 600, "h": 600, "sizes": [600],
                      "urls": {600: NO_PHOTO, 1200: NO_PHOTO}}
ADMIN_CFG = admin_sync.config()


def _setting(key, default, ok=None):
    v = (ADMIN["settings"].get(key) or "").strip()
    return v if v and (ok is None or re.match(ok, v)) else default


# A setting that fails its pattern keeps the built-in value rather than printing
# a broken phone link on 564 pages.
PHONE_H = _setting("phone", PHONE_H, r"^\+?[\d ()-]{6,24}$")
PHONE = "+" + re.sub(r"\D", "", PHONE_H) if PHONE_H.startswith("+") else re.sub(r"\D", "", PHONE_H)
EMAIL = _setting("email", EMAIL, r"^[^@\s<>\"']+@[^@\s<>\"']+\.[a-z]{2,}$")
VIBER = "viber://chat?number=%2B" + PHONE.lstrip("+")
ADDRESS = _setting("address", ADDRESS)
HOURS = esc(_setting("hours", HOURS))     # every template drops HOURS in unescaped
ANNOUNCE = _setting("announcement", "")

STATS = {"pages": 0, "cards": 0, "dropped_no_image": 0, "priced_doors": 0}

# Hand-edited draft price list. See prices.json and pricing.py.
PRICES = pricing.load()


def have(url):
    return url in MANIFEST


def _at(m, width):
    """Where one size of an image lives: /assets/img for the catalogue, Supabase for hers."""
    if "urls" in m:
        return m["urls"][width]
    return "/assets/img/%s-%d.%s" % (m["key"], width, m.get("format", "webp"))


def img_tag(url, alt, sizes="(max-width: 520px) 50vw, 300px", cls="", eager=False):
    """A card image. Never called for a URL that failed to encode."""
    m = MANIFEST[url]
    src = _at(m, GRID_W)
    srcset = "%s %dw" % (src, min(GRID_W, m["w"]))
    if FULL_W in m["sizes"]:
        srcset += ", %s %dw" % (_at(m, FULL_W), min(FULL_W, m["w"]))
    return ('<img src="%s" srcset="%s" sizes="%s" width="%d" height="%d" alt="%s"%s%s>'
            % (src, srcset, sizes, m["w"], m["h"], esc(alt),
               ' class="%s"' % cls if cls else "",
               ' fetchpriority="high"' if eager else ' loading="lazy" decoding="async"'))


def full_src(url):
    m = MANIFEST[url]
    return _at(m, FULL_W if FULL_W in m["sizes"] else GRID_W)


_CONTRAST = {}


def contrast(item):
    """Pixel spread of the item's first encoded image, 0 when there is none.

    Used only to order the four homepage cards. A pale oak swatch has almost no
    spread and reads as a broken image next to three that do not.
    """
    urls = [u for u in item["images"] if have(u)]
    if not urls:
        return 0.0
    key = MANIFEST[urls[0]]["key"]
    if key not in _CONTRAST:
        path = os.path.join(SITE, "assets", "img", os.path.basename(_at(MANIFEST[urls[0]], GRID_W)))
        try:
            from PIL import Image, ImageStat
            with Image.open(path) as im:
                _CONTRAST[key] = ImageStat.Stat(im.convert("L").resize((64, 64))).stddev[0]
        except Exception:
            _CONTRAST[key] = 0.0
    return _CONTRAST[key]


# ------------------------------------------------------------------ admin edits
# Every product the panel can edit, captured BEFORE her edits apply, so the panel
# shows the catalogue value next to hers and can still find a product she hid.
CATALOGUE = []
BADGES = {"new": "Ново", "sale": "Промоция", "hit": "Топ продукт"}


def set_size_prices(rec, rows):
    """Apply her complete size list. Zero is a quote; None keeps the supplier list."""
    if rows is None:
        return
    if not isinstance(rows, list) or len(rows) > 30:
        raise ValueError("invalid size prices for " + rec["name"])
    seen, opts = set(), []
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("invalid size price for " + rec["name"])
        size, amount = row.get("size"), row.get("price")
        if (not isinstance(size, str) or not 1 <= len(size) <= 80 or size != size.strip()
                or any(ord(c) < 32 for c in size) or size.lower() in seen
                or isinstance(amount, bool) or not isinstance(amount, (int, float))
                or not math.isfinite(amount) or not 0 <= amount < 1000000 or round(amount, 2) != amount):
            raise ValueError("invalid size price for " + rec["name"])
        seen.add(size.lower())
        opts.append({"size": size, "note": "", "price": amount * BGN_PER_EUR})
    rec["custom_sizes"] = True
    rec["sizes"] = [s["size"] for s in opts]
    rec["size_opts"] = opts
    rec["specs"] = [s for s in rec["specs"] if not s[0].strip().lower().startswith(("размер", "ширина", "височина"))]
    if opts:
        rec["specs"].append(["Размери", ", ".join(rec["sizes"])])
        anchor = min(opts, key=lambda s: s["price"])
        rec["price"], rec["base_size"] = anchor["price"], anchor["size"]
        for s in opts:
            s["delta"] = s["price"] - anchor["price"]
    else:
        rec["base_size"] = ""
    if opts:
        rec["confirmed"] = True
        rec.pop("draft_price", None)


def apply_override(rec, key):
    """Her price, strike-through price, badge and hide switch, laid over one product.

    A price she typed is a confirmed price, so the "draft" disclaimer comes off it.
    0 means she wants "По запитване" there instead of a number.
    """
    rec["key"] = key
    rec["catalogue_price"] = rec["price"]
    rec["catalogue_sizes"] = [dict(s) for s in rec.get("size_opts") or []]
    rec["catalogue_images"] = rec["images"][:]
    o = ADMIN["overrides"].get(key)
    if not o:
        return rec
    if o.get("hidden"):
        rec["hidden"] = True
    mine = [u for u in o.get("images") or [] if have(u)]
    if mine:
        rec["images"] = mine
    else:
        excluded = set(o.get("excluded_images") or [])
        rec["images"] = [u for u in rec["images"] if u not in excluded] or [NO_PHOTO]
    if o.get("price") is not None:
        # Her prices are euro. Converted unrounded, so money() prints her euro back
        # exactly; the lev figure is the one that gets rounded, as the law intends.
        new = float(o["price"]) * BGN_PER_EUR
        # The size picker prices every option as base + surcharge, so the ladder
        # moves with her base price instead of keeping the old absolute numbers.
        for s in rec.get("size_opts") or []:
            s["price"] = new + s["delta"]
        rec["price"] = new
        rec["confirmed"] = True
        rec.pop("draft_price", None)
    set_size_prices(rec, o.get("size_prices"))
    if o.get("old_price") and (rec.get("custom_sizes") or (rec["price"] > 0 and float(o["old_price"]) * BGN_PER_EUR > rec["price"])):
        rec["old_price"] = float(o["old_price"]) * BGN_PER_EUR
    if o.get("badge") in BADGES:
        rec["badge"] = o["badge"]
    return rec


def admin_rec(a, kind):
    """A product she added, in the same shape as a scraped one. None if it has no photo."""
    imgs = [u for u in a.get("images") or [] if have(u)]
    if not imgs:
        return None
    sizes = [s.strip() for s in a.get("sizes") or [] if s and s.strip()]
    rec = {
        "kind": kind, "admin": True,
        "id": "n" + a["id"].replace("-", "")[:10],
        "name": " ".join((a.get("name") or "").split()),
        "images": imgs, "desc": a.get("description") or "",
        "specs": ([["Размери", ", ".join(sizes)]] if sizes else []),
        "sizes": sizes, "size_opts": [], "size_tags": [], "base_size": "",
        "price": float(a.get("price") or 0) * BGN_PER_EUR, "confirmed": True,     # euro in
        "brand": a.get("brand") or "", "src": "",
    }
    # Older products have labels with one shared price; make those selectable too.
    rows = a.get("size_prices")
    if rows is None and sizes:
        rows = [{"size": s, "price": float(a.get("price") or 0)} for s in sizes]
    set_size_prices(rec, rows)
    if a.get("old_price") and (rec.get("custom_sizes") or (rec["price"] > 0 and float(a["old_price"]) * BGN_PER_EUR > rec["price"])):
        rec["old_price"] = float(a["old_price"]) * BGN_PER_EUR
    if a.get("badge") in BADGES:
        rec["badge"] = a["badge"]
    return rec


# ------------------------------------------------------------------ model
def build_catalogue():
    """Doors: one node per category, products hung on their leaf."""
    labels = {p: nice(l) for p, l in DATA["cat_labels"].items()}
    nodes = {}
    for p in DATA["products"].values():
        imgs = [u for u in p["images"] if have(u)]
        if not imgs:
            STATS["dropped_no_image"] += 1
            continue
        trail = [c for c in p["trail"] if c["path"]]
        rec = {
            "kind": "door",
            "id": p["id"],
            "name": p["name"].strip(),
            "images": imgs,
            "desc": p["desc"],
            "specs": p["specs"],
            "sizes": p["sizes"],
            "price": 0.0,
            "brand": labels.get(trail[0]["path"], "") if trail else "",
            "cat": p["category"],
            "trail": [(c["path"], labels.get(c["path"], nice(c["label"]))) for c in trail],
            "src": p["url"],
        }
        rec["url"] = "/produkt/%s-%s/" % (slug(rec["name"]), rec["id"])
        nodes.setdefault(p["category"], []).append(rec)

    # Doors she added in the admin panel, hung on the category she picked.
    for a in ADMIN["products"]:
        if a["section"] != "door":
            continue
        rec = admin_rec(a, "door")
        path = a.get("category") or ""
        if not rec or path not in labels:
            print("admin: skipped door %r (no photo or unknown category %r)" % (a.get("name"), path))
            continue
        segs = path.split("/")
        rec["cat"] = path
        rec["trail"] = [("/".join(segs[:i]), labels.get("/".join(segs[:i]), nice(segs[i - 1])))
                        for i in range(1, len(segs) + 1)]
        rec["brand"] = a.get("brand") or rec["trail"][0][1]
        rec["url"] = "/produkt/%s-%s/" % (slug(rec["name"]), rec["id"])
        nodes.setdefault(path, []).append(rec)

    # every ancestor path is a page too
    tree = {}
    for path in list(nodes) + list(labels):
        segs = path.split("/")
        for i in range(1, len(segs) + 1):
            sub = "/".join(segs[:i])
            tree.setdefault(sub, {"path": sub,
                                  "label": labels.get(sub, nice(sub.split("/")[-1].replace("-", " "))),
                                  "own": [], "children": set()})
            if i > 1:
                tree["/".join(segs[:i - 1])]["children"].add(sub)
    for path, items in nodes.items():
        tree[path]["own"] = sorted(items, key=lambda r: r["name"])

    def descend(path):
        node = tree[path]
        out = list(node["own"])
        for c in sorted(node["children"]):
            out.extend(descend(c))
        return out

    # Prices and sizes are joined on last, once every door knows its category, so
    # a series price can be resolved from the nearest declared ancestor path.
    for items in nodes.values():
        for rec in items:
            if not rec.get("admin"):
                res = pricing.resolve(rec, PRICES)
                rec["price"] = res["price"]
                rec["base_size"] = res["base_size"]
                rec["size_opts"] = res["sizes"]
                rec["size_tags"] = res["tags"]
                rec["sizes"] = [s["size"] for s in res["sizes"]]
            CATALOGUE.append(rec)
            apply_override(rec, "door:" + rec["id"])
            if rec["price"] > 0:
                STATS["priced_doors"] += 1

    # A hidden door leaves every listing, and its page is not written.
    for path in tree:
        tree[path]["own"] = [r for r in tree[path]["own"] if not r.get("hidden")]
    for path in tree:
        tree[path]["all"] = descend(path)
        tree[path]["url"] = "/vrati/%s/" % "/".join(slug(s) for s in path.split("/"))
    return tree


def build_floors():
    out = []
    for d in DATA["darnox"]:
        imgs = [u for u in d["images"] if have(u)]
        if not imgs:
            STATS["dropped_no_image"] += 1
            continue
        t = d["title"]
        thick = re.search(r"(\d+(?:[.,]\d+)?)\s*(?:mm|мм)", t, re.I)
        ac = re.search(r"\bAC\s?(\d)\b", t, re.I)
        rec = {
            "kind": "floor",
            "id": d["id"],
            "name": t,
            "images": imgs,
            "desc": d["body"],
            "specs": [],
            "sizes": [],
            "price": d["price"],
            "brand": d["vendor"] or "DARNOX",
            "section": d["section"],
            "thick": (thick.group(1).replace(",", ".") + " mm") if thick else "",
            "ac": ("AC" + ac.group(1)) if ac else "",
            "url": "/nastilki/produkt/%s/" % slug(d["handle"]),
            "src": "https://darnox.com/products/%s" % d["handle"],
        }
        specs = []
        if rec["brand"]:
            specs.append(["Марка", rec["brand"]])
        if rec["thick"]:
            specs.append(["Дебелина", rec["thick"]])
        if rec["ac"]:
            specs.append(["Клас на износване", rec["ac"]])
        rec["specs"] = specs
        # 124 of the 171 supplier items publish no price. Rather than leave two
        # thirds of the flooring saying "По запитване", a draft price is derived
        # from the ones that DO publish — never overwriting a real price, and
        # flagged so the same notice that guards the door prices guards these too.
        if rec["price"] <= 0:
            drafted = pricing.floor_price(rec, PRICES)
            if drafted > 0:
                rec["price"] = drafted
                rec["draft_price"] = True
        CATALOGUE.append(rec)
        apply_override(rec, "floor:" + rec["id"])
        if not rec.get("hidden"):
            out.append(rec)

    for a in ADMIN["products"]:
        if a["section"] not in ("nastilki", "granitogres", "parvazi"):
            continue
        rec = admin_rec(a, "floor")
        if not rec:
            print("admin: skipped floor item %r (no photo)" % a.get("name"))
            continue
        thick = re.search(r"(\d+(?:[.,]\d+)?)\s*mm", rec["name"], re.I)
        ac = re.search(r"\bAC\s?(\d)\b", rec["name"], re.I)
        rec.update({
            "section": a["section"], "brand": rec["brand"] or "NG Doors",
            "thick": (thick.group(1).replace(",", ".") + " mm") if thick else "",
            "ac": ("AC" + ac.group(1)) if ac else "",
            "url": "/nastilki/produkt/%s-%s/" % (slug(rec["name"]), rec["id"]),
        })
        rec["specs"] = [["Марка", rec["brand"]]] + rec["specs"]
        out.append(rec)
    return out


TREE = build_catalogue()
FLOORS = build_floors()
if not any(TREE[p]["all"] for p in TREE):
    sys.exit("build: every door is hidden. Refusing to publish a door shop with no doors.")
ROOTS = sorted([p for p in TREE if "/" not in p],
               key=lambda p: -len(TREE[p]["all"]))
ROOTS = [p for p in ROOTS if TREE[p]["all"]]
BRANDS = {}
for f in FLOORS:
    BRANDS.setdefault(f["brand"], []).append(f)
SECTION_OF = {"nastilki": [f for f in FLOORS if f["section"] == "nastilki"],
              "granitogres": [f for f in FLOORS if f["section"] == "granitogres"],
              "parvazi": [f for f in FLOORS if f["section"] == "parvazi"]}
NASTILKI_BRANDS = {}
for f in SECTION_OF["nastilki"]:
    NASTILKI_BRANDS.setdefault(f["brand"], []).append(f)

# Which product names are not unique, so page_title only disambiguates where it must.
TITLE_DUP = {}
for _r in [r for p in TREE for r in TREE[p]["own"]] + FLOORS:
    TITLE_DUP[_r["name"]] = TITLE_DUP.get(_r["name"], 0) + 1

GALLERY_LABEL = {
    "входни-врати": "Входни врати", "интериорни-врати": "Интериорни врати",
    "врати-за-къщи": "Врати за къщи", "двойни-врати": "Двойни врати",
    "входни-остъклени": "Входни остъклени", "двойни-интериорни-врати": "Двойни интериорни врати",
    "обков": "Обков", "врати-за-баня": "Врати за баня", "плъзгащи-врати": "Плъзгащи врати",
}
ALBUMS = []
for key, urls in DATA["gallery"].items():
    ok = [u for u in urls if have(u)]
    if ok:
        ALBUMS.append({"key": key, "label": GALLERY_LABEL.get(key, nice(key.replace("-", " "))),
                       "photos": ok, "url": "/proekti/%s/" % slug(key)})
# Her uploads go to the front of their album, newest first, because a job finished
# last week is the best thing the page can show. An album name she typed that does
# not exist yet becomes a new album.
for ph in ADMIN["photos"]:          # oldest first, each pushed to the front
    label = " ".join(ph["album"].split())
    album = next((a for a in ALBUMS if a["label"].lower() == label.lower()), None)
    if album is None:
        album = {"key": label, "label": label, "photos": [], "url": "/proekti/%s/" % slug(label)}
        ALBUMS.append(album)
    album["photos"].insert(0, ph["url"])
ALBUMS.sort(key=lambda a: -len(a["photos"]))


# ------------------------------------------------------------------ shell
NAV = [("/vrati/", "Врати"), ("/nastilki/", "Настилки"),
       ("/parvazi/", "Первази"),
       ("/proekti/", "Проекти"), ("/kontakti/", "Контакти")]


def shell(path, title, desc, body, cls="", nav_as=None):
    canonical = BASE_URL + path
    here = nav_as or path
    nav = "".join(
        '<a href="%s"%s>%s</a>' % (u, ' aria-current="page"' if here.startswith(u) and u != "/" else "", t)
        for u, t in NAV)
    return """<!doctype html>
<html lang="bg">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>%(title)s</title>
<meta name="description" content="%(desc)s">
<link rel="canonical" href="%(canonical)s">
<meta property="og:type" content="website">
<meta property="og:site_name" content="NG Doors">
<meta property="og:title" content="%(title)s">
<meta property="og:description" content="%(desc)s">
<meta property="og:locale" content="bg_BG">
<meta name="theme-color" content="#fff5e9">
<link rel="preload" href="/assets/fonts/bitter-var-cyrillic.woff2" as="font" type="font/woff2" crossorigin>
<link rel="preload" href="/assets/fonts/ubuntusans-var-cyrillic.woff2" as="font" type="font/woff2" crossorigin>
<link rel="stylesheet" href="/assets/site.css">
<link rel="icon" href="/assets/favicon.svg" type="image/svg+xml">
</head>
<body%(cls)s>
<a class="skip" href="#main">Към съдържанието</a>
%(announce)s<div class="utility">
  <div class="wrap">
    <span class="hours">%(hours)s</span>
    <span class="utility-right">
      <a href="tel:%(phone)s">%(phone_h)s</a>
      <a href="%(viber)s">Viber</a>
      <a href="mailto:%(email)s">%(email)s</a>
    </span>
  </div>
</div>
<header class="masthead">
  <div class="wrap">
    <a class="brand" href="/">NG<span>&nbsp;Doors</span></a>
    <button class="burger" type="button" aria-label="Меню" aria-expanded="false" aria-controls="nav">
      <!-- three separate bars, not one path, so the open state can fold them into an X -->
      <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6">
        <line class="b1" x1="3" y1="6" x2="21" y2="6"/>
        <line class="b2" x1="3" y1="12" x2="21" y2="12"/>
        <line class="b3" x1="3" y1="18" x2="21" y2="18"/>
      </svg>
    </button>
    <nav class="nav" id="nav">%(nav)s
      <a class="btn btn-primary btn-sm nav-cta" href="/kontakti/">Запитване</a>
    </nav>
  </div>
</header>
<main id="main">
%(body)s
</main>
<footer class="footer">
  <div class="wrap">
    <div class="footer-grid">
      <div>
        <a class="brand" href="/">NG<span>&nbsp;Doors</span></a>
        <p class="tagline">Входни и интериорни врати, ламинат, SPC настилки и первази. Шоурум в Божурище, доставка в цялата страна.</p>
      </div>
      <div>
        <h4>Врати</h4>
        <ul>%(foot_doors)s</ul>
      </div>
      <div>
        <h4>Настилки</h4>
        <ul>
          <li><a href="/nastilki/">Ламинат и SPC</a></li>
          <li><a href="/parvazi/">Первази</a></li>
        </ul>
      </div>
      <div>
        <h4>Контакти</h4>
        <ul>
          <li><a href="tel:%(phone)s">%(phone_h)s</a></li>
          <li><a href="%(viber)s">Viber на същия номер</a></li>
          <li><a href="mailto:%(email)s">%(email)s</a></li>
          <li>%(address)s</li>
          <li><a href="/proekti/">Реализирани проекти</a></li>
        </ul>
      </div>
    </div>
    <div class="footer-base">
      <span>&copy; 2026 NG Doors</span>
      <span>%(hours)s</span>
    </div>
  </div>
</footer>
<dialog class="lightbox" id="lightbox" aria-label="Преглед на снимка">
  <div class="lb-stage"><img id="lb-img" alt=""></div>
  <button class="lb-close" type="button" aria-label="Затвори">&times;</button>
  <button class="lb-nav lb-prev" type="button" aria-label="Предишна">&#8249;</button>
  <button class="lb-nav lb-next" type="button" aria-label="Следваща">&#8250;</button>
  <span class="lb-counter" id="lb-counter"></span>
</dialog>
<script src="/assets/site.js" defer></script>
</body>
</html>
""" % {
        "title": esc(title), "desc": esc(desc), "canonical": esc(canonical),
        "body": body,
        "cls": ' class="%s"' % cls if cls else "", "nav": nav,
        "announce": ('<div class="announce"><div class="wrap">%s</div></div>\n' % esc(ANNOUNCE)) if ANNOUNCE else "",
        "phone": PHONE, "phone_h": PHONE_H, "email": EMAIL, "viber": VIBER,
        "address": esc(ADDRESS), "hours": HOURS,
        "foot_doors": "".join('<li><a href="%s">%s</a></li>' % (TREE[p]["url"], esc(TREE[p]["label"]))
                              for p in ROOTS[:5]),
    }


def write(path, html):
    dest = os.path.join(SITE, path.strip("/"), "index.html") if path != "/" \
        else os.path.join(SITE, "index.html")
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    with io.open(dest, "w", encoding="utf-8") as f:
        f.write(html)
    STATS["pages"] += 1


# ------------------------------------------------------------------ pieces
# BGN_PER_EUR is defined at the top: the catalogue build needs it before this point.


def money(bgn):
    """Euro first, lev second.

    Bulgaria adopted the euro on 2026-01-01 and the mandatory dual-display window
    (BGN and EUR together) ran to 2026-08-08. Since 2026-08-09 the euro is the
    primary price and the lev is an optional secondary reference, so a lev-only
    figure is the one that is now out of step. Source prices come from darnox's
    Shopify, whose shop currency reports BGN, so the lev figure is the original
    and the euro is converted at the fixed rate.
    """
    eur = ("%.2f" % (bgn / BGN_PER_EUR)).replace(".", ",")
    lev = ("%.2f" % bgn).replace(".", ",")
    return '<span class="eur">%s €</span> <span class="bgn">(%s лв.)</span>' % (eur, lev)


def page_title(rec):
    """Unique per page. 18 skirting products ship with byte-identical names, and a
    title repeated 18 times is the same defect as a title left empty."""
    bits = [rec["name"]]
    if rec["kind"] == "door" and rec["trail"]:
        bits.append(rec["trail"][-1][1])
    elif rec.get("brand"):
        bits.append(rec["brand"])
    if TITLE_DUP.get(rec["name"], 0) > 1:
        bits.append("№ %s" % rec["id"][-4:])
    bits.append(SITE_NAME)
    return " — ".join(b for b in bits if b)


def meta_desc(rec):
    """Composed from what makes this product different, not from the shared blurb.

    Taking the scraped description verbatim put one identical sentence on 83 pages
    and left 351 of 564 sharing a description with something else — which is the
    defect this whole project exists to fix, wearing a different hat.
    """
    where = rec["trail"][-1][1] if (rec["kind"] == "door" and rec["trail"]) else {
        "nastilki": "Ламинат и SPC настилки", "granitogres": "Гранитогрес",
        "parvazi": "Первази"}.get(rec.get("section"), "Каталог")
    bits = ["%s — %s" % (rec["name"], where)]
    if rec.get("brand") and rec["brand"] != where:
        bits.append(rec["brand"])
    if rec["price"] > 0:
        bits.append("%s € (%s лв.)" % (("%.2f" % (rec["price"] / BGN_PER_EUR)).replace(".", ","),
                                       ("%.2f" % rec["price"]).replace(".", ",")))
    if rec.get("sizes"):
        bits.append("размери: " + ", ".join(rec["sizes"][:3]))
    elif rec.get("specs"):
        bits.append("; ".join("%s: %s" % (k, v) for k, v in rec["specs"][:2]))
    if TITLE_DUP.get(rec["name"], 0) > 1:
        # The supplier lists 18 skirting boards under one identical name with nothing
        # in the feed to tell them apart. The catalogue number is the only real
        # distinguishing fact there is, so the page carries it rather than pretending.
        bits.append("кат. № %s" % rec["id"])
    bits.append("NG Doors, Божурище")
    out = ". ".join(b.strip(" .") for b in bits if b and b.strip())
    return (out[:250] + ".") if not out.endswith(".") else out


def price_html(rec, big=False):
    cls = "price-big" if big else "price"
    if rec["price"] > 0 or (big and rec.get("size_opts")):
        # data-bgn is what the size picker recomputes from. It never parses the
        # rendered string: "1 090,00 лв." is a display format, not a number.
        was = ""
        if rec.get("old_price") and rec["price"] > 0 and rec["old_price"] > rec["price"]:
            eur = ("%.2f" % (rec["old_price"] / BGN_PER_EUR)).replace(".", ",")
            was = ' <s class="was" aria-label="Стара цена">%s €</s>' % eur
        old = ' data-old-bgn="%.6f"' % rec["old_price"] if rec.get("old_price") else ""
        return '<div class="%s%s" data-bgn="%.6f"%s>%s%s</div>' % (
            cls, " ask" if rec["price"] <= 0 else "", rec["price"], old,
            money(rec["price"]) if rec["price"] > 0 else "По запитване", was)
    return '<div class="%s ask">По запитване</div>' % cls


def size_picker(rec):
    """The size pills, as a real radiogroup that repricing hangs off.

    They were inert <span>s. Each option carries its surcharge over the anchor
    price so site.js can reprice without a round trip, and the wall-thickness
    clause the source ships with the size ("зид до 34 см") stays with its option.
    """
    opts = rec.get("size_opts") or []
    if not opts:
        return ""
    out = []
    for i, s in enumerate(opts):
        sel = "true" if s["size"] == rec.get("base_size") else "false"
        note = ' <span class="size-note">%s</span>' % esc(s["note"]) if s["note"] else ""
        out.append('<button class="size-pill" type="button" role="radio" aria-checked="%s"'
                   ' tabindex="%d" data-size="%s" data-delta="%.6f" data-price="%.6f">%s%s</button>'
                   % (sel, 0 if sel == "true" else -1, esc(s["size"]), s["delta"], s["price"],
                      esc(s["size"]), note))
    return ('<div class="sizes-block">'
            '<div class="sizes-label" id="szlab">Размер (ш/в, см)</div>'
            '<div class="sizes" role="radiogroup" aria-labelledby="szlab" data-custom="%s">%s</div>'
            '</div>' % ("true" if rec.get("custom_sizes") else "false", "".join(out)))


def addons_html(rec):
    """Her real add-on prices, as a list instead of a sentence buried in the blurb.

    13 descriptions carry "дръжка 20 лв. и Уширение за каса 10 см – 25 лв." as
    prose. clean_desc strips those lines; this is where the numbers come back.
    """
    if rec.get("kind") != "door" or rec.get("price", 0) <= 0:
        return ""
    rows = "".join('<li><span>%s</span><span class="addon-price">%s</span></li>'
                   % (esc(a["label"]), money(float(a["price"])))
                   for a in PRICES.get("addons", []))
    if not rows:
        return ""
    return ('<div class="addons"><div class="addons-label">Допълнително</div>'
            '<ul>%s</ul></div>' % rows)


def sticky_buy(rec):
    """A phone-width bar that keeps the name and the enquiry button in reach.

    The product column is long once it carries a price, a picker, add-ons and a
    spec table, so on a phone the CTA is several screens above the fold by the
    time anyone has decided. Hidden until the real price scrolls out of view.
    """
    if rec.get("price", 0) <= 0:
        return ""
    return ('<div class="stickybuy" id="stickybuy" data-show="false">'
            '<div class="wrap">'
            '<div class="sb-name">%s</div>'
            '<a class="btn btn-primary" href="mailto:%s?subject=%s">Запитване</a>'
            '</div></div>' % (esc(rec["name"]), EMAIL,
                              esc("Запитване: %s" % rec["name"]).replace(" ", "%20")))


def price_note_html(rec):
    """Says out loud that the figure is a draft, wherever a draft figure appears."""
    if rec.get("price", 0) <= 0 or not PRICES.get("draft") or rec.get("confirmed"):
        return ""
    if rec.get("kind") == "door":
        lead = PRICES.get("note_bg", "")
    elif rec.get("draft_price"):
        # A drafted floor price, next to siblings carrying the supplier's own.
        # Say which kind this is rather than letting the two look alike.
        lead = "Ориентировъчна цена на кв.м, изведена от обявените цени в каталога."
    else:
        return ""      # a real supplier price needs no disclaimer
    return '<p class="price-note">%s <strong>Цените са ориентировъчни и подлежат на потвърждение.</strong></p>' % esc(lead)


def card(rec, kicker=None):
    STATS["cards"] += 1
    k = kicker if kicker is not None else (rec.get("brand") or "")
    badge = ('<span class="badge badge-%s">%s</span>' % (rec["badge"], BADGES[rec["badge"]])
             if rec.get("badge") in BADGES else "")
    return """<a class="card reveal" href="%s">
  <div class="shot">%s%s</div>
  <div class="card-body">
    %s<div class="title">%s</div>
    %s
  </div>
</a>""" % (rec["url"], badge, img_tag(rec["images"][0], rec["name"]),
           '<div class="kicker">%s</div>' % esc(k) if k else "",
           esc(rec["name"]), price_html(rec))


def crumbs(items):
    parts = []
    for i, (url, label) in enumerate(items):
        if i:
            parts.append('<span class="sep">/</span>')
        parts.append('<a href="%s">%s</a>' % (url, esc(label)) if url
                     else '<span class="here">%s</span>' % esc(label))
    return '<nav class="crumbs" aria-label="Пътека">%s</nav>' % "".join(parts)


# One generated room per section top. Keyed by the page path so a caller cannot hand
# the wrong scene to the wrong page. A path with no entry gets no banner, which is why
# every other pagehead() call needed no change.
SCENES = {
    "/vrati/vhodni-vrati/":     ("vhodni",      "Входна врата в коридор на апартамент"),
    "/vrati/interiorni-vrati/": ("interiorni",  "Открехната интериорна врата към стая"),
    "/nastilki/":               ("nastilki",    "Ламиниран под в дневна светлина"),
    "/granitogres/":            ("granitogres", "Гранитогрес на кухненски под"),
    "/parvazi/":                ("parvazi",     "Первази в ъгъла между под и стена"),
    "/vrati/":                  ("proekti",     "Завършена стая с интериорна врата"),
}


def film(name, alt, w, h, cls, eager=False):
    """One scene as a silent looping video, with its own first frame as the poster.

    The poster is cut from the clip rather than reused from the old still, so the
    two are the same pixels and the frame cannot shift the moment playback starts.
    preload is 'none' on a band: the poster paints immediately and not a byte of
    video is fetched until site.js sees the band come into view. The hero is the
    one exception, because it is above the fold on every visit.

    role=img is deliberate. These carry the same meaning the <img alt> carried and
    none of the meaning of a media player: nothing to hear, nothing to seek, no
    controls. A screen reader should read the label and move on.
    """
    return ('<div class="%s"><video class="film" data-film poster="/assets/scenes/%s-poster.webp" '
            'width="%d" height="%d" muted loop playsinline preload="%s"%s '
            'role="img" aria-label="%s">'
            '<source src="/assets/scenes/%s.webm" type="video/webm">'
            '<source src="/assets/scenes/%s.mp4" type="video/mp4">'
            '</video></div>') % (cls, name, w, h,
                                 "auto" if eager else "none",
                                 " autoplay" if eager else "",
                                 esc(alt), name, name)


# Still photographs for the sections that have no film. Generated in the same look
# (LOOK-LOCK.md, "2026-09-29 stills"), and like the films they show a room, never
# a product: the door in each one is a plain generic leaf.
STILLS = {
    "/vrati/aluminievi-vrati/":                ("aluminievi", "Алуминиева остъклена врата към балкон"),
    "/vrati/obkov-i-aksesoari/":               ("obkov", "Черна дръжка на дъбова интериорна врата"),
    "/vrati/vrati-za-servizni-pomeshteniya/":  ("servizni", "Врата към перално помещение"),
    "/vrati/pvts-vrati-za-banya/":             ("banya", "Открехната врата на баня"),
    "/vrati/pozharoustoychivi-vrati/":         ("pojaro", "Метална врата във входа на жилищен блок"),
    "/kontakti/":                              ("kontakti", "Отворена входна врата към светъл коридор"),
}


def photo(name, alt, sizes, cls="", eager=False):
    """One of the generated stills in static/photos, as a responsive img."""
    return ('<img%s src="/assets/photos/%s-1200.webp" srcset="/assets/photos/%s-640.webp 640w, '
            '/assets/photos/%s-1200.webp 1200w" sizes="%s" width="1200" height="800" alt="%s"%s>'
            % (' class="%s"' % cls if cls else "", name, name, name, sizes, esc(alt),
               ' fetchpriority="high"' if eager else ' loading="lazy" decoding="async"'))


def scene_band(path):
    got = SCENES.get(path)
    if got:
        name, alt = got
        return film(name, alt, 1120, 630, "scene reveal")
    got = STILLS.get(path)
    if got:
        return '<div class="scene reveal">%s</div>' % photo(
            got[0], got[1], "(max-width: 1320px) 100vw, 1320px", "still")
    return ""


def pagehead(title, lede="", crumb=None, note="", scene=None):
    return """<section class="pagehead"><div class="wrap">
%s<h1>%s</h1>%s%s%s
</div></section>""" % (
        crumbs(crumb) if crumb else "",
        esc(title),
        '<p class="lede">%s</p>' % esc(lede) if lede else "",
        '<p class="count-note">%s</p>' % esc(note) if note else "",
        scene_band(scene) if scene else "")


ENQUIRY = """<section class="section"><div class="wrap">
  <div class="enquiry">
    <div>
      <h2>Не сте сигурни кой модел е вашият?</h2>
      <p>Обадете се или пишете. Ще подберем вариант по размер, бюджет и стил, а при нужда идваме на място за замерване.</p>
    </div>
    <div class="enquiry-actions">
      <a class="btn btn-light" href="tel:%s">%s</a>
      <a class="btn btn-light" href="%s">Пишете в Viber</a>
      <a class="btn btn-light" href="mailto:%s">Пишете ни</a>
    </div>
  </div>
</div></section>""" % (PHONE, PHONE_H, VIBER, EMAIL)


# ------------------------------------------------------------------ pages
TRUST_SIZES = "(max-width: 760px) 100vw, 430px"


def page_home():
    hero_a = hero_b = None
    for p in ROOTS:
        for r in TREE[p]["all"]:
            if hero_a is None:
                hero_a = r
                break
        if hero_a:
            break
    for f in FLOORS:
        if f["price"] > 0:
            hero_b = f
            break
    hero_b = hero_b or (FLOORS[0] if FLOORS else ALL_DOORS[min(1, len(ALL_DOORS) - 1)])
    floor_face = (SECTION_OF["nastilki"] or FLOORS or ALL_DOORS)[0]

    rail = "".join("""<a class="rail-item" href="%s">
  <div class="shot">%s</div>
  <div class="label">%s</div><div class="count">%s</div>
</a>""" % (TREE[p]["url"], img_tag(TREE[p]["all"][0]["images"][0], TREE[p]["label"],
                                  "150px"), esc(TREE[p]["label"]), plural(len(TREE[p]["all"]), "модел", "модела"))
        for p in ROOTS)
    rail += "".join("""<a class="rail-item" href="%s">
  <div class="shot">%s</div>
  <div class="label">%s</div><div class="count">%s</div>
</a>""" % (url, img_tag(items[0]["images"][0], label, "150px"), esc(label), plural(len(items), "артикул", "артикула"))
        for url, label, items in [
            ("/nastilki/", "Настилки", SECTION_OF["nastilki"]),
            ("/parvazi/", "Первази", SECTION_OF["parvazi"])] if items)

    big = TREE[ROOTS[0]]
    small1 = TREE[ROOTS[1]] if len(ROOTS) > 1 else big
    bento = """<div class="bento">
  <a class="tile tile-lg" href="%s">%s
    <div class="tile-body"><p class="eyebrow">%s</p><h3>%s</h3>
      <p>Стоманени и алуминиеви врати с термопрекъсване, обков и брави от европейски производители.</p>
      <span class="more">Разгледайте</span></div>
  </a>
  <div class="bento-right">
    <a class="tile tile-sm" href="%s">%s
      <div class="tile-body"><p class="eyebrow">%s</p><h3>%s</h3>
        <span class="more">Разгледайте</span></div>
    </a>
    <a class="tile tile-sm" href="/nastilki/">%s
      <div class="tile-body"><p class="eyebrow">%s</p><h3>Ламинат и SPC настилки</h3>
        <span class="more">Разгледайте</span></div>
    </a>
  </div>
</div>""" % (
        big["url"], img_tag(big["all"][0]["images"][0], big["label"], "(max-width: 860px) 100vw, 780px"),
        plural(len(big["all"]), "модел", "модела"), esc(big["label"]),
        small1["url"], img_tag(small1["all"][0]["images"][0], small1["label"], "(max-width: 860px) 100vw, 480px"),
        plural(len(small1["all"]), "модел", "модела"), esc(small1["label"]),
        img_tag(floor_face["images"][0], "Настилки", "(max-width: 860px) 100vw, 480px"),
        plural(len(SECTION_OF["nastilki"]), "артикул", "артикула"))

    # Each of these appears in the scraped category labels or Shopify vendor field —
    # verified, not assembled. Unlabelled it read as orphan text, so it says what it is.
    marks = ["Star Steel Door", "Gradde", "Vario Door", "Classen", "Efapel", "DRE",
             "Floorpan", "Swiss Krono"]
    strip = '<p class="eyebrow strip-label">Марки в шоурума</p><div class="marks">%s</div>' % "".join(
        '<span class="mark">%s</span>' % esc(m) for m in marks)

    # Seed one per brand so the row is not four of the same range, then top up to
    # four. Only 2 of 6 brands publish prices at all, so seeding alone left the
    # four-column panel half empty.
    # Three constraints, each one a defect this row shipped with at some point:
    # only настилки (a panel headed "Настилки" filled up with PVC skirting), one card
    # per title (the same перваз three times), and ordered by how much the swatch
    # actually shows (a near-white oak reads as a failed image load on a white card).
    priced = sorted([f for f in FLOORS if f["price"] > 0 and f["section"] == "nastilki"
                     and any(have(u) for u in f["images"])],
                    key=lambda x: -contrast(x))
    featured, seen_brand, seen_title = [], set(), set()
    for pass_ in (0, 1):
        for f in priced:
            if len(featured) >= 4:
                break
            if f["name"] in seen_title:
                continue
            if pass_ == 0 and f["brand"] in seen_brand:
                continue
            seen_brand.add(f["brand"])
            seen_title.add(f["name"])
            featured.append(f)
    feat_cards = "".join(card(f) for f in featured)
    feat_hide = "" if featured else " hidden"     # every priced floor hidden: drop the panel

    body = """<section class="hero"><div class="wrap">
  <div class="hero-grid">
    <div>
      <p class="eyebrow">NG Doors · Божурище</p>
      <h1>Врати и настилки, които издържат.</h1>
      <p class="lede">%s врати и %s настилки и первази. Замерване, доставка и монтаж в цялата страна.</p>
      <div class="hero-actions">
        <a class="btn btn-primary" href="/vrati/">Разгледайте вратите</a>
        <a class="link-underline" href="/nastilki/">Вижте настилките</a>
      </div>
    </div>
    <div class="hero-art">
      <figure class="tall">%s
        <figcaption class="art-tag">Врати</figcaption></figure>
      <figure class="short">%s<figcaption class="art-tag">Настилки</figcaption></figure>
    </div>
  </div>
</div></section>

<section class="section"><div class="wrap">
  <div class="section-head">
    <div><p class="eyebrow">Разгледайте</p><h2>Какво търсите?</h2></div>
    <a class="link-underline" href="/vrati/">Всички категории</a>
  </div>
  <div class="rail-wrap">
    <button class="rail-btn rail-prev" type="button" aria-label="Назад">&#8249;</button>
    <div class="rail" id="rail">%s</div>
    <button class="rail-btn rail-next" type="button" aria-label="Напред">&#8250;</button>
  </div>
</div></section>

<section class="section" style="padding-top:0"><div class="wrap">%s</div></section>

<section class="brandstrip"><div class="wrap">%s</div></section>

<section class="section"%s><div class="wrap">
  <div class="panel-sage">
    <div class="section-head">
      <div><p class="eyebrow">С обявена цена</p><h2>Настилки с цена онлайн</h2></div>
      <a class="link-underline" href="/nastilki/">Всички настилки</a>
    </div>
    <div class="grid grid-4">%s</div>
  </div>
</div></section>

<section class="section" style="padding-top:0"><div class="wrap">
  <div class="trust">
    <div>%s<h3>Доставка в цялата страна</h3><p>Изпращаме до всеки адрес в България, с уговорен ден за получаване.</p></div>
    <div>%s<h3>Монтаж от наши екипи</h3><p>Заявява се заедно с поръчката. Замерваме на място преди производство.</p></div>
    <div>%s<h3>Шоурум в Божурище</h3><p>Елате и вижте моделите и мострите на живо, преди да решите. %s</p></div>
  </div>
</div></section>
%s""" % (
        plural(len(ALL_DOORS), "модел", "модела"),
        plural(len(FLOORS), "артикул", "артикула"),
        film("hero", "Коридор с интериорна врата и ламиниран под", 834, 1112,
             "hero-tall", eager=True),
        img_tag(hero_b["images"][0], hero_b["name"], "(max-width: 900px) 40vw, 300px", eager=True),
        rail, bento, strip, feat_hide, feat_cards,
        photo("dostavka", "Нови врати в защитна опаковка, готови за монтаж", TRUST_SIZES, "trust-img"),
        photo("montazh", "Нова каса с нивелир, поставена в отвор на стена", TRUST_SIZES, "trust-img"),
        photo("mostri", "Мостри на ламинат и фурнир върху маса", TRUST_SIZES, "trust-img"),
        HOURS, ENQUIRY)

    write("/", shell("/", "NG Doors — входни и интериорни врати, ламинат и SPC настилки",
                     "Входни и интериорни врати, алуминиеви врати, ламинат, SPC настилки и первази. "
                     "Шоурум в Божурище, доставка и монтаж в цялата страна.", body))


def page_doors_index():
    tiles = "".join("""<a class="card card-flat" href="%s">
  <div class="shot">%s</div>
  <div class="card-body"><div class="title">%s</div><div class="kicker">%s</div></div>
</a>""" % (TREE[p]["url"], img_tag(TREE[p]["all"][0]["images"][0], TREE[p]["label"],
                                  "(max-width: 520px) 50vw, 300px"),
           esc(TREE[p]["label"]), plural(len(TREE[p]["all"]), "модел", "модела")) for p in ROOTS)
    body = pagehead("Врати",
                    "Входни, интериорни, алуминиеви и пожароустойчиви врати. "
                    "Всеки модел е с реални размери и обков от производителя.",
                    [("/", "Начало"), (None, "Врати")],
                    "%s в %s" % (plural(len(ALL_DOORS), "модел", "модела"), plural(len(ROOTS), "категория", "категории")),
                    scene="/vrati/") + \
        '<section class="section" style="padding-top:0"><div class="wrap"><div class="grid">%s</div></div></section>%s' % (tiles, ENQUIRY)
    write("/vrati/", shell("/vrati/", "Врати — NG Doors",
                           "Входни, интериорни, алуминиеви и пожароустойчиви врати — %s." % plural(len(ALL_DOORS), "модел", "модела"),
                           body))


def page_category(path):
    node = TREE[path]
    if not node["all"]:
        return
    trail = [("/", "Начало"), ("/vrati/", "Врати")]
    segs = path.split("/")
    for i in range(1, len(segs)):
        anc = "/".join(segs[:i])
        if anc in TREE and TREE[anc]["all"]:
            trail.append((TREE[anc]["url"], TREE[anc]["label"]))
    trail.append((None, node["label"]))

    # children is a set, so a pure count key leaves ties in hash order and the
    # build stops being reproducible; the path breaks the tie.
    kids = [c for c in sorted(node["children"], key=lambda c: (-len(TREE[c]["all"]), c))
            if TREE[c]["all"]]

    if kids:
        # A parent lists its series, never every descendant: 'Входни врати' held 165
        # cards on one 23000px page, which is a dump, not a category.
        tiles = "".join("""<a class="card card-flat" href="%s">
  <div class="shot">%s</div>
  <div class="card-body"><div class="title">%s</div><div class="kicker">%s</div></div>
</a>""" % (TREE[c]["url"], img_tag(TREE[c]["all"][0]["images"][0], TREE[c]["label"]),
           esc(TREE[c]["label"]), plural(len(TREE[c]["all"]), "модел", "модела")) for c in kids)
        own = ""
        if node["own"]:
            own = ('<h2 style="margin:44px 0 22px;font-size:1.3rem">Още от %s</h2>'
                   '<div class="grid">%s</div>') % (
                esc(node["label"]), "".join(card(r, kicker="") for r in node["own"]))
        body = pagehead(node["label"], "", trail,
                        "%s в %s" % (plural(len(node["all"]), "модел", "модела"), plural(len(kids), "серия", "серии")),
                        scene=node["url"]) + \
            '<section class="section" style="padding-top:0"><div class="wrap"><div class="grid">%s</div>%s</div></section>%s' % (
                tiles, own, ENQUIRY)
    else:
        items = node["own"]
        # the parent name is already the page title and the breadcrumb; repeating it
        # on all 16 cards was noise
        grid = "".join(card(r, kicker="") for r in items)
        body = pagehead(node["label"], "", trail, plural(len(items), "модел", "модела"),
                        scene=node["url"]) + \
            '<section class="section" style="padding-top:0"><div class="wrap"><div class="grid">%s</div></div></section>%s' % (grid, ENQUIRY)

    # 'Серия Nature' exists under two different parents; the label alone is not a
    # unique page name, so the parent qualifies it.
    parent = trail[-2][1] if len(trail) > 2 else ""
    full = "%s — %s" % (node["label"], parent) if parent and parent != node["label"] else node["label"]
    write(node["url"], shell(node["url"], "%s — NG Doors" % full,
                             "%s — %s от NG Doors, Божурище." % (full, plural(len(node["all"]), "модел", "модела")),
                             body))


def page_product(rec):
    main = rec["images"][0]
    photo = MANIFEST[main]
    gallery_class = "gallery-main"
    if rec["kind"] == "door" and photo["w"] > photo["h"]:
        gallery_class += " gallery-wide"
    thumbs = ""
    if len(rec["images"]) > 1:
        thumbs = '<div class="thumbs">%s</div>' % "".join(
            '<button class="thumb" type="button" data-full="%s" data-i="%d"%s>%s</button>'
            % (full_src(u), i, ' aria-current="true"' if i == 0 else "",
               img_tag(u, "%s — снимка %d" % (rec["name"], i + 1), "80px"))
            for i, u in enumerate(rec["images"]))

    # Values the size parser rejected are still facts about the door — a fire
    # class or a wood decor — so they move into the spec table rather than being
    # dropped, or shown as a size the customer can pick.
    specs = list(rec["specs"])
    tags = [t for t in (rec.get("size_tags") or [])]
    if tags:
        specs = specs + [["Други характеристики", ", ".join(tags)]]
    spec = ""
    if specs:
        spec = '<table class="spec"><tbody>%s</tbody></table>' % "".join(
            "<tr><th>%s</th><td>%s</td></tr>" % (esc(k), esc(v)) for k, v in specs)
    sizes = size_picker(rec)

    if rec["kind"] == "door":
        trail = [("/", "Начало"), ("/vrati/", "Врати")]
        for p, l in rec["trail"]:
            if p in TREE and TREE[p]["all"]:
                trail.append((TREE[p]["url"], TREE[p]["label"]))
        trail.append((None, rec["name"]))
        section_url = "/vrati/"
    else:
        sec = {"nastilki": ("/nastilki/", "Настилки"),
               "granitogres": ("/granitogres/", "Гранитогрес"),
               "parvazi": ("/parvazi/", "Первази")}[rec["section"]]
        trail = [("/", "Начало"), sec, (None, rec["name"])]
        section_url = sec[0]

    lb = json.dumps([full_src(u) for u in rec["images"]], ensure_ascii=False)
    subject = "Запитване: %s" % rec["name"]
    body = """<section class="wrap" style="padding-top:34px">
%s
<div class="product">
  <div>
    <button class="%s" type="button" id="pmain" data-gallery='%s' aria-label="Уголеми снимката">%s</button>
    %s
  </div>
  <div>
    %s
    <h1>%s</h1>
    %s
    %s
    %s
    %s
    %s
    %s
    <div class="product-cta">
      <a class="btn btn-primary" href="mailto:%s?subject=%s">Направете запитване</a>
      <a class="btn btn-ghost" href="tel:%s">%s</a>
      <a class="btn btn-ghost" href="%s">Viber</a>
    </div>
    <p class="source-note">%s</p>
  </div>
</div>
</section>
<section class="section"><div class="wrap"><a class="link-underline" href="%s">&#8249; Обратно към категорията</a></div></section>
%s
""" % (crumbs(trail), gallery_class, esc(lb),
       img_tag(main, rec["name"], "(max-width: 860px) 100vw, 620px", eager=True), thumbs,
       ('<span class="badge badge-%s">%s</span>' % (rec["badge"], BADGES[rec["badge"]])
        if rec.get("badge") in BADGES else "") +
       ('<p class="eyebrow">%s</p>' % esc(rec["brand"]) if rec["brand"] else ""),
       esc(rec["name"]), price_html(rec, big=True), price_note_html(rec),
       '<div class="desc">%s</div>' % esc(clean_desc(rec)) if clean_desc(rec) else "",
       sizes, addons_html(rec), spec,
       EMAIL, esc(subject).replace(" ", "%20"), PHONE, PHONE_H, VIBER,
       ("Наличността и срокът се потвърждават при запитване." if rec.get("admin") else
        "Каталожна информация от %s. Наличността и срокът се потвърждават при запитване."
        % ("ngdoors.bg" if rec["kind"] == "door" else "darnox.com")),
       trail[-2][0] or section_url, sticky_buy(rec))
    # Every floor item lives under /nastilki/produkt/, so the URL alone would light
    # "Настилки" on a skirting board; the menu follows the section instead.
    write(rec["url"], shell(rec["url"], page_title(rec), meta_desc(rec), body, nav_as=section_url))


# The full darnox catalog puts 468 items on /parvazi/ and only 54 are skirting
# boards; the rest are corners, caps and floor strips. Group by the title's first word.
PARVAZ_KINDS = [("Первази", ("пвц", "перваз")),
                ("Ъгли, тапи и снадки", ("вътрешен", "външен", "тапа", "снадка")),
                ("Лайсни за под", ("алуминиева", "алуминиево", "преходна"))]


def parvaz_kind(f):
    first = f["name"].split()[0].lower() if f["name"] else ""
    for i, (label, words) in enumerate(PARVAZ_KINDS):
        if first in words:
            return i, label
    return len(PARVAZ_KINDS), "Други"


def floor_section(path, title, lede, items, brands=None):
    chips = ""
    kinds = []
    if path == "/parvazi/":
        items = sorted(items, key=lambda f: parvaz_kind(f)[0])  # stable: keeps feed order inside a group
        kinds = sorted({parvaz_kind(f) for f in items})
    facets = sorted({f["thick"] for f in items if f["thick"]},
                    key=lambda s: float(s.split()[0]))
    acs = sorted({f["ac"] for f in items if f["ac"]})
    # Two rows of pills that look identical but behave differently is the defect:
    # the brand row navigates to another page, the facet row filters in place.
    # Each row is labelled and the link pills carry their own style.
    if facets or acs or kinds:
        chips = ('<div class="facet-row"><span class="facet-label">Филтър</span>'
                 '<div class="chips" id="facets"><button class="chip" type="button" data-f="*" aria-pressed="true">Всички</button>%s%s%s</div></div>') % (
            "".join('<button class="chip" type="button" data-f="k:%d" aria-pressed="false">%s</button>' % (i, esc(k)) for i, k in kinds),
            "".join('<button class="chip" type="button" data-f="t:%s" aria-pressed="false">%s</button>' % (esc(t), esc(t)) for t in facets),
            "".join('<button class="chip" type="button" data-f="a:%s" aria-pressed="false">%s</button>' % (esc(a), esc(a)) for a in acs))
    brand_nav = ""
    if brands:
        brand_nav = ('<div class="facet-row"><span class="facet-label">Марка</span>'
                     '<div class="chips">%s</div></div>') % "".join(
            '<a class="chip chip-link" href="/nastilki/%s/">%s <span class="chip-n">%d</span></a>' % (slug(b), esc(b), len(v))
            for b, v in sorted(brands.items(), key=lambda kv: -len(kv[1])))
    grid = "".join(
        '<div data-t="%s" data-a="%s" data-k="%s">%s</div>' % (
            esc(f["thick"]), esc(f["ac"]), parvaz_kind(f)[0] if kinds else "", card(f))
        for f in items)
    # darnox dropped all granite tiles in Sep 2026: an empty section says so plainly
    # instead of shipping "0 артикула" over a blank grid.
    if not items:
        grid = '<p class="empty-note" style="grid-column:1/-1;margin:1rem 0">В момента няма модели онлайн. Обадете се и ще проверим наличността.</p>'
    body = pagehead(title, lede, [("/", "Начало"), (None, title)],
                    count_note(items) if items else "", scene=path) + \
        '<section class="section" style="padding-top:0"><div class="wrap">%s%s<div class="grid" id="filtergrid">%s</div></div></section>%s' % (
            brand_nav, chips, grid, ENQUIRY)
    write(path, shell(path, "%s — NG Doors" % title, lede or title, body))


def page_gallery_index():
    tiles = "".join("""<a class="card card-flat" href="%s">
  <div class="shot">%s</div>
  <div class="card-body"><div class="title">%s</div><div class="kicker">%d снимки</div></div>
</a>""" % (a["url"], img_tag(a["photos"][0], a["label"], "(max-width: 520px) 50vw, 300px"),
           esc(a["label"]), len(a["photos"])) for a in ALBUMS)
    total = sum(len(a["photos"]) for a in ALBUMS)
    body = pagehead("Реализирани проекти",
                    "Врати и обков, монтирани при клиенти. Снимките са от обекти, не от каталог.",
                    [("/", "Начало"), (None, "Проекти")], "%d снимки в %d албума" % (total, len(ALBUMS))) + \
        '<section class="section" style="padding-top:0"><div class="wrap"><div class="grid">%s</div></div></section>%s' % (tiles, ENQUIRY)
    write("/proekti/", shell("/proekti/", "Реализирани проекти — NG Doors",
                             "Врати и обков, монтирани при клиенти — %d снимки от реални обекти." % total, body))


def page_album(a):
    lb = json.dumps([full_src(u) for u in a["photos"]], ensure_ascii=False)
    photos = "".join(
        '<button class="photo" type="button" data-i="%d">%s</button>'
        % (i, img_tag(u, "%s — обект %d" % (a["label"], i + 1), "(max-width: 520px) 50vw, 280px"))
        for i, u in enumerate(a["photos"]))
    body = pagehead(a["label"], "",
                    [("/", "Начало"), ("/proekti/", "Проекти"), (None, a["label"])],
                    "%d снимки" % len(a["photos"])) + \
        '<section class="section" style="padding-top:0"><div class="wrap"><div class="photos" data-gallery=\'%s\'>%s</div></div></section>%s' % (esc(lb), photos, ENQUIRY)
    write(a["url"], shell(a["url"], "%s — реализирани проекти — NG Doors" % a["label"],
                          "%s — %d снимки от реални обекти." % (a["label"], len(a["photos"])), body))


def page_contact():
    body = pagehead("Контакти", "Заповядайте в шоурума или ни пишете. Отговаряме в рамките на работния ден.",
                    [("/", "Начало"), (None, "Контакти")], scene="/kontakti/") + """
<section class="section" style="padding-top:0"><div class="wrap">
  <div class="contact-grid">
    <div>
      <dl class="contact-list">
        <dt>Телефон</dt><dd><a href="tel:%s">%s</a></dd>
        <dt>Viber</dt><dd><a href="%s">%s</a></dd>
        <dt>Имейл</dt><dd><a href="mailto:%s">%s</a></dd>
        <dt>Адрес</dt><dd>%s</dd>
        <dt>Работно време</dt><dd>%s</dd>
      </dl>
      <!-- No embedded map: the OSM iframe rendered as a 130px tile with its English
           attribution sprawled across the column, and it is the one thing on the page
           that is not self-hosted. A link does the same job. -->
      <a class="btn btn-ghost map-link" target="_blank" rel="noopener"
         href="https://www.google.com/maps/dir/?api=1&amp;destination=%s">Маршрут до шоурума</a>
    </div>
    <div>
      <h2 style="margin-bottom:16px">Запитване</h2>
      <p class="lede" style="margin-bottom:22px">Попълнете и изпратете. Отговаряме в рамките на работния ден, а телефонът остава най-бързият път.</p>
      <form id="enquiry-form"%s>
        <label class="hp" aria-hidden="true">Не попълвайте<input name="website" tabindex="-1" autocomplete="off"></label>
        <label class="field"><span>Име</span><input name="name" required autocomplete="name"></label>
        <label class="field"><span>Имейл</span><input type="email" name="email" required autocomplete="email" maxlength="254"></label>
        <label class="field"><span>Телефон</span><input type="tel" name="phone" required autocomplete="tel" minlength="6" maxlength="32" pattern="[+0-9 .\\(\\)\\-]{6,32}" title="Въведете телефон с цифри, интервали и при нужда +, скоби или тире."></label>
        <label class="field"><span>Какво търсите</span>
          <select name="topic">
            <option>Входна врата</option><option>Интериорна врата</option>
            <option>Алуминиева врата</option><option>Настилка / ламинат</option>
            <option>Первази</option>
            <option>Обков и аксесоари</option><option>Друго</option>
          </select></label>
        <label class="field"><span>Съобщение</span><textarea name="message" placeholder="Размери, модел, срок…"></textarea></label>
        <button class="btn btn-primary" type="submit">Изпратете запитване</button>
        <p class="form-note" id="form-note" role="status" aria-live="polite"></p>
      </form>
    </div>
  </div>
</div></section>""" % (PHONE, PHONE_H, VIBER, PHONE_H, EMAIL, EMAIL, esc(ADDRESS), HOURS,
                        urllib.parse.quote("NG Doors, " + ADDRESS),
                        # Without a backend the form still works: it opens an email.
                        (' data-sb-url="%s" data-sb-key="%s" data-email="%s"'
                         % (esc(ADMIN_CFG["url"]), esc(ADMIN_CFG["key"]), EMAIL)) if ADMIN_CFG
                        else ' data-email="%s"' % EMAIL)
    write("/kontakti/", shell("/kontakti/", "Контакти — NG Doors",
                              "NG Doors, %s. Телефон %s, имейл %s." % (ADDRESS, PHONE_H, EMAIL), body))


# ------------------------------------------------------------------ run
ALL_DOORS = sorted({r["id"]: r for p in ROOTS for r in TREE[p]["all"]}.values(),
                   key=lambda r: r["name"])
ALL_PRODUCTS = ALL_DOORS + FLOORS


def mirror(src, dst):
    """Make dst hold exactly what src holds -- copy in, and delete what is no longer there.

    Both of these directories used to be copied name-by-name and never cleared, so a
    file removed from static/ stayed in the built site forever and shipped. That is how
    six retired font files were still being served from production after the family was
    replaced: the stylesheet had stopped asking for them and the deploy still carried
    them. Copying is not the same as mirroring, and only mirroring is idempotent.
    """
    if not os.path.isdir(src):
        return
    os.makedirs(dst, exist_ok=True)
    keep = set(os.listdir(src))
    for name in sorted(keep):
        shutil.copy(os.path.join(src, name), os.path.join(dst, name))
    for name in sorted(set(os.listdir(dst)) - keep):
        os.remove(os.path.join(dst, name))
        print("  removed stale asset %s/%s" % (os.path.basename(dst), name))


def write_admin_catalogue():
    """Everything the panel needs to list and edit, in one file it fetches on login.

    Prices are the CATALOGUE values, before her edits, so the panel can show both and
    "reset" means going back to exactly this. Categories are the door tree, so a door
    she adds can only land on a page that exists.
    """
    def thumb(r):
        return _at(MANIFEST[r["catalogue_images"][0]], GRID_W)
    items = []
    for r in CATALOGUE:
        if r.get("admin"):
            continue
        where = (r["trail"][-1][1] if r["kind"] == "door" and r["trail"] else
                 {"nastilki": "Настилки", "granitogres": "Гранитогрес",
                  "parvazi": "Первази"}.get(r.get("section"), ""))
        items.append({"key": r["key"], "name": fix_script(r["name"]), "where": fix_script(where),
                      "brand": r.get("brand") or "", "price": r["catalogue_price"],
                      "size_prices": [{"size": s["size"], "price": s["price"] / BGN_PER_EUR}
                                      for s in r.get("catalogue_sizes") or []],
                      "draft": bool(r.get("draft_price") or (r["kind"] == "door" and PRICES.get("draft"))),
                      "thumb": thumb(r), "url": r["url"],
                      "images": [{"id": u, "thumb": _at(MANIFEST[u], GRID_W)}
                                 for u in r["catalogue_images"]]})
    cats = []
    for p in TREE:
        segs = p.split("/")
        chain = ["/".join(segs[:i]) for i in range(1, len(segs) + 1)]
        cats.append({"path": p, "label": " / ".join(TREE[a]["label"] for a in chain)})
    cats.sort(key=lambda c: c["label"])
    os.makedirs(os.path.join(SITE, "admin"), exist_ok=True)
    with io.open(os.path.join(SITE, "admin", "catalogue.json"), "w", encoding="utf-8") as f:
        json.dump({"items": items, "categories": cats, "albums": [a["label"] for a in ALBUMS],
                   "bgn_per_eur": BGN_PER_EUR,
                   "supabase_url": ADMIN_CFG["url"] if ADMIN_CFG else "",
                   "supabase_key": ADMIN_CFG["key"] if ADMIN_CFG else ""},
                  f, ensure_ascii=False, separators=(",", ":"))


def main():
    if os.path.isdir(SITE):
        for entry in os.listdir(SITE):
            # Dotfiles in here are tooling state, not build output. rmtree quietly
            # does nothing to a file, so site/.gitignore always survived -- but
            # site/.vercel is a DIRECTORY, and wiping it unlinked the project, so the
            # next deploy silently created a second one named after the folder.
            if entry == "assets" or entry.startswith("."):
                continue
            shutil.rmtree(os.path.join(SITE, entry), ignore_errors=True)
    os.makedirs(os.path.join(SITE, "assets"), exist_ok=True)

    shutil.copy(os.path.join(STATIC, "site.css"), os.path.join(SITE, "assets", "site.css"))
    shutil.copy(os.path.join(STATIC, "site.js"), os.path.join(SITE, "assets", "site.js"))
    shutil.copy(os.path.join(STATIC, "favicon.svg"), os.path.join(SITE, "assets", "favicon.svg"))
    shutil.copy(os.path.join(STATIC, "no-photo.svg"), os.path.join(SITE, "assets", "no-photo.svg"))
    # Generated room scenes. They carry no product claim, which is the whole reason they
    # exist: the 623 catalogue photos stay real because a price sits next to them.
    mirror(os.path.join(STATIC, "scenes"), os.path.join(SITE, "assets", "scenes"))
    # Vendored in static/fonts/ so the build is self-contained. They used to be
    # copied from a sibling project folder, which made the build depend on a
    # directory that does not exist in this repository.
    mirror(os.path.join(STATIC, "fonts"), os.path.join(SITE, "assets", "fonts"))
    mirror(os.path.join(STATIC, "photos"), os.path.join(SITE, "assets", "photos"))
    # The admin panel. Static files; everything it does goes through Supabase with
    # her login, so the page itself holds nothing secret.
    mirror(os.path.join(STATIC, "admin"), os.path.join(SITE, "admin"))
    write_admin_catalogue()

    page_home()
    page_doors_index()
    for path in TREE:
        page_category(path)
    for rec in ALL_DOORS:
        page_product(rec)

    floor_section("/nastilki/", "Настилки",
                  "Ламинат и SPC настилки от Floorpan, Swiss Krono, MONE и DARNOX. "
                  "Филтрирайте по дебелина и клас на износване.",
                  SECTION_OF["nastilki"], NASTILKI_BRANDS)
    for b, items in NASTILKI_BRANDS.items():
        floor_section("/nastilki/%s/" % slug(b), b,
                      "Настилки %s от NG Doors, Божурище." % b, items)
    floor_section("/parvazi/", "Первази",
                  "PVC первази в цвят на настилката.", SECTION_OF["parvazi"])
    for rec in FLOORS:
        page_product(rec)
    # Supplier items come and go with every darnox pull, so an old link must land
    # somewhere useful. Vercel serves site/404.html with a real 404 status.
    with io.open(os.path.join(SITE, "404.html"), "w", encoding="utf-8") as f:
        f.write(shell("/404.html", "Страницата не е намерена — NG Doors",
                      "Този продукт вече не се предлага.",
                      '<section class="section"><div class="wrap"><h1>Страницата не е намерена</h1>'
                      '<p style="margin:1rem 0 1.5rem">Този модел вероятно вече не се предлага. '
                      'Разгледайте актуалните или ни се обадете.</p><div class="chips">%s</div></div></section>%s' % (
                          "".join('<a class="chip chip-link" href="%s">%s</a>' % (u, t) for u, t in NAV), ENQUIRY)))

    page_gallery_index()
    for a in ALBUMS:
        page_album(a)
    page_contact()

    urls = []
    for root, _dirs, files in os.walk(SITE):
        for fn in files:
            if fn == "index.html":
                rel = os.path.relpath(os.path.join(root, fn), SITE).replace("\\", "/")
                rel = "/" + rel[:-len("index.html")]
                if not rel.startswith("/admin/"):
                    urls.append(rel)
    with io.open(os.path.join(SITE, "sitemap.xml"), "w", encoding="utf-8") as f:
        f.write('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n')
        for u in sorted(urls):
            f.write("<url><loc>%s%s</loc></url>\n" % (BASE_URL, u))
        f.write("</urlset>\n")
    # Cloudflare Pages reads redirects from site/_redirects (vercel.json is ignored there).
    shutil.copy(os.path.join(HERE, "redirects.txt"), os.path.join(SITE, "_redirects"))
    with io.open(os.path.join(SITE, "robots.txt"), "w", encoding="utf-8") as f:
        # Open to search since 2026-08-31: the supplier confirmed their catalogue photos
        # and specs may be republished. Before that this wrote Disallow: / and every page
        # carried a noindex meta. check.py still fails if only one of those two halves is
        # ever thrown again, in either direction.
        f.write("User-agent: *\nAllow: /\nDisallow: /admin/\n\nSitemap: %s/sitemap.xml\n" % BASE_URL)

    print("--- BUILD ---")
    print("pages        : %d" % STATS["pages"])
    print("door models  : %d in %d category pages" % (len(ALL_DOORS), sum(1 for p in TREE if TREE[p]["all"])))
    print("floor items  : %d (priced %d)" % (len(FLOORS), sum(1 for f in FLOORS if f["price"] > 0)))
    print("gallery      : %d photos in %d albums" % (sum(len(a["photos"]) for a in ALBUMS), len(ALBUMS)))
    print("cards        : %d" % STATS["cards"])
    print("dropped (no usable image): %d" % STATS["dropped_no_image"])


if __name__ == "__main__":
    main()
