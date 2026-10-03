"""Record an inspected ChatGPT render and encode the two existing website sizes.

Run with --product door:1527 --image <generated PNG>. --index selects another
photo of that product. --init initializes the queue and applies exact duplicate reuse.
This only converts the generated file to WebP; it does not generate or retouch it.
"""
import argparse
import hashlib
import json
import pathlib
import shutil

from PIL import Image

ROOT = pathlib.Path(__file__).resolve().parent
LEDGER = ROOT / "renders" / "manifest.json"
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--product")
parser.add_argument("--index", type=int, default=0)
parser.add_argument("--image", type=pathlib.Path)
parser.add_argument("--format", choices=("webp", "avif"), default="webp")
parser.add_argument("--quality", type=int, choices=range(1, 96),
                    help="Encoding quality; defaults to WebP 82 or AVIF 55, preserving the native PNG")
parser.add_argument("--init", action="store_true")
args = parser.parse_args()
if args.quality is None:
    args.quality = 55 if args.format == "avif" else 82


def encode(image, path, quality, image_format):
    options = {"speed": 6} if image_format == "avif" else {"method": 6}
    image.save(path, quality=quality, **options)
data = json.loads((ROOT / "data.json").read_text(encoding="utf-8"))
manifest = json.loads((ROOT / "images.json").read_text(encoding="utf-8"))
products = {"door:" + p["id"]: p for p in data["products"].values()}
products.update({"floor:" + p["id"]: p for p in data["darnox"]})
ledger = json.loads(LEDGER.read_text(encoding="utf-8")) if LEDGER.exists() else {}
assets = ROOT / "site" / "assets" / "img"
backup = ROOT / "renders" / "originals"
for key, product in products.items():
    for url in product["images"]:
        if url not in manifest["images"]:
            continue
        row = ledger.setdefault(url, {"state": "pending", "source": manifest["images"][url], "products": []})
        if key not in row["products"]:
            row["products"].append(key)
for row in ledger.values():
    if "reference_sha256" not in row:
        source = row["source"]
        hashes = []
        for width in source["sizes"]:
            path = assets / (source["key"] + "-" + str(width) + "." + source.get("format", "webp"))
            if not path.exists():
                path = backup / path.name
            if not path.exists():
                raise FileNotFoundError("Missing original reference: " + str(path))
            hashes.append((width, hashlib.sha256(path.read_bytes()).hexdigest()))
        row["reference_sha256"] = hashlib.sha256(json.dumps([source["w"], source["h"], hashes]).encode()).hexdigest()
old_keys = set()
if not args.init:
    if not args.image or args.product not in products:
        parser.error("supply a valid --product and the inspected --image")
    url = products[args.product]["images"][args.index]
    row = ledger[url]
    source_key = row["source"]["key"]
    if not source_key.isalnum():
        raise ValueError("unexpected source asset key")
    raw = args.image.read_bytes()
    key = source_key + "-gpt-" + hashlib.sha256(raw).hexdigest()[:12]
    if args.format != "webp":
        key += "-" + args.format
    if args.quality != 82:
        key += "-q" + str(args.quality)
    backup.mkdir(parents=True, exist_ok=True)
    masters = pathlib.Path("C:/Users/Win11/Desktop/Claudes Workspace/Outputs/ngdoors-product-renders")
    masters.mkdir(parents=True, exist_ok=True)
    shutil.copy2(args.image, masters / (key + ".png"))
    with Image.open(args.image) as generated:
        generated = generated.convert("RGB")
        w, h = generated.size
        for width in row["source"]["sizes"]:
            size = min(width, w)
            encode(generated.resize((size, round(h * size / w)), Image.Resampling.LANCZOS),
                   assets / (key + "-" + str(width) + "." + args.format), args.quality, args.format)
    old_keys.add(manifest["images"][url]["key"])
    old_keys.add(source_key)
    manifest["images"][url] = {"key": key, "w": w, "h": h, "sizes": row["source"]["sizes"], "format": args.format}
    row.update(state="accepted", generated=manifest["images"][url], master=str(masters / (key + ".png")), encoding_quality=args.quality)
# Exact same generated PNGs share one website asset. Reusing a render on a
# different reference is allowed only after it was explicitly accepted above.
rendered = {}
for url, row in ledger.items():
    if row["state"] != "accepted":
        continue
    sha = row["generated"]["key"].split("-gpt-", 1)[1]
    canonical = rendered.setdefault(sha, row)
    if row is not canonical:
        old_keys.add(row["generated"]["key"])
        row.update(generated=canonical["generated"], master=canonical["master"])
        manifest["images"][url] = canonical["generated"]
# Exact original-image duplicates (including every available resolution and
# original dimensions) can reuse an accepted render without another generation.
accepted = {row["reference_sha256"]: (url, row) for url, row in ledger.items() if row["state"] == "accepted"}
for url, row in ledger.items():
    match = accepted.get(row["reference_sha256"])
    if row["state"] == "pending" and match:
        original_url, canonical = match
        old_keys.add(row["source"]["key"])
        row.update(state="accepted", generated=canonical["generated"], master=canonical["master"], duplicate_of=original_url)
        manifest["images"][url] = canonical["generated"]
# Keep the catalogue's existing resolution choices. A shared asset uses the
# union required by its source references; full native PNGs remain in masters.
groups = {}
for row in ledger.values():
    if row["state"] == "accepted":
        groups.setdefault(row["generated"]["key"], []).append(row)
for key, rows in groups.items():
    widths = sorted({width for row in rows for width in row["source"]["sizes"]})
    rows[0]["generated"]["sizes"] = widths
    image_format = rows[0]["generated"].get("format", "webp")
    missing = [width for width in widths if not (assets / (key + "-" + str(width) + "." + image_format)).exists()]
    if missing:
        with Image.open(rows[0]["master"]) as generated:
            generated = generated.convert("RGB")
            w, h = generated.size
            for width in missing:
                path = assets / (key + "-" + str(width) + "." + image_format)
                size = min(width, w)
                encode(generated.resize((size, round(h * size / w)), Image.Resampling.LANCZOS),
                       path, rows[0].get("encoding_quality", 82), image_format)
    for row in rows:
        row["generated"] = rows[0]["generated"]
    for path in assets.glob(key + "-*." + image_format):
        if int(path.stem.rsplit("-", 1)[1]) not in widths:
            path.unlink()
for url, row in ledger.items():
    if row["state"] == "accepted":
        manifest["images"][url] = row["generated"]
used = {row["key"] for row in manifest["images"].values()}
backup.mkdir(parents=True, exist_ok=True)
for old_key in old_keys - used:
    for old in assets.glob(old_key + "-*"):
        if old.suffix not in (".webp", ".avif"):
            continue
        if old.stem.rsplit("-", 1)[0] != old_key:
            continue
        if "-gpt-" not in old.name:
            shutil.copy2(old, backup / old.name)
        old.unlink()
for row in ledger.values():
    if row["state"] == "accepted":
        for width in row["generated"]["sizes"]:
            assert (assets / (row["generated"]["key"] + "-" + str(width) + "." + row["generated"].get("format", "webp"))).exists(), "Missing rendered asset"
(ROOT / "images.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\r\n")
LEDGER.parent.mkdir(parents=True, exist_ok=True)
LEDGER.write_text(json.dumps(ledger, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
done = sum(r["state"] == "accepted" for r in ledger.values())
print(f"ChatGPT photos accepted: {done}/{len(ledger)} source photos")
