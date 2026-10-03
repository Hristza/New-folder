"""Record an inspected ChatGPT render and encode the two existing website sizes.

Run with --product door:1527 --image <generated PNG>. --index selects another
photo of that product. --init records the remaining source photos without editing.
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
parser.add_argument("--init", action="store_true")
args = parser.parse_args()
data = json.loads((ROOT / "data.json").read_text(encoding="utf-8"))
manifest = json.loads((ROOT / "images.json").read_text(encoding="utf-8"))
products = {"door:" + p["id"]: p for p in data["products"].values()}
products.update({"floor:" + p["id"]: p for p in data["darnox"]})
ledger = json.loads(LEDGER.read_text(encoding="utf-8")) if LEDGER.exists() else {}
for key, product in products.items():
    for url in product["images"]:
        if url not in manifest["images"]:
            continue
        row = ledger.setdefault(url, {"state": "pending", "source": manifest["images"][url], "products": []})
        if key not in row["products"]:
            row["products"].append(key)
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
    assets = ROOT / "site" / "assets" / "img"
    backup = ROOT / "renders" / "originals"
    backup.mkdir(parents=True, exist_ok=True)
    masters = pathlib.Path("C:/Users/Win11/Desktop/Claudes Workspace/Outputs/ngdoors-product-renders")
    masters.mkdir(parents=True, exist_ok=True)
    shutil.copy2(args.image, masters / (key + ".png"))
    with Image.open(args.image) as generated:
        generated = generated.convert("RGB")
        w, h = generated.size
        for width in (manifest["grid_w"], manifest["full_w"]):
            size = min(width, w)
            generated.resize((size, round(h * size / w)), Image.Resampling.LANCZOS).save(
                assets / (key + "-" + str(width) + ".webp"), quality=82, method=6)
    manifest["images"][url] = {"key": key, "w": w, "h": h, "sizes": [manifest["grid_w"], manifest["full_w"]]}
    row.update(state="accepted", generated=manifest["images"][url], master=str(masters / (key + ".png")))
    # Preserve the reference outside the deploy, then remove only proven unused copies.
    used = {r["key"] for r in manifest["images"].values()}
    for old in assets.glob(source_key + "-*.webp"):
        if source_key not in used and "-gpt-" not in old.name:
            shutil.copy2(old, backup / old.name)
            old.unlink()
    (ROOT / "images.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\r\n")
LEDGER.parent.mkdir(parents=True, exist_ok=True)
LEDGER.write_text(json.dumps(ledger, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
done = sum(r["state"] == "accepted" for r in ledger.values())
print(f"ChatGPT photos accepted: {done}/{len(ledger)} source photos")
