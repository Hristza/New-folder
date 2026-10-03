"""Read-only visual comparisons. Product files and native masters are never changed."""
import json
import pathlib
import sys

from PIL import Image, ImageDraw, ImageFont

jobs = json.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8-sig"))
prefix = pathlib.Path(sys.argv[2])
font = ImageFont.truetype("C:/Windows/Fonts/consola.ttf", 18)
for offset in range(0, len(jobs), 4):
    group = jobs[offset:offset + 4]
    canvas = Image.new("RGB", (1140, 1100), "#f3f0ea")
    draw = ImageDraw.Draw(canvas)
    for i, job in enumerate(group):
        x, y = (i % 2) * 570, (i // 2) * 550
        draw.text((x + 10, y + 5), job["id"], fill="black", font=font)
        for column, (label, image_path) in enumerate((("REFERENCE", job["path"]), ("CHATGPT", job.get("image")))):
            if not image_path:
                continue
            draw.text((x + 10 + column * 280, y + 28), label, fill="black", font=font)
            with Image.open(image_path) as photo:
                preview = photo.convert("RGB")
                preview.thumbnail((260, 490), Image.Resampling.LANCZOS)
                canvas.paste(preview, (x + 10 + column * 280 + (260 - preview.width) // 2,
                                      y + 54 + (490 - preview.height) // 2))
    target = prefix.with_name(prefix.name + "-" + str(offset // 4 + 1) + ".png")
    target.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(target)
    print(target.resolve())
