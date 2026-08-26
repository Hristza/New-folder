# -*- coding: utf-8 -*-
"""Assert the built site is internally sound. Exits 1 on any failure.

Catches the things a screenshot cannot: a link to a page that was never written,
an <img> pointing at a file that failed to encode, a page that lost its title,
a count that drifted from the scrape.

Run:  python check.py
"""
import io
import json
import os
import re
import sys
import urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__))
SITE = os.path.join(HERE, "site")

fails = []
warns = []


def fail(msg):
    fails.append(msg)


def main():
    with io.open(os.path.join(HERE, "data.json"), encoding="utf-8") as f:
        data = json.load(f)
    with io.open(os.path.join(HERE, "images.json"), encoding="utf-8") as f:
        images = json.load(f)

    pages = {}
    for root, _d, files in os.walk(SITE):
        for fn in files:
            if fn == "index.html":
                p = os.path.relpath(os.path.join(root, fn), SITE).replace("\\", "/")
                pages["/" + p[:-len("index.html")]] = os.path.join(root, fn)
    print("pages on disk: %d" % len(pages))
    if len(pages) < 500:
        fail("only %d pages built, expected 500+" % len(pages))

    # ---- source counts still match what the builder claimed
    n_doors = len([p for p in data["products"].values() if any(u in images["images"] for u in p["images"])])
    n_floor = len([d for d in data["darnox"] if any(u in images["images"] for u in d["images"])])
    n_photo = sum(len([u for u in v if u in images["images"]]) for v in data["gallery"].values())
    n_priced = len([d for d in data["darnox"] if d["price"] > 0])
    print("doors %d | floors %d (priced %d) | gallery %d" % (n_doors, n_floor, n_priced, n_photo))
    if len(data["darnox"]) != 171:
        fail("darnox is %d, expected 171 (подложки must be excluded)" % len(data["darnox"]))
    if sum(len(v) for v in data["gallery"].values()) != 357:
        fail("gallery is %d photos, expected 357" % sum(len(v) for v in data["gallery"].values()))
    if len(data["products"]) != 323:
        fail("door catalogue is %d, expected 323" % len(data["products"]))
    if images["failures"]:
        fail("%d images failed to encode: %s" % (len(images["failures"]),
                                                 list(images["failures"])[:3]))

    # ---- every referenced asset and link resolves
    missing_img, missing_link, no_alt, no_title = set(), set(), 0, []
    title_seen, desc_seen = {}, {}
    mixed_script, bad_plural, stock_claim, empty_counter = set(), [], [], []
    LAT, CYRL = re.compile(r"[A-Za-z]"), re.compile(r"[Ѐ-ӿ]")
    product_pages = 0
    for url, path in sorted(pages.items()):
        with io.open(path, encoding="utf-8") as f:
            html = f.read()
        if "/produkt/" in url or "/nastilki/produkt/" in url:
            product_pages += 1

        t = re.search(r"<title>(.*?)</title>", html, re.S)
        if not t or not t.group(1).strip():
            no_title.append(url)
        else:
            title_seen[t.group(1).strip()] = title_seen.get(t.group(1).strip(), 0) + 1
        d = re.search(r'<meta name="description" content="(.*?)"', html, re.S)
        if not d or not d.group(1).strip():
            fail("empty meta description: %s" % url)
        else:
            desc_seen[d.group(1).strip()] = desc_seen.get(d.group(1).strip(), 0) + 1

        text = re.sub(r"<[^>]+>", " ",
                      re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", html, flags=re.S))
        for w in re.findall(r"[A-Za-zЀ-ӿ]{2,}", text):
            if LAT.search(w) and CYRL.search(w):
                mixed_script.add(w)
        if re.search(r"\b1 (модела|артикула|серии|категории)\b", text):
            bad_plural.append(url)
        if "в наличност" in text:
            stock_claim.append(url)
        if re.search(r"· 0 с (цена|обявена)", text):
            empty_counter.append(url)

        for src in re.findall(r'<img[^>]+src="([^"]+)"', html):
            if src.startswith("/") and not os.path.exists(os.path.join(SITE, src.lstrip("/"))):
                missing_img.add(src)
        for src in re.findall(r'srcset="([^"]+)"', html):
            for part in src.split(","):
                u = part.strip().split(" ")[0]
                if u.startswith("/") and not os.path.exists(os.path.join(SITE, u.lstrip("/"))):
                    missing_img.add(u)
        for tag in re.findall(r"<img[^>]*>", html):
            if 'alt="' not in tag:
                no_alt += 1
        for href in re.findall(r'href="(/[^"#?]*)"', html):
            href = urllib.parse.unquote(href)
            if href.endswith((".css", ".js", ".svg", ".xml", ".txt", ".woff2")):
                if not os.path.exists(os.path.join(SITE, href.lstrip("/"))):
                    missing_link.add(href)
            elif href not in pages:
                missing_link.add(href)
        # lightbox payloads must point at real files too
        for blob in re.findall(r"data-gallery='(\[.*?\])'", html, re.S):
            try:
                for u in json.loads(blob.replace("&quot;", '"').replace("&amp;", "&")):
                    if not os.path.exists(os.path.join(SITE, u.lstrip("/"))):
                        missing_img.add(u)
            except ValueError:
                fail("unparsable data-gallery on %s" % url)

    print("product pages: %d" % product_pages)
    if product_pages < 480:
        fail("only %d product pages, expected ~492" % product_pages)
    if missing_img:
        fail("%d image srcs resolve to nothing, e.g. %s" % (len(missing_img), sorted(missing_img)[:3]))
    if missing_link:
        fail("%d internal links resolve to nothing, e.g. %s" % (len(missing_link), sorted(missing_link)[:5]))
    if no_alt:
        fail("%d <img> without alt" % no_alt)
    if no_title:
        fail("%d pages with an empty <title>, e.g. %s" % (len(no_title), no_title[:3]))

    # ---- unique titles and descriptions
    # An empty <title> and a <title> shared by 18 pages are the same defect; the
    # first build shipped 351 of 564 pages sharing a meta description with something
    # else, and nothing here caught it.
    dup_t = sorted([(v, k) for k, v in title_seen.items() if v > 1], reverse=True)
    dup_d = sorted([(v, k) for k, v in desc_seen.items() if v > 1], reverse=True)
    print("unique titles: %d | unique descriptions: %d" % (len(title_seen), len(desc_seen)))
    if dup_t:
        fail("%d pages share a duplicate <title>, worst x%d: %r"
             % (sum(v for v, _ in dup_t), dup_t[0][0], dup_t[0][1][:70]))
    if dup_d:
        fail("%d pages share a duplicate meta description, worst x%d: %r"
             % (sum(v for v, _ in dup_d), dup_d[0][0], dup_d[0][1][:70]))

    # ---- one alphabet per word
    # "Moдел" is Latin M+o welded to Cyrillic дел: invisible on screen, fatal to
    # Ctrl-F and to the mailto: subject the name gets copied into.
    if mixed_script:
        fail("%d mixed Latin/Cyrillic words, e.g. %s"
             % (len(mixed_script), sorted(mixed_script)[:4]))

    # ---- Bulgarian counts agree with their number
    if bad_plural:
        fail("%d pages read '1 <plural>', e.g. %s" % (len(bad_plural), bad_plural[:3]))

    # ---- claims the site cannot support
    if stock_claim:
        fail("%d pages claim 'в наличност' for goods held by the supplier: %s"
             % (len(stock_claim), stock_claim[:3]))
    if empty_counter:
        fail("%d pages advertise '0 с цена': %s" % (len(empty_counter), empty_counter[:3]))

    # ---- the publish switch is coherent across all three places it lives
    robots = io.open(os.path.join(SITE, "robots.txt"), encoding="utf-8").read()
    noindexed = sum(1 for p in pages.values()
                    if 'content="noindex' in io.open(p, encoding="utf-8").read())
    blocked = "Disallow: /" in robots
    print("noindex pages: %d/%d | robots.txt blocks: %s" % (noindexed, len(pages), blocked))
    if noindexed and not blocked:
        fail("pages say noindex but robots.txt does not block — the switch is half-thrown")
    if blocked and noindexed != len(pages):
        fail("robots.txt blocks the site but only %d of %d pages carry noindex"
             % (noindexed, len(pages)))

    # ---- the thing that started this project
    home = io.open(pages["/"], encoding="utf-8").read()
    if re.search(r"<title>\s*</title>", home):
        fail("home has an empty <title>, same defect as the old site")
    if 'name="description" content=""' in home:
        fail("home has an empty meta description, same defect as the old site")

    # ---- copy checks
    for url, path in pages.items():
        body = io.open(path, encoding="utf-8").read()
        for bad in ("&ndash;", "&mdash;", "&nbsp;&nbsp;", "lorem", "TODO", "PLACEHOLDER"):
            if bad in body:
                fail("%s contains %r" % (url, bad))
        if re.search(r"\bВходна врата \d{3}\b", body):
            fail("%s still uses a numbered placeholder name" % url)

    # ---- fonts self-hosted, no CDN
    css = io.open(os.path.join(SITE, "assets", "site.css"), encoding="utf-8").read()
    if "fonts.googleapis" in css or "fonts.gstatic" in css:
        fail("stylesheet links a font CDN")
    for f in ("onest-var-cyrillic.woff2", "manrope-var-cyrillic.woff2"):
        if not os.path.exists(os.path.join(SITE, "assets", "fonts", f)):
            fail("missing self-hosted font %s" % f)
    for page in list(pages.values())[:40]:
        if "fonts.googleapis" in io.open(page, encoding="utf-8").read():
            fail("a page links Google Fonts")
            break

    # ---- prices and the size picker
    # The picker reprices in JS. If its arithmetic or its money format ever drifts
    # from build.py's, the page changes format the moment it is touched, which reads
    # as broken. These two must be checked together, not trusted.
    # Importing build runs it as a module: same catalogue the pages were rendered
    # from, so the checker grades the real records rather than re-deriving them.
    import build
    import pricing
    prices = pricing.load()
    if not prices.get("draft"):
        warns.append("prices.json is no longer marked draft — confirm the numbers are real")

    doors = [r for r in build.ALL_DOORS if r["kind"] == "door"]
    unpriced = [r["name"] for r in doors if r["price"] <= 0]
    picker = [r for r in doors if len(r.get("size_opts") or []) > 1]
    print("doors priced: %d/%d | with a size picker: %d" % (len(doors) - len(unpriced), len(doors), len(picker)))
    if unpriced:
        fail("%d door(s) still have no price, first: %s" % (len(unpriced), unpriced[0]))

    # Read the shipped HTML, not the in-memory records: pricing.parse_size already
    # guarantees the shape of what it returns, so checking its own output proves
    # nothing. What can still break is the template — an unescaped value, a delta
    # that never made it onto the button, a pill emitted outside its radiogroup.
    pill_re = re.compile(r'<button class="size-pill"[^>]*>')
    size_re = re.compile(r'data-size="([^"]*)"')
    delta_re = re.compile(r'data-delta="(-?[\d.]+)"')
    checked = pills = 0
    for rec in picker:
        page = os.path.join(SITE, rec["url"].strip("/"), "index.html")
        if not os.path.exists(page):
            continue
        html = io.open(page, encoding="utf-8").read()
        if 'role="radiogroup"' not in html:
            fail("%s: size pills are not inside a radiogroup" % rec["name"])
            break
        found = pill_re.findall(html)
        if len(found) != len(rec["size_opts"]):
            fail("%s: %d size pills rendered for %d options"
                 % (rec["name"], len(found), len(rec["size_opts"])))
            break
        for tag in found:
            pills += 1
            m, d = size_re.search(tag), delta_re.search(tag)
            if not m or not re.match(r"^\d{2,3}/\d{2,3}$", m.group(1)):
                fail("%s: rendered size %r is not a WIDTH/HEIGHT pair"
                     % (rec["name"], m.group(1) if m else None))
                break
            if not d:
                fail("%s: size pill %s carries no surcharge" % (rec["name"], m.group(1)))
                break
        if html.count('aria-checked="true"') < 1:
            fail("%s: no size is selected on load" % rec["name"])
            break
        checked += 1
    print("size pickers verified in HTML: %d (%d pills)" % (checked, pills))

    # A door whose selected option is not the one the server priced would show one
    # number on load and a different one after the first click on the same size.
    for r in picker:
        anchor_opt = [s_ for s_ in r["size_opts"] if s_["size"] == r["base_size"]]
        if not anchor_opt:
            fail("%s: base_size %r is not among its offered sizes" % (r["name"], r["base_size"]))
            break
        if abs(anchor_opt[0]["delta"]) > 0.001:
            fail("%s: the anchor size carries a non-zero surcharge" % r["name"])
            break
        if any(s_["delta"] < -0.001 for s_ in r["size_opts"]):
            fail("%s: a size is cheaper than the anchor, so the headline price is not the lowest"
                 % r["name"])
            break

    # JS mirror of money(): same rate, same comma decimal, same euro-first order.
    js = io.open(os.path.join(HERE, "static", "site.js"), encoding="utf-8").read()
    if "%s" % build.BGN_PER_EUR not in js:
        fail("site.js does not carry build.py's BGN_PER_EUR (%s)" % build.BGN_PER_EUR)
    for rec in doors[:200]:
        for opt in (rec.get("size_opts") or []):
            want = build.money(opt["price"])
            eur = ("%.2f" % (opt["price"] / build.BGN_PER_EUR)).replace(".", ",")
            lev = ("%.2f" % opt["price"]).replace(".", ",")
            got = '<span class="eur">%s €</span> <span class="bgn">(%s лв.)</span>' % (eur, lev)
            if want != got:
                fail("price format disagrees for %s at %s" % (rec["name"], opt["size"]))
                break

    # ---- draft disclosure
    # A draft price with no notice beside it is a quote. Every priced door page must
    # say so, on the page, not only in the JSON.
    if prices.get("draft"):
        missing = 0
        for rec in doors:
            if rec["price"] <= 0:
                continue
            page = os.path.join(SITE, rec["url"].strip("/"), "index.html")
            if not os.path.exists(page):
                continue
            if "price-note" not in io.open(page, encoding="utf-8").read():
                missing += 1
        if missing:
            fail("%d priced door page(s) carry a draft price with no draft notice" % missing)

    # ---- weight
    total = 0
    for root, _d, files in os.walk(SITE):
        for fn in files:
            total += os.path.getsize(os.path.join(root, fn))
    mb = total / 1048576.0
    print("site weight: %.1f MB" % mb)
    if mb > 70:
        fail("site is %.1f MB, over the 70 MB hard ceiling" % mb)
    elif mb > 60:
        warns.append("site is %.1f MB, over the ~60 MB target" % mb)

    print()
    for w in warns:
        print("WARN  %s" % w)
    if fails:
        for f_ in fails:
            print("FAIL  %s" % f_)
        print("\n%d failure(s)" % len(fails))
        return 1
    print("ALL CHECKS PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
