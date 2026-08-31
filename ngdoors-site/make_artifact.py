# -*- coding: utf-8 -*-
"""Inline one built product page into a single self-contained file.

The Artifact CSP blocks every external host, so the stylesheet, the script, the
six woff2 faces and every image have to travel inside the file as data URIs.
Nothing here is redesigned: this is the shipped page, made portable, so the size
selector can be clicked in a review without deploying anything.
"""
import base64, io, os, re

HERE = os.path.dirname(os.path.abspath(__file__))
SITE = os.path.join(HERE, "site")
SRC = os.path.join(SITE, "produkt", "d-012-lara-antratsit-2890", "index.html")

def datauri(path, mime):
    with open(path, "rb") as fh:
        return "data:%s;base64,%s" % (mime, base64.b64encode(fh.read()).decode())

html = io.open(SRC, encoding="utf-8").read()
css = io.open(os.path.join(SITE, "assets", "site.css"), encoding="utf-8").read()
js = io.open(os.path.join(SITE, "assets", "site.js"), encoding="utf-8").read()

# fonts -> data URIs inside the stylesheet
for name in os.listdir(os.path.join(SITE, "assets", "fonts")):
    # site.css references them relatively ("fonts/bitter-var-cyrillic.woff2"),
    # not from the site root, so match that form.
    css = css.replace("fonts/" + name,
                      datauri(os.path.join(SITE, "assets", "fonts", name), "font/woff2"))

body = re.search(r"<body[^>]*>(.*)</body>", html, re.S).group(1)
body = re.sub(r'<script src="[^"]*"[^>]*></script>', "", body)

# images -> data URIs (src and every srcset candidate)
for key in sorted(set(re.findall(r"/assets/img/([\w-]+\.webp)", body)), key=len, reverse=True):
    p = os.path.join(SITE, "assets", "img", key)
    if os.path.exists(p):
        body = body.replace("/assets/img/" + key, datauri(p, "image/webp"))

# Internal navigation would 404 inside a one-page artifact. Neutralise it, but keep
# mailto:/tel: live — the enquiry button is part of what is being reviewed.
body = re.sub(r'href="/[^"]*"', 'href="#" data-nav-disabled="true"', body)

banner = """<div class="review-strip">
  <strong>Копие за преглед</strong>
  <span>Една продуктова страница от NG Doors, направена самостоятелна, за да може размерът да се пробва. Снимката е оригинална — предстои да бъде заменена с рендер. Цените са чернова.</span>
</div>"""

extra = """
.review-strip { background: var(--sage); color: var(--cream); padding: 12px 24px;
  display: flex; gap: 14px; align-items: baseline; flex-wrap: wrap;
  font-family: 'Ubuntu Sans', system-ui, sans-serif; font-size: 13px; line-height: 1.5; }
.review-strip strong { font-size: 11px; letter-spacing: .14em; text-transform: uppercase; flex: none; }
.review-strip span { color: #e8efe9; max-width: 78ch; }
/* Dead links must not invite a click that goes nowhere. */
[data-nav-disabled] { cursor: default; }
"""

out = ("<title>NG Doors Size Selector</title>\n<style>\n%s\n%s\n</style>\n%s\n%s\n<script>\n%s\n</script>\n"
       % (css, extra, banner, body, js))
dest = os.path.join(HERE, "ngdoors-product-demo.html")
io.open(dest, "w", encoding="utf-8").write(out)
print("wrote %s  (%.0f KB)" % (dest, os.path.getsize(dest) / 1024.0))
