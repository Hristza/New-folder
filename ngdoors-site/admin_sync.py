# -*- coding: utf-8 -*-
"""Pull the admin panel's edits out of Supabase for build.py.

build.py calls load() once. It returns the price overrides, the products and project
photos she added, and the site settings. Her photos are NOT copied into the site: the
panel resizes each one in the browser and uploads a 600px and a 1200px copy, and the
pages link those straight from Supabase storage. Copying them in would grow every
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


PAGE = 500


def publishable(key):
    """True only for keys that are safe on a public page.

    This key is written into the contact form and the panel's catalogue.json, so a
    secret key here hands the whole database to anyone who opens view-source.
    """
    if key.startswith("sb_publishable_"):
        return True
    if key.startswith("sb_secret_"):
        return False
    parts = key.split(".")
    if len(parts) == 3:                      # legacy JWT key: read its role claim
        import base64
        try:
            pad = parts[1] + "=" * (-len(parts[1]) % 4)
            claims = json.loads(base64.urlsafe_b64decode(pad.encode()).decode("utf-8"))
        except Exception:
            return False
        return claims.get("role") == "anon"
    return False


def config():
    """{url, key}, or None ONLY when nothing anywhere says the admin is configured.

    Env vars win over the file and do not need it. A file that exists but will not
    parse, or a url without a key (or the reverse), is a broken configuration, and a
    broken configuration exits: read as "not configured" it would build catalogue-only
    and silently undo every price and hide she saved.
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
    url = (os.environ.get("NGDOORS_SUPABASE_URL") or c.get("supabase_url") or "").strip().rstrip("/")
    key = (os.environ.get("NGDOORS_SUPABASE_KEY") or c.get("supabase_key") or "").strip()
    if bool(url) != bool(key):
        sys.exit("admin: half-configured (url %s, key %s). Refusing to build without her edits."
                 % ("set" if url else "missing", "set" if key else "missing"))
    if url and not url.startswith("https://"):
        sys.exit("admin: supabase url must be https, got %r" % url)
    if key and not publishable(key):
        sys.exit("admin: that Supabase key is a SECRET key. It would be published in every"
                 " page. Use the publishable (sb_publishable_...) or anon key.")
    return {"url": url, "key": key} if url else None


def _get(cfg, path):
    """Every row, page by page. PostgREST caps one response (1000 by default), and a
    capped read would drop her later edits without an error. Callers pass an order
    with a unique tiebreak so pages never overlap or skip."""
    rows, offset = [], 0
    while True:
        sep = "&" if "?" in path else "?"
        req = urllib.request.Request("%s%s%slimit=%d&offset=%d" % (cfg["url"], path, sep, PAGE, offset),
                                     headers={"apikey": cfg["key"], "Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=30) as r:
            page = json.loads(r.read().decode("utf-8"))
        if not isinstance(page, list):
            raise ValueError("expected a list from %s" % path)
        rows += page
        if len(page) < PAGE:
            return rows
        offset += PAGE


def public_url(cfg, path):
    return "%s/storage/v1/object/public/media/%s" % (cfg["url"], urllib.parse.quote(path))


def manifest_row(cfg, photo):
    """One uploaded photo as a manifest entry, keyed by its 1200px URL.

    "urls" is what tells build.img_tag to link Supabase instead of /assets/img.
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
        ov = _get(cfg, "/rest/v1/product_overrides?select=*&order=product_key.asc")
        products = _get(cfg, "/rest/v1/products?select=*&hidden=eq.false&order=created_at.asc,id.asc")
        photos = _get(cfg, "/rest/v1/project_photos?select=*&hidden=eq.false&order=created_at.asc,id.asc")
        settings = _get(cfg, "/rest/v1/settings?select=key,value&order=key.asc")
    except Exception as e:
        sys.exit("admin: cannot reach Supabase (%s). Refusing to build without her edits." % e)

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
