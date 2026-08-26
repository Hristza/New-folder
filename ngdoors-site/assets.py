# -*- coding: utf-8 -*-
"""Download every source image once, re-encode to WebP.

Writes site/assets/img/<hash>-600.webp (grid) and, only where the source is wide
enough to be worth it, <hash>-1200.webp (lightbox). images.json is the manifest
the builder reads. A source that fails to download or decode is recorded as a
failure and simply never gets a card in the built site — no broken <img> ever
ships.

Weight ledger — the plan set a ~60 MB ceiling and said quality drops rather than
shipping heavy. Measured, in order:
  600+1600 both tiers, q78 ......... 95.7 MB  reverted (over)
  drop duplicate tier, 600+1400 q78  80.1 MB  reverted (over)
  600@78 + 1400@68 ................. 65.1 MB  reverted (over)
  600@78 + 1200@60 ................. 60.7 MB  kept
The cut lands on the lightbox tier because the grid is on screen constantly and
the lightbox is height-constrained anyway.

Run:  python assets.py [--refresh] [--quality N]
"""
import hashlib
import io
import json
import os
import sys
import time
import urllib.parse
import urllib.request

from PIL import Image, ImageFile

ImageFile.LOAD_TRUNCATED_IMAGES = True

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "cache", "img")
OUT = os.path.join(HERE, "site", "assets", "img")
UA = {"User-Agent": "Mozilla/5.0 (compatible; ngdoors-site-builder/1.0)"}
GRID_W = 600      # what a card actually renders at
FULL_W = 1200     # what the lightbox opens
# The lightbox is height-constrained (max-height: 100vh - 92px), so a portrait door
# displays ~530px wide on a 1440 viewport and a landscape photo ~945px. 1200 covers
# both; the grid tier keeps the higher quality because it is on screen constantly.
Q_FULL = 60
# Below this, the source is not meaningfully wider than a card, so the grid file
# *is* the full-size file and a second tier would be a byte-identical duplicate.
# 367 of 1064 sources measured <=600px wide; emitting both doubled them for nothing.
FULL_MIN_SRC = 760
REFRESH = "--refresh" in sys.argv
QUALITY = 78
if "--quality" in sys.argv:
    QUALITY = int(sys.argv[sys.argv.index("--quality") + 1])


def enc_url(u):
    p = urllib.parse.urlsplit(u)
    return urllib.parse.urlunsplit(
        (p.scheme, p.netloc, urllib.parse.quote(p.path), p.query, p.fragment)
    )


def key_of(url):
    return hashlib.sha1(url.encode("utf-8")).hexdigest()[:16]


def download(url):
    k = key_of(url)
    path = os.path.join(RAW, k)
    if os.path.exists(path) and os.path.getsize(path) > 0 and not REFRESH:
        return path
    for attempt in range(3):
        try:
            req = urllib.request.Request(enc_url(url), headers=UA)
            data = urllib.request.urlopen(req, timeout=60).read()
            if len(data) < 100:
                raise ValueError("suspiciously small (%d bytes)" % len(data))
            with open(path, "wb") as f:
                f.write(data)
            return path
        except Exception as e:
            if attempt == 2:
                return ("FAIL", "%s: %s" % (type(e).__name__, e))
            time.sleep(1.5 * (attempt + 1))


def collect(data):
    """Every image URL referenced anywhere, in a stable order."""
    urls = []
    for p in data["products"].values():
        urls.extend(p["images"])
    for album in data["gallery"].values():
        urls.extend(album)
    for d in data["darnox"]:
        urls.extend(d["images"])
    seen = set()
    return [u for u in urls if not (u in seen or seen.add(u))]


def main():
    os.makedirs(RAW, exist_ok=True)
    os.makedirs(OUT, exist_ok=True)
    with io.open(os.path.join(HERE, "data.json"), encoding="utf-8") as f:
        data = json.load(f)

    urls = collect(data)
    print("unique source images: %d" % len(urls))

    manifest, failures = {}, {}
    for i, url in enumerate(urls, 1):
        if i % 100 == 0:
            print("  ...%d/%d  (ok %d, failed %d)" % (i, len(urls), len(manifest), len(failures)))
        k = key_of(url)
        got = download(url)
        if isinstance(got, tuple):
            failures[url] = got[1]
            continue
        try:
            with Image.open(got) as im:
                im.load()
                if im.mode in ("P", "LA", "RGBA"):
                    bg = Image.new("RGB", im.size, (255, 255, 255))
                    conv = im.convert("RGBA")
                    bg.paste(conv, mask=conv.split()[-1])
                    im = bg
                else:
                    im = im.convert("RGB")
                ow, oh = im.size
                widths = [GRID_W] + ([FULL_W] if ow > FULL_MIN_SRC else [])
                for w in widths:
                    dest = os.path.join(OUT, "%s-%d.webp" % (k, w))
                    if os.path.exists(dest) and not REFRESH:
                        continue
                    tw = min(w, ow)
                    th = max(1, round(oh * tw / ow))
                    im.resize((tw, th), Image.LANCZOS).save(
                        dest, "WEBP", quality=(QUALITY if w == GRID_W else Q_FULL),
                        method=5
                    )
            manifest[url] = {"key": k, "w": ow, "h": oh, "sizes": widths}
        except Exception as e:
            failures[url] = "decode: %s: %s" % (type(e).__name__, e)

    with io.open(os.path.join(HERE, "images.json"), "w", encoding="utf-8") as f:
        json.dump({"images": manifest, "failures": failures,
                   "grid_w": GRID_W, "full_w": FULL_W},
                  f, ensure_ascii=False, indent=1)

    total = sum(os.path.getsize(os.path.join(OUT, x)) for x in os.listdir(OUT))
    print("\n--- ASSETS ---")
    print("encoded : %d  (%d webp files)" % (len(manifest), len(os.listdir(OUT))))
    print("failed  : %d" % len(failures))
    for u, why in list(failures.items())[:10]:
        print("   %s  <- %s" % (why, u))
    print("weight  : %.1f MB at quality %d" % (total / 1048576.0, QUALITY))


if __name__ == "__main__":
    main()
