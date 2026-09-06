#!/usr/bin/env python3
"""
Harvest Sofia business listings that publish a phone number.

Two sources, both usable on their own:

  osm     OpenStreetMap via the Overpass API. Free, no key, ODbL-licensed.
  places  Google Places API. Needs GOOGLE_PLACES_API_KEY. Better coverage
          of small retail/hospitality, but billed per request.

Examples:
    python3 leadgen/scrape_sofia.py --limit 1000
    python3 leadgen/scrape_sofia.py --source osm --category shop --category office
    GOOGLE_PLACES_API_KEY=... python3 leadgen/scrape_sofia.py --source places \
        --query "счетоводна кантора" --query "адвокат" --limit 400
"""

import argparse
import csv
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request

OVERPASS_ENDPOINTS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.osm.ch/api/interpreter",
]
PLACES_TEXT_SEARCH = "https://places.googleapis.com/v1/places:searchText"

# Sofia city bounding box (south, west, north, east)
SOFIA_BBOX = (42.60, 23.19, 42.79, 23.47)
SOFIA_CENTRE = (42.6977, 23.3219)

# OSM top-level keys that denote a business-ish entity
CATEGORIES = ["shop", "office", "amenity", "craft", "healthcare", "tourism", "leisure"]
PHONE_KEYS = ["phone", "contact:phone", "contact:mobile", "phone:mobile"]

FIELDS = [
    "name", "phone", "phone_raw", "category", "type", "address", "city",
    "postcode", "website", "email", "opening_hours", "lat", "lon", "source", "source_url",
]


# --------------------------------------------------------------------------- #
# Phone handling
# --------------------------------------------------------------------------- #

def normalise_phone(raw):
    """Return an E.164 Bulgarian number, or None if the value is unusable."""
    if not raw:
        return None
    first = re.split(r"[;,/]| или ", str(raw))[0]
    digits = re.sub(r"[^\d+]", "", first)
    digits = re.sub(r"(?<=.)\+", "", digits)  # strip stray inner '+'
    if not digits:
        return None
    if digits.startswith("00"):
        digits = "+" + digits[2:]
    if digits.startswith("+"):
        pass
    elif digits.startswith("359"):
        digits = "+" + digits
    elif digits.startswith("0"):
        digits = "+359" + digits[1:]
    else:
        return None  # bare fragment, too ambiguous to dial
    if not digits.startswith("+359"):
        return digits if 8 <= len(digits) <= 16 else None
    national = digits[4:]
    # BG national significant numbers run 8-9 digits (Sofia landline 2xxxxxxx,
    # mobile 87/88/89xxxxxxx). Anything outside that is a broken listing.
    return digits if 8 <= len(national) <= 9 else None


def phone_kind(phone):
    if not phone.startswith("+359"):
        return "foreign"
    nat = phone[4:]
    if nat.startswith(("87", "88", "89", "98", "99")):
        return "mobile"
    if nat.startswith("2"):
        return "sofia_landline"
    return "landline"


# --------------------------------------------------------------------------- #
# Source: OpenStreetMap / Overpass
# --------------------------------------------------------------------------- #

def build_overpass_query(bbox, categories, timeout=180):
    s, w, n, e = bbox
    parts = []
    for cat in categories:
        for pk in ("phone", "contact:phone"):
            for kind in ("node", "way", "relation"):
                parts.append(f'{kind}["{cat}"]["{pk}"]({s},{w},{n},{e});')
    body = "\n  ".join(parts)
    return f"[out:json][timeout:{timeout}];\n(\n  {body}\n);\nout center tags;"


def fetch_overpass(query, retries=4):
    data = urllib.parse.urlencode({"data": query}).encode()
    last = None
    for attempt in range(retries):
        endpoint = OVERPASS_ENDPOINTS[attempt % len(OVERPASS_ENDPOINTS)]
        req = urllib.request.Request(
            endpoint, data=data,
            headers={"User-Agent": "sofia-lead-scraper/1.0 (OSM Overpass client)"},
        )
        try:
            sys.stderr.write(f"[osm] {endpoint} (attempt {attempt + 1})\n")
            with urllib.request.urlopen(req, timeout=300) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception as exc:  # noqa: BLE001 - report and retry
            last = exc
            sys.stderr.write(f"[osm] failed: {exc}\n")
            time.sleep(2 ** attempt)
    raise SystemExit(f"All Overpass endpoints failed. Last error: {last}")


def category_of(tags):
    for cat in CATEGORIES:
        if cat in tags:
            return cat, tags[cat]
    return "", ""


def parse_overpass(elements):
    rows = []
    for el in elements:
        tags = el.get("tags", {})
        phone_raw = next((tags[k] for k in PHONE_KEYS if tags.get(k)), None)
        phone = normalise_phone(phone_raw)
        name = tags.get("name") or tags.get("operator") or tags.get("brand")
        if not phone or not name:
            continue
        cat, subcat = category_of(tags)
        centre = el.get("center") or {}
        street, num = tags.get("addr:street", ""), tags.get("addr:housenumber", "")
        rows.append({
            "name": name,
            "phone": phone,
            "phone_raw": phone_raw,
            "category": cat,
            "type": subcat,
            "address": " ".join(x for x in (street, num) if x),
            "city": tags.get("addr:city", ""),
            "postcode": tags.get("addr:postcode", ""),
            "website": tags.get("website") or tags.get("contact:website", ""),
            "email": tags.get("email") or tags.get("contact:email", ""),
            "opening_hours": tags.get("opening_hours", ""),
            "lat": el.get("lat") or centre.get("lat", ""),
            "lon": el.get("lon") or centre.get("lon", ""),
            "source": "osm",
            "source_url": f"https://www.openstreetmap.org/{el['type']}/{el['id']}",
        })
    return rows


def harvest_osm(bbox, categories):
    payload = fetch_overpass(build_overpass_query(bbox, categories))
    elements = payload.get("elements", [])
    sys.stderr.write(f"[osm] {len(elements)} raw elements\n")
    return parse_overpass(elements)


# --------------------------------------------------------------------------- #
# Source: Google Places
# --------------------------------------------------------------------------- #

PLACES_FIELDS = (
    "places.displayName,places.nationalPhoneNumber,places.internationalPhoneNumber,"
    "places.formattedAddress,places.websiteUri,places.primaryType,places.location,"
    "places.id,nextPageToken"
)


def fetch_places_page(query, api_key, page_token=None, radius_m=15000):
    body = {
        "textQuery": query,
        "languageCode": "bg",
        "regionCode": "BG",
        "maxResultCount": 20,
        "locationBias": {
            "circle": {
                "center": {"latitude": SOFIA_CENTRE[0], "longitude": SOFIA_CENTRE[1]},
                "radius": radius_m,
            }
        },
    }
    if page_token:
        body["pageToken"] = page_token
    req = urllib.request.Request(
        PLACES_TEXT_SEARCH,
        data=json.dumps(body).encode(),
        headers={
            "Content-Type": "application/json",
            "X-Goog-Api-Key": api_key,
            "X-Goog-FieldMask": PLACES_FIELDS,
        },
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode("utf-8"))


def parse_places(places):
    rows = []
    for p in places:
        raw = p.get("internationalPhoneNumber") or p.get("nationalPhoneNumber")
        phone = normalise_phone(raw)
        name = (p.get("displayName") or {}).get("text")
        if not phone or not name:
            continue
        loc = p.get("location") or {}
        rows.append({
            "name": name,
            "phone": phone,
            "phone_raw": raw,
            "category": "places",
            "type": p.get("primaryType", ""),
            "address": p.get("formattedAddress", ""),
            "city": "Sofia",
            "postcode": "",
            "website": p.get("websiteUri", ""),
            "email": "",
            "opening_hours": "",
            "lat": loc.get("latitude", ""),
            "lon": loc.get("longitude", ""),
            "source": "google_places",
            "source_url": f"https://www.google.com/maps/place/?q=place_id:{p.get('id', '')}",
        })
    return rows


def harvest_places(queries, api_key, per_query_pages=3):
    rows = []
    for q in queries:
        token = None
        for page in range(per_query_pages):
            try:
                payload = fetch_places_page(q, api_key, token)
            except Exception as exc:  # noqa: BLE001
                sys.stderr.write(f"[places] '{q}' page {page + 1} failed: {exc}\n")
                break
            got = parse_places(payload.get("places", []))
            rows.extend(got)
            sys.stderr.write(f"[places] '{q}' page {page + 1}: +{len(got)}\n")
            token = payload.get("nextPageToken")
            if not token:
                break
            time.sleep(2)  # token needs a moment to become valid
    return rows


# --------------------------------------------------------------------------- #
# Assembly
# --------------------------------------------------------------------------- #

def load_suppression(path):
    """Numbers you must never dial again: opt-outs, DNC entries, bad data."""
    if not path or not os.path.exists(path):
        return set()
    out = set()
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            n = normalise_phone(line.strip())
            if n:
                out.add(n)
    return out


def dedupe(rows, suppressed=frozenset()):
    seen_phone, seen_ident, out = set(), set(), []
    for r in rows:
        if r["phone"] in suppressed or r["phone"] in seen_phone:
            continue
        ident = (r["name"].strip().lower(), r["phone"])
        if ident in seen_ident:
            continue
        seen_phone.add(r["phone"])
        seen_ident.add(ident)
        out.append(r)
    return out


def main():
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--source", choices=["osm", "places", "both"], default="osm")
    ap.add_argument("--limit", type=int, default=1000)
    ap.add_argument("--out", default="leads_sofia.csv")
    ap.add_argument("--category", action="append", choices=CATEGORIES,
                    help="OSM categories; repeatable. Default: all.")
    ap.add_argument("--query", action="append",
                    help="Google Places text queries; repeatable.")
    ap.add_argument("--bbox", help="south,west,north,east")
    ap.add_argument("--suppress", default="leadgen/suppression.txt",
                    help="File of numbers to exclude, one per line.")
    ap.add_argument("--landline-only", action="store_true",
                    help="Drop mobile numbers (they are far likelier to be personal).")
    args = ap.parse_args()

    bbox = tuple(float(x) for x in args.bbox.split(",")) if args.bbox else SOFIA_BBOX
    rows = []

    if args.source in ("osm", "both"):
        rows += harvest_osm(bbox, args.category or CATEGORIES)

    if args.source in ("places", "both"):
        key = os.environ.get("GOOGLE_PLACES_API_KEY")
        if not key:
            raise SystemExit("GOOGLE_PLACES_API_KEY is not set.")
        queries = args.query or ["business in Sofia"]
        rows += harvest_places(queries, key)

    for r in rows:
        r["phone_kind"] = phone_kind(r["phone"])
    if args.landline_only:
        before = len(rows)
        rows = [r for r in rows if r["phone_kind"] != "mobile"]
        sys.stderr.write(f"[filter] dropped {before - len(rows)} mobile numbers\n")

    rows = dedupe(rows, load_suppression(args.suppress))
    sys.stderr.write(f"[info] {len(rows)} usable leads after dedupe\n")

    # Richest records first: more contact channels means a more callable lead.
    rows.sort(key=lambda r: -sum(
        bool(r[k]) for k in ("website", "email", "address", "opening_hours")
    ))
    rows = rows[: args.limit]

    fields = FIELDS + ["phone_kind"]
    with open(args.out, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)

    if len(rows) < args.limit:
        sys.stderr.write(
            f"[warn] only {len(rows)} of {args.limit} requested. Widen --bbox, "
            "add --category, or add --source places.\n"
        )
    sys.stderr.write(f"[done] wrote {len(rows)} leads -> {args.out}\n")


if __name__ == "__main__":
    main()
