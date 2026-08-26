# -*- coding: utf-8 -*-
"""Door prices and door sizes, resolved from prices.json.

`data.json` carries no price for any of the 323 doors — ngdoors.bg is a catalogue,
not a shop, and the prices live in an offline ЦЕНОВА ЛИСТА that two of the scraped
descriptions actually point at. So the numbers come from `prices.json`, which is
hand-edited and never generated.

Sizes are a separate problem. The scraper reads them out of the source site's
`filt_ind` filter blocks, which hold sizes, fire classes, wood decors and skirting
widths in the same field, so `клас А++` and `палисандър` both arrive as "sizes".
Anything that is not a `ШИР/ВИС` pair is rejected here and handed back as a tag for
the spec table instead.

Price of a door = series base_price + (surcharge[chosen size] - surcharge[base_size]).
"""
import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))

# 86/197, 90/200, 94/200 … optionally followed by a wall-thickness clause
# ("зид до 34 см"). The source misspells зид as сид on nine products.
_SIZE = re.compile(r"^\s*(\d{2,3})\s*/\s*(\d{2,4})\s*(?:см)?\s*(.*)$")
_SPLIT = re.compile(r"[,;/]{1}(?=\s*\d{2,3}\s*/)|[,;]|\n")


def load(path=None):
    with open(path or os.path.join(HERE, "prices.json"), encoding="utf-8") as fh:
        return json.load(fh)


def parse_size(raw):
    """'89/199 сид до 21 см' -> ('89/199', 'зид до 21 см'); 'клас А++' -> None."""
    if not raw:
        return None
    txt = str(raw).replace("сид", "зид").strip()
    m = _SIZE.match(txt)
    if not m:
        return None
    w, h = int(m.group(1)), int(m.group(2))
    if w > 1000 or h > 1000:            # '940/2010' is millimetres, not our notation
        w, h = round(w / 10.0), round(h / 10.0)
    if not (50 <= w <= 200 and 150 <= h <= 260):
        return None
    note = re.sub(r"\s+", " ", m.group(3) or "").strip(" .,")
    return ("%d/%d" % (w, h), note)


def raw_sizes(rec):
    """Every size-looking string on a product, plus the values that were not sizes.

    Two sources say the same thing in different shapes: the `sizes` list and the
    `Размер входна врата` spec row, which comma-joins its values on 122 products.
    """
    found, tags = {}, []
    candidates = list(rec.get("sizes") or [])
    for row in rec.get("specs") or []:
        if len(row) >= 2 and "азмер" in (row[0] or ""):
            candidates.extend(_SPLIT.split(row[1] or ""))
    for raw in candidates:
        raw = (raw or "").strip()
        if not raw:
            continue
        got = parse_size(raw)
        if got:
            size, note = got
            if note and not found.get(size):
                found[size] = note
            else:
                found.setdefault(size, note)
        elif raw not in tags:
            tags.append(raw)
    return found, tags


def _family(prices, series):
    return prices["families"].get(series.get("family") or "", prices["families"]["hardware"])


def series_for(prices, cat):
    """Nearest declared ancestor of the product's category path."""
    segs = (cat or "").split("/")
    while segs:
        hit = prices["series"].get("/".join(segs))
        if hit:
            return hit
        segs.pop()
    return None


def _surcharge(fam, size, base_size):
    tbl = fam.get("surcharge") or {}
    if size in tbl and base_size in tbl:
        return tbl[size] - tbl[base_size]
    # Defensive: a size the table has never seen still has to price sensibly
    # rather than silently costing the same as the base.
    per_cm = fam.get("fallback_per_cm", 10)
    a, b = parse_size(size), parse_size(base_size)
    if not a or not b:
        return 0
    (aw, ah) = [int(x) for x in a[0].split("/")]
    (bw, bh) = [int(x) for x in b[0].split("/")]
    return int(round(((aw - bw) + (ah - bh)) * per_cm))


def resolve(rec, prices):
    """-> dict(price, base_size, sizes=[{size,note,delta,price}], tags, addons)

    `price` is the price at `base_size`, which is what the page renders on load and
    what the cards and meta descriptions use.
    """
    series = series_for(prices, rec.get("cat", ""))
    found, tags = raw_sizes(rec)
    if not series:
        return {"price": 0.0, "base_size": "", "sizes": [], "tags": tags, "addons": []}

    fam = _family(prices, series)
    base_price = float(prices.get("products", {}).get(rec["id"], {}).get(
        "base_price", series["base_price"]))
    base_size = series.get("base_size") or ""

    # Observed sizes first, then the family's standard ladder. The source lists a
    # single size for most series, but the catalogue itself says "цената на всяка
    # врата се формира според индивидуалните размери" — the other standard widths
    # are made to order, so offering only the one scraped size understates her range.
    order = list(found)
    for s in fam.get("default_sizes") or []:
        if s not in order:
            order.append(s)
    if base_size and order and base_size not in order:
        # The series' declared base is the price anchor; it has to be offerable.
        order.append(base_size)
    order.sort(key=lambda s: [int(x) for x in s.split("/")])

    sizes = []
    for s in order:
        delta = _surcharge(fam, s, base_size) if base_size else 0
        sizes.append({"size": s, "note": found.get(s, ""), "delta": delta,
                      "price": round(base_price + delta, 2)})

    # Anchor the displayed price to the cheapest offered size, so the headline
    # number is never one the customer cannot actually buy.
    if sizes:
        anchor = min(sizes, key=lambda x: x["price"])
        base_price, base_size = anchor["price"], anchor["size"]
        for s in sizes:
            s["delta"] = round(s["price"] - base_price, 2)

    return {"price": round(base_price, 2), "base_size": base_size, "sizes": sizes,
            "tags": tags, "addons": prices.get("addons", [])}
