# -*- coding: utf-8 -*-
"""Pack a browsable slice of the built site into one self-contained file.

The real site is 66 MB, almost all of it images, and an Artifact must be under
16 MB with no external requests at all. So: the page shell (header, nav, footer,
lightbox) is identical on all 564 pages and is stored once; only each page's
<main> is stored per route; and every image is re-encoded smaller for preview and
kept once per key, shared by every page that uses it.

Each route is handed to an iframe as a whole document via srcdoc, which is what
lets the site's own site.js run per page exactly as it does in production —
swapping innerHTML instead would leave stale listeners behind on every
navigation and break the lightbox after the first click.

Excluded to stay under the cap: the 9 project albums (357 photos) and the
per-product thumbnail strips. Everything else is browsable.
"""
import base64, io, json, os, re
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
SITE = os.path.join(HERE, "site")
IMGDIR = os.path.join(SITE, "assets", "img")
PREVIEW_W, PREVIEW_Q = 400, 54

def read(p):
    return io.open(p, encoding="utf-8").read()

# ---- which routes to include
routes = []
for root, _d, files in os.walk(SITE):
    if "index.html" not in files:
        continue
    rel = os.path.relpath(root, SITE).replace(os.sep, "/")
    path = "/" if rel == "." else "/" + rel + "/"
    if path.startswith("/proekti/") and path != "/proekti/":
        continue                        # album pages: 357 photos, too heavy
    routes.append(path)
routes.sort()

shell_src = read(os.path.join(SITE, "kontakti", "index.html"))
SHELL_TOP = re.search(r"<body[^>]*>(.*?)<main[^>]*>", shell_src, re.S).group(1)
SHELL_BOT = re.search(r"</main>(.*?)</body>", shell_src, re.S).group(1)
SHELL_BOT = re.sub(r'<script src="[^"]*"[^>]*></script>', "", SHELL_BOT)

IMG_RE = re.compile(r"/assets/img/([\w-]+)\.webp")
pages, keys = {}, {}

for path in routes:
    p = os.path.join(SITE, path.strip("/"), "index.html") if path != "/" else os.path.join(SITE, "index.html")
    html = read(p)
    main = re.search(r"<main[^>]*>(.*?)</main>", html, re.S)
    if not main:
        continue
    body = main.group(1)
    body = re.sub(r'<div class="thumbs">.*?</div>\s*(?=</div>)', "", body, flags=re.S)
    body = re.sub(r'\ssrcset="[^"]*"', "", body)      # one preview encode per image
    body = re.sub(r'\ssizes="[^"]*"', "", body)
    def tok(m):
        k = m.group(1)
        keys.setdefault(k, len(keys))
        return "\x01%d\x01" % keys[k]
    pages[path] = IMG_RE.sub(tok, body)

# ---- encode each used image once, at preview size
uris = [None] * len(keys)
for k, idx in keys.items():
    src = os.path.join(IMGDIR, k + ".webp")
    if not os.path.exists(src):
        uris[idx] = ""
        continue
    with Image.open(src) as im:
        im = im.convert("RGB")
        if im.width > PREVIEW_W:
            im = im.resize((PREVIEW_W, max(1, round(im.height * PREVIEW_W / im.width))), Image.LANCZOS)
        buf = io.BytesIO()
        im.save(buf, "WEBP", quality=PREVIEW_Q, method=6)
    uris[idx] = "data:image/webp;base64," + base64.b64encode(buf.getvalue()).decode()

css = read(os.path.join(SITE, "assets", "site.css"))
for name in os.listdir(os.path.join(SITE, "assets", "fonts")):
    with open(os.path.join(SITE, "assets", "fonts", name), "rb") as fh:
        css = css.replace("fonts/" + name,
                          "data:font/woff2;base64," + base64.b64encode(fh.read()).decode())
js = read(os.path.join(SITE, "assets", "site.js"))

titles = {}
for path in pages:
    p = os.path.join(SITE, path.strip("/"), "index.html") if path != "/" else os.path.join(SITE, "index.html")
    t = re.search(r"<title>(.*?)</title>", read(p), re.S)
    titles[path] = (t.group(1) if t else "NG Doors").replace(" — NG Doors", "")

out = io.open(os.path.join(HERE, "ngdoors-preview.html"), "w", encoding="utf-8")
out.write("<title>NG Doors Catalogue Preview</title>\n")
out.write("""<style>
html,body{margin:0;height:100%;background:#fff5e9}
#strip{background:#587364;color:#fff5e9;font:13px/1.5 system-ui,sans-serif;
  padding:9px 18px;display:flex;gap:12px;align-items:baseline;flex-wrap:wrap}
#strip b{font-size:10.5px;letter-spacing:.14em;text-transform:uppercase;flex:none}
#strip span{color:#dfe8e1}
#strip #where{margin-left:auto;opacity:.85;font-size:12px}
#frame{display:block;width:100%;height:calc(100% - 38px);border:0}
#toast{position:fixed;left:50%;bottom:22px;transform:translate(-50%,140%);
  background:#292929;color:#fff5e9;font:13px system-ui,sans-serif;padding:10px 16px;
  border-radius:999px;transition:transform .3s cubic-bezier(.22,.61,.36,1);z-index:9}
#toast.on{transform:translate(-50%,0)}
@media (prefers-reduced-motion:reduce){#toast{transition:none}}
</style>
""")
out.write('<div id="strip"><b>Копие за преглед</b>'
          '<span>Кликайте из каталога. Размерите се сменят и цената се преизчислява. '
          'Снимките са оригинални и в намалена резолюция за прегледа; предстои да бъдат заменени с рендери. '
          'Цените са чернова.</span><span id="where"></span></div>\n')
out.write('<iframe id="frame" title="NG Doors"></iframe><div id="toast"></div>\n')
out.write("<script>\nvar CSS=" + json.dumps(css) + ";\n")
out.write("var JS=" + json.dumps(js) + ";\n")
out.write("var TOP=" + json.dumps(SHELL_TOP) + ";\nvar BOT=" + json.dumps(SHELL_BOT) + ";\n")
out.write("var IMGS=" + json.dumps(uris) + ";\n")
out.write("var PAGES=" + json.dumps(pages, ensure_ascii=False) + ";\n")
out.write("var TITLES=" + json.dumps(titles, ensure_ascii=False) + ";\n")
out.write(r"""
var frame = document.getElementById('frame'),
    where = document.getElementById('where'),
    toast = document.getElementById('toast'), tid;

function say(msg) {
  toast.textContent = msg; toast.classList.add('on');
  clearTimeout(tid); tid = setTimeout(function () { toast.classList.remove('on'); }, 2600);
}

// Links are intercepted inside the frame and bubbled up, so the parent owns
// routing and a route we did not pack says so instead of showing a blank page.
var HOOK = "document.addEventListener('click',function(e){" +
  "var a=e.target.closest&&e.target.closest('a[href]');if(!a)return;" +
  "var h=a.getAttribute('href');if(!h||h.charAt(0)!=='/')return;" +
  "e.preventDefault();parent.postMessage({ng:h},'*');});";

function go(path) {
  if (!PAGES[path]) { say('Тази страница не е включена в прегледа.'); return; }
  var main = PAGES[path].replace(/\x01(\d+)\x01/g, function (_, i) { return IMGS[+i] || ''; });
  frame.srcdoc = '<!doctype html><html lang="bg"><head><meta charset="utf-8">' +
    '<meta name="viewport" content="width=device-width,initial-scale=1">' +
    '<style>' + CSS + '</style></head><body>' + TOP + '<main>' + main + '</main>' +
    BOT + '<script>' + JS + '<\/script><script>' + HOOK + '<\/script></body></html>';
  where.textContent = TITLES[path] || path;
}

window.addEventListener('message', function (e) {
  if (e.data && e.data.ng) go(e.data.ng);
});
go('/');
""")
out.write("\n</script>\n")
out.close()
sz = os.path.getsize(os.path.join(HERE, "ngdoors-preview.html"))
print("routes packed : %d" % len(pages))
print("images packed : %d at %dpx q%d" % (len(keys), PREVIEW_W, PREVIEW_Q))
print("file size     : %.1f MB" % (sz / 1048576.0))
