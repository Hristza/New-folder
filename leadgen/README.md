# Sofia business lead harvester

Builds a CSV of Sofia businesses that **publish their own phone number**, ready
for a calling list. No numbers are invented — every row carries a `source_url`
you can open to check the listing.

## Quick start

```bash
# 1000 leads from OpenStreetMap, no API key, no cost
python3 leadgen/scrape_sofia.py --limit 1000 --out leads_sofia.csv
```

That is the whole thing — no dependencies beyond the Python 3 standard library.

## Sources

| Source | Key needed | Cost | Notes |
|---|---|---|---|
| `osm` (default) | no | free | OpenStreetMap via Overpass. ODbL-licensed. Strongest on offices, restaurants, clinics, workshops. |
| `places` | `GOOGLE_PLACES_API_KEY` | billed per request | Google Places Text Search. Better coverage of small retail and hospitality. |

```bash
# Both sources, merged and deduped
GOOGLE_PLACES_API_KEY=xxx python3 leadgen/scrape_sofia.py --source both --limit 1000

# Target specific trades (Places matches Bulgarian-language queries well)
GOOGLE_PLACES_API_KEY=xxx python3 leadgen/scrape_sofia.py --source places \
  --query "счетоводна кантора София" \
  --query "адвокатска кантора София" \
  --query "автосервиз София" \
  --limit 600
```

## Useful flags

| Flag | What it does |
|---|---|
| `--category shop` | Restrict OSM harvest. Repeatable. One of: shop, office, amenity, craft, healthcare, tourism, leisure. |
| `--landline-only` | Drop mobile numbers. Sofia landlines (`+3592…`) are almost always genuine business lines; `+35988…` is often a sole trader's personal mobile. |
| `--bbox 42.60,23.19,42.79,23.47` | Change the area. Widen it if you come up short. |
| `--suppress leadgen/suppression.txt` | Numbers to never dial. Append every opt-out here. |
| `--limit N` | Cap the output. |

## Output

CSV with: `name, phone, phone_raw, category, type, address, city, postcode,
website, email, opening_hours, lat, lon, source, source_url, phone_kind`.

Rows are sorted richest-first — listings with a website, email, address and
opening hours sit at the top, because those are the ones worth a call.

`phone` is normalised to E.164 (`+3592…`), so it imports into any dialler.
`phone_raw` keeps the original string in case normalisation went wrong.

## If you get fewer than 1000

The script warns you when it does. In order of effectiveness:

1. Drop `--landline-only` if you set it.
2. Use all categories (the default) rather than a subset.
3. Widen `--bbox` to cover Sofia oblast, e.g. `42.50,23.00,42.90,23.70`.
4. Add `--source places` with a list of Bulgarian trade queries — this is the
   biggest single lift, since Google's coverage of Sofia SMEs beats OSM's.

## Before you dial — Bulgarian rules

Not legal advice; confirm with a lawyer before you run a campaign at volume.

- **GDPR applies even to business numbers.** A named person's direct line is
  personal data. Your basis for cold B2B calling is normally legitimate
  interest, which means you must log why, and stop on request.
- **The КЗП (Commission for Consumer Protection) keeps a register of numbers
  that must not receive unsolicited marketing calls.** Screen against it before
  a consumer-facing campaign and re-screen periodically. Company switchboards
  are lower risk than mobiles.
- **Sole traders (ЕТ) and freelancers count as consumers** in practice. A
  `+35988…` mobile on a listing is frequently one of these — `--landline-only`
  exists for exactly this reason.
- **Honour opt-outs immediately and permanently.** Append the number to
  `leadgen/suppression.txt`; every later run excludes it automatically.
- **Identify yourself and your company at the start of the call**, and give a
  working way to opt out.
- Calling hours: keep to normal business hours. Evening and weekend cold calls
  generate complaints regardless of what the law strictly permits.

## Tests

```bash
python3 leadgen/test_pipeline.py
```

Covers phone normalisation (Bulgarian formats, multi-number tags, junk),
record parsing for both sources, dedupe, and the suppression list. Runs offline
against fixtures, so it needs no network and no API key.
