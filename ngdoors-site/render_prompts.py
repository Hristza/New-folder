# -*- coding: utf-8 -*-
"""Turn the catalogue's own series and model names into render prompts.

One locked look across every prompt, so 42 renders read as one photoshoot rather
than 42 unrelated pictures. The decor words come from the models' real Bulgarian
names — ОЗИГО is a wood, АНТРАЦИТ is a colour — so a series looks like what it
is called instead of being invented.
"""
import io, json, re

LOOK = ("Photorealistic architectural interior photograph, shot straight-on at eye level. "
        "Warm cream plaster wall (#fff5e9), pale wide-plank oak floor, soft diffuse daylight "
        "from the left casting one long gentle shadow. Calm Scandinavian editorial styling, "
        "uncluttered, generous negative space, a single muted sage-green ceramic vase as the "
        "only prop. 35mm, subtle natural grain, warm calm colour grade, high detail on "
        "material texture and edges. No text, no lettering, no logos, no signage, no "
        "watermark, no people.")

FAMILY = {
 "входни-врати": "One closed steel security entrance door filling most of the frame, substantial "
   "frame, flush panel with a long vertical brushed-steel bar handle and a discreet lock cylinder, matte finish",
 "алуминиеви-врати": "One closed aluminium entrance door filling most of the frame, slim profiles, "
   "narrow vertical glazed insert with obscured glass, brushed metal hardware",
 "интериорни-врати": "One closed interior room door filling most of the frame, slim flush casing, "
   "small matte black lever handle, light contemporary joinery",
 "пвц-врати-за-баня": "One closed simple PVC utility door filling most of the frame, plain smooth "
   "surface, small lever handle",
 "врати-за-сервизни-помещения": "One closed plain service-room door filling most of the frame, "
   "utilitarian, minimal hardware",
 "пожароустойчиви-врати": "One closed fire-rated steel door filling most of the frame, plain flat "
   "surface, heavy frame, simple lever handle",
 "обков-и-аксесоари": "A single door handle photographed as a product still life, resting on a "
   "smooth cream plaster surface, three-quarter view, crisp shadow, macro detail on the metal finish",
}

# Decor words that actually appear in the model names.
DECOR = [
 ("антрацит", "anthracite grey"), ("черен", "deep black"), ("черно", "deep black"),
 ("бял", "soft white"), ("бяла", "soft white"), ("сив", "warm grey"), ("сиво", "warm grey"),
 ("златен", "brushed brass"), ("злат", "brushed brass"), ("инокс", "brushed stainless steel"),
 ("орех", "walnut wood"), ("дъб", "natural oak"), ("озиго", "ozigo wood, pale golden-brown grain"),
 ("акация", "acacia wood"), ("мура", "pine wood"), ("ясен", "ash wood"),
 ("палисандър", "rosewood"), ("венге", "wenge, very dark brown wood"), ("седир", "cedar wood"),
 ("бетон", "raw concrete grey"), ("натурал", "natural pale wood"), ("лен", "linen beige"),
 ("атлантис", "cool graphite grey"), ("лара", "smoked oak"), ("сарухан", "warm chestnut"),
 ("арктика", "arctic white"), ("савана", "sand beige"), ("перла", "pearl grey"),
]

def decor_for(samples):
    hits = []
    for s in samples:
        low = s.lower()
        for k, v in DECOR:
            if k in low and v not in hits:
                hits.append(v)
    return hits[:3]

rows = json.load(io.open("render_series.json", encoding="utf-8"))
out = []
for r in rows:
    fam = FAMILY.get(r["top"], FAMILY["интериорни-врати"])
    dec = decor_for(r["samples"])
    finish = ("Finish: %s." % ", ".join(dec)) if dec else "Finish: natural oak veneer."
    out.append({"cat": r["cat"], "label": r["label"], "n": r["n"],
                "prompt": "%s %s %s" % (fam + ".", finish, LOOK)})
io.open("render_prompts.json", "w", encoding="utf-8").write(json.dumps(out, ensure_ascii=False, indent=1))
print("prompts:", len(out))
for o in out[:3]:
    print("\n---", o["label"], "(%d doors)" % o["n"])
    print(o["prompt"][:230] + "...")
