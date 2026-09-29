# -*- coding: utf-8 -*-
"""Scrape ngdoors.bg (catalogue + gallery) and darnox.com (Shopify) into data.json.

Cached: every fetched page lands in cache/ so re-runs are free and offline.
Run:  python scrape.py [--refresh] [--darnox-only]
"""
import hashlib
import html
import io
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, "cache")
UA = {"User-Agent": "Mozilla/5.0 (compatible; ngdoors-site-builder/1.0)"}
REFRESH = "--refresh" in sys.argv


def enc_url(u):
    """Percent-encode the Cyrillic path. urllib refuses non-ASCII in the request line."""
    p = urllib.parse.urlsplit(u)
    return urllib.parse.urlunsplit(
        (p.scheme, p.netloc, urllib.parse.quote(p.path), p.query, p.fragment)
    )


def fetch(url, binary=False):
    key = hashlib.sha1(url.encode("utf-8")).hexdigest() + (".bin" if binary else ".html")
    path = os.path.join(CACHE, key)
    if os.path.exists(path) and not REFRESH:
        mode = "rb" if binary else "r"
        with io.open(path, mode, **({} if binary else {"encoding": "utf-8"})) as f:
            return f.read()
    for attempt in range(3):
        try:
            raw = urllib.request.urlopen(
                urllib.request.Request(enc_url(url), headers=UA), timeout=45
            ).read()
            break
        except Exception as e:
            if attempt == 2:
                print("  FETCH FAIL", url, e)
                return None
            time.sleep(2 * (attempt + 1))
    data = raw if binary else raw.decode("utf-8", "replace")
    os.makedirs(CACHE, exist_ok=True)  # a fresh checkout has no cache/ (it is gitignored)
    mode = "wb" if binary else "w"
    with io.open(path, mode, **({} if binary else {"encoding": "utf-8"})) as f:
        f.write(data)
    return data


def strip_tags(s):
    s = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", s, flags=re.S | re.I)
    s = re.sub(r"<br\s*/?>", "\n", s, flags=re.I)
    s = re.sub(r"</(p|div|li|tr|h\d)>", "\n", s, flags=re.I)
    s = re.sub(r"<[^>]+>", " ", s)
    # html.unescape, not a hand-rolled table: the source uses &ndash; &laquo; &deg;
    # and a hand list shipped a literal "&ndash;" into a product description.
    s = html.unescape(s).replace("\xa0", " ")
    s = re.sub(r"[ \t\r\f\v]+", " ", s)
    s = re.sub(r"\n\s*\n+", "\n", s)
    return s.strip()


# --------------------------------------------------------------- ngdoors tree
BASE = "https://ngdoors.bg"

# The nav renders the whole tree on every page, so one fetch gives every category.
def category_tree():
    h = fetch(BASE + "/")
    links = set(re.findall(r'href="(https://ngdoors\.bg/[^"]+)"', h))
    cats = set()
    for l in links:
        path = urllib.parse.unquote(urllib.parse.urlsplit(l).path).strip("/")
        if not path or path.endswith(".htm") or path.endswith(".html"):
            continue
        if path.startswith("категории/"):
            path = path[len("категории/"):]
        segs = path.split("/")
        if segs[0] in ("assets", "libs", "количка", "регистрация", "забравена-парола",
                       "категории", "обща-информация"):
            continue
        cats.add("/".join(segs))
    return sorted(cats)


PRODUCT_RE = re.compile(r'href="(https://ngdoors\.bg/[^"]*?\.htm)"')


def breadcrumbs(html):
    """Every product page ships a JSON-LD BreadcrumbList: exact path + human labels.

    Returns [(url_path, display_name), ...] excluding 'начало' and the product itself.
    """
    m = re.search(r'"BreadcrumbList".*?"itemListElement"\s*:\s*\[(.*?)\]\s*\}', html, re.S)
    if not m:
        return []
    out = []
    for item in re.findall(r'\{\s*"@type"\s*:\s*"ListItem".*?"@id"\s*:\s*"([^"]*)".*?"name"\s*:\s*"([^"]*)"',
                           m.group(1), re.S):
        url, name = item[0].strip(), item[1].strip()
        if name.lower() == "начало":
            continue
        path = urllib.parse.unquote(urllib.parse.urlsplit(url).path).strip("/") if url else ""
        out.append((path, name))
    return out


def scrape_catalogue():
    cats = category_tree()
    print("categories found: %d" % len(cats))
    products = {}
    cat_labels = {}
    urls = set()
    for c in cats:
        h = fetch(BASE + "/" + c)
        if not h:
            continue
        for pu in set(PRODUCT_RE.findall(h)):
            dec = urllib.parse.unquote(pu)
            # a product URL is <category path>/<slug>-<id>.htm
            if "/галерия/" in dec or not re.search(r"-\d+\.htm$", dec):
                continue
            urls.add(dec)

    print("product URLs discovered: %d" % len(urls))
    for i, pu in enumerate(sorted(urls), 1):
        if i % 50 == 0:
            print("  ...%d/%d" % (i, len(urls)))
        ph = fetch(pu)
        if not ph:
            continue
        pid = re.search(r"-(\d+)\.htm$", pu).group(1)
        h1 = re.findall(r"<h1[^>]*>(.*?)</h1>", ph, re.S)
        name = strip_tags(h1[0]) if h1 else ""
        if not name:
            continue

        # Category from the breadcrumb, not from whichever listing page linked it:
        # parent pages carry a 24-item "new products" carousel that misfiles everything.
        crumbs = breadcrumbs(ph)
        trail = [c for c in crumbs if c[0]]
        cat = trail[-1][0] if trail else "/".join(
            urllib.parse.urlsplit(pu).path.strip("/").split("/")[:-1])
        cat = urllib.parse.unquote(cat)
        for path, label in trail:
            cat_labels[path] = label
        imgs = []
        for m in re.findall(r'href="(\S*assets/products/large/[^"\s]+)"', ph):
            u = m.strip()
            imgs.append(u if u.startswith("http") else BASE + "/" + u.lstrip("/"))
        for m in re.findall(r'src="\s*(\S*assets/products/(?:small|large)/[^"\s]+)"', ph):
            u = m.strip()
            u = u if u.startswith("http") else BASE + "/" + u.lstrip("/")
            u = u.replace("/products/small/", "/products/large/")
            imgs.append(u)
        seen = set()
        imgs = [x for x in imgs if not (x in seen or seen.add(x))]

        specs = []
        for row in re.findall(r"<tr[^>]*>(.*?)</tr>", ph, re.S):
            cells = [strip_tags(c) for c in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", row, re.S)]
            cells = [c for c in cells if c]
            if len(cells) >= 2:
                specs.append([cells[0], " ".join(cells[1:])])

        # The description lives in the first tab pane, not after the tab *link*
        # of the same name — that link is only the heading of the tab strip.
        desc = ""
        m = re.search(r'<div class="tab-pane active" id="tab1">(.*?)<div class="tab-pane"', ph, re.S)
        if m:
            body = re.sub(r"<table.*?</table>", " ", m.group(1), flags=re.S)
            desc = strip_tags(body)[:1200]

        sizes = []
        for m in re.findall(r'<div class="col-sm-3 filt_ind[^"]*">(.*?)</div>', ph, re.S):
            t = strip_tags(m)
            if t:
                sizes.append(t)

        products[pid] = {
            "id": pid,
            "name": name,
            "url": pu,
            "category": cat,
            "trail": [{"path": p, "label": l} for p, l in crumbs],
            "images": imgs,
            "specs": specs,
            "sizes": sizes,
            "desc": desc,
        }
    return cats, cat_labels, products


GALLERY_PAGES = ["врати-за-баня", "врати-за-къщи", "входни-врати", "входни-остъклени",
                 "двойни-врати", "двойни-интериорни-врати", "интериорни-врати",
                 "обков", "плъзгащи-врати"]


def scrape_gallery():
    out = {}
    for g in GALLERY_PAGES:
        h = fetch("%s/галерия/%s.html" % (BASE, g))
        if not h:
            out[g] = []
            continue
        imgs = []
        for m in re.findall(r'(?:src|href)="(\S*assets/pages/(?:large|small)/[^"\s]+)"', h):
            u = m.strip()
            u = u if u.startswith("http") else BASE + "/" + u.lstrip("/")
            imgs.append(u.replace("/pages/small/", "/pages/large/"))
        seen = set()
        out[g] = [x for x in imgs if not (x in seen or seen.add(x))]
        print("  gallery %-26s %d" % (g, len(out[g])))
    return out


# ---------------------------------------------------------------- darnox
DARNOX = "https://darnox.com"


def darnox_paged(path, key):
    """Every page of a Shopify list. A single ?limit=250 call silently stopped at 250;
    darnox had 658 products on 2026-09-30. A failed page raises: a short catalogue
    must never be written as if it were the whole one."""
    items = []
    for page in range(1, 200):
        time.sleep(0.5)  # one request at a time, gently: darnox answered 429 to a burst on 2026-09-30
        raw = fetch("%s%s?limit=250&page=%d" % (DARNOX, path, page))
        if raw is None:
            raise RuntimeError("darnox page failed: %s page %d" % (path, page))
        got = json.loads(raw)[key]
        items.extend(got)
        if len(got) < 250:
            return items
    raise RuntimeError("darnox %s: over 200 pages, stopping" % path)


def scrape_darnox():
    data = darnox_paged("/products.json", "products")

    # product_type is blank on many products, so the section a product belongs to
    # comes from its collections, not from the product record.
    cols = darnox_paged("/collections.json", "collections")
    member = {}
    for c in cols:
        if not c.get("products_count"):
            continue
        for p in darnox_paged("/collections/%s/products.json" % c["handle"], "products"):
            member.setdefault(str(p["id"]), []).append(c["handle"])
    print("  products: %d, collections walked: %d" % (len(data), len(cols)))

    def section(pid):
        h = member.get(pid, [])
        if "гранитогрес" in h:
            return "granitogres"
        if "pvc-первази" in h:
            return "parvazi"
        return "nastilki"

    out = []
    for p in data:
        tags = [t.strip() for t in p.get("tags", [])]
        if any("подложк" in t.lower() for t in tags):
            continue
        variants = p.get("variants") or []
        price = 0.0
        for v in variants:
            try:
                price = max(price, float(v.get("price") or 0))
            except (TypeError, ValueError):
                pass
        pid = str(p["id"])
        out.append({
            "id": pid,
            "handle": p["handle"],
            "title": p["title"].strip(),
            "vendor": (p.get("vendor") or "").strip(),
            "type": (p.get("product_type") or "").strip(),
            "tags": tags,
            "collections": member.get(pid, []),
            "section": section(pid),
            "price": round(price, 2),
            "body": strip_tags(p.get("body_html") or "")[:900],
            "images": [i["src"] for i in p.get("images", [])],
        })
    return out


def main():
    if "--darnox-only" in sys.argv:
        # Refresh the supplier catalogue alone; the door catalogue and gallery stay as they are.
        path = os.path.join(HERE, "data.json")
        with io.open(path, encoding="utf-8") as f:
            data = json.load(f)
        print("== darnox ==")
        data["darnox"] = scrape_darnox()
        with io.open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=1)
        sec = {}
        for d in data["darnox"]:
            sec[d["section"]] = sec.get(d["section"], 0) + 1
        print("darnox        : %d (priced %d) sections %s"
              % (len(data["darnox"]), sum(1 for d in data["darnox"] if d["price"] > 0), sec))
        return
    print("== ngdoors catalogue ==")
    cats, cat_labels, products = scrape_catalogue()
    print("== ngdoors gallery ==")
    gallery = scrape_gallery()
    print("== darnox ==")
    darnox = scrape_darnox()

    data = {"categories": cats, "cat_labels": cat_labels, "products": products,
            "gallery": gallery, "darnox": darnox}
    with io.open(os.path.join(HERE, "data.json"), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)

    named = sum(1 for p in products.values() if p["name"])
    with_img = sum(1 for p in products.values() if p["images"])
    with_spec = sum(1 for p in products.values() if p["specs"] or p["sizes"])
    with_desc = sum(1 for p in products.values() if p["desc"])
    cats_used = len({p["category"] for p in products.values()})
    print("\n--- SUMMARY ---")
    print("door products : %d  (named %d, with image %d, with specs/sizes %d, with desc %d)"
          % (len(products), named, with_img, with_spec, with_desc))
    print("leaf categories used: %d   labelled: %d" % (cats_used, len(cat_labels)))
    print("gallery photos: %d" % sum(len(v) for v in gallery.values()))
    sec = {}
    for d in darnox:
        sec[d["section"]] = sec.get(d["section"], 0) + 1
    print("darnox        : %d (priced %d) sections %s"
          % (len(darnox), sum(1 for d in darnox if d["price"] > 0), sec))


if __name__ == "__main__":
    main()
