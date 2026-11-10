# -*- coding: utf-8 -*-
"""Pull the admin panel's edits out of the ngdoors-api Worker (api/) for build.py.

build.py calls load() once. It returns the price overrides, the products and project
photos she added, and the site settings. Her photos are NOT copied into the site: the
panel resizes each one in the browser and uploads a 600px and a 1200px copy, and the
pages link those straight from the Worker's /media/ (Cloudflare R2). Copying them in would grow every
deploy by every photo she ever uploads, and this site already sits near its ceiling.

Not configured (admin_config.json has no url) -> an empty result, and the build is the
catalogue-only build it always was. Configured but unreachable -> the build FAILS.
Building without her edits would quietly put her old prices back on the live site,
and a failed build leaves the last good deploy standing, so failing is the safe side.

Run alone to see what it would pull:  python admin_sync.py
"""
import hashlib
import io
import json
import os
import sys
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
CONFIG = os.path.join(HERE, "admin_config.json")
SIZES = (600, 1200)
EMPTY = {"overrides": {}, "products": [], "photos": [], "settings": {}, "images": {}}


def config():
    """{url}, or None ONLY when nothing anywhere says the admin is configured.

    The env var wins over the file. A file that exists but will not parse is a broken
    configuration, and a broken configuration exits: read as "not configured" it would
    build catalogue-only and silently undo every price and hide she saved.
    """
    c = {}
    if os.path.exists(CONFIG):
        try:
            with io.open(CONFIG, encoding="utf-8") as f:
                c = json.load(f)
            if not isinstance(c, dict):
                raise ValueError("top level is not an object")
        except (OSError, ValueError) as e:
            sys.exit("admin: %s is unreadable (%s). Fix it or delete it." % (CONFIG, e))
    url = (os.environ.get("NGDOORS_API_URL") or c.get("api_url") or "").strip().rstrip("/")
    if url and not url.startswith("https://"):
        sys.exit("admin: api url must be https, got %r" % url)
    return {"url": url} if url else None


def _get(cfg, path):
    """One read of everything the build needs. The Worker returns it whole, no paging."""
    # Cloudflare answers 403 to the default "Python-urllib/x" user-agent, so name ourselves.
    req = urllib.request.Request(cfg["url"] + path, headers={"Accept": "application/json",
                                                             "User-Agent": "ngdoors-build/1.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.loads(r.read().decode("utf-8"))
    if not isinstance(data, dict) or not all(isinstance(data.get(k), list) for k in ("overrides", "products", "photos", "settings")):
        raise ValueError("unexpected answer from %s" % path)
    return data


def public_url(cfg, path):
    return "%s/media/%s" % (cfg["url"], urllib.parse.quote(path))


def manifest_row(cfg, photo):
    """One uploaded photo as a manifest entry, keyed by its 1200px URL.

    "urls" is what tells build.img_tag to link the API instead of /assets/img.
    """
    small, large = public_url(cfg, photo["s"]), public_url(cfg, photo["l"])
    w, h = int(photo["w"]), int(photo["h"])
    return large, {"key": "a" + hashlib.sha1(large.encode("utf-8")).hexdigest()[:15],
                   "w": w, "h": h, "sizes": list(SIZES),
                   "urls": {SIZES[0]: small, SIZES[1]: large}}


def load():
    cfg = config()
    if not cfg:
        print("admin: not configured, catalogue-only build")
        return json.loads(json.dumps(EMPTY))
    try:
        d = _get(cfg, "/public-data")         # hidden products and photos are already left out
    except Exception as e:
        sys.exit("admin: cannot reach the admin API (%s). Refusing to build without her edits." % e)
    ov, products, photos, settings = d["overrides"], d["products"], d["photos"], d["settings"]

    images = {}
    for pr in products:
        urls = []
        for ph in pr.get("images") or []:
            url, row = manifest_row(cfg, ph)
            images[url] = row
            urls.append(url)
        pr["images"] = urls
    for o in ov:
        urls = []
        for ph in o.get("images") or []:
            url, row = manifest_row(cfg, ph)
            images[url] = row
            urls.append(url)
        o["images"] = urls
    for ph in photos:
        ph["url"], row = manifest_row(cfg, ph["photo"])
        images[ph["url"]] = row
    out = {"overrides": {o["product_key"]: o for o in ov}, "products": products, "photos": photos,
           "settings": {s["key"]: s["value"] for s in settings}, "images": images}
    print("admin: %d overrides, %d products, %d project photos, %d settings"
          % (len(out["overrides"]), len(products), len(photos), len(out["settings"])))
    return out


if __name__ == "__main__":
    d = load()
    print(json.dumps({k: len(v) for k, v in d.items()}))
