#!/usr/bin/env python3
"""Offline checks for the parsing/normalising/dedupe pipeline.

Runs against fixtures shaped like real Overpass and Places responses, so the
transform logic can be verified without network access.

    python3 leadgen/test_pipeline.py
"""

import sys
import unittest

sys.path.insert(0, __file__.rsplit("/", 1)[0])

from scrape_sofia import (  # noqa: E402
    dedupe, normalise_phone, parse_overpass, parse_places, phone_kind,
)

OVERPASS_FIXTURE = [
    {   # national format with spaces
        "type": "node", "id": 1, "lat": 42.6977, "lon": 23.3219,
        "tags": {"name": "Кафе Ротонда", "amenity": "cafe", "phone": "02 987 6543",
                 "addr:street": "ул. Съборна", "addr:housenumber": "2",
                 "addr:city": "София", "opening_hours": "Mo-Su 08:00-22:00"},
    },
    {   # already international, plus website/email
        "type": "way", "id": 2, "center": {"lat": 42.69, "lon": 23.32},
        "tags": {"name": "Адвокатска кантора Иванов", "office": "lawyer",
                 "contact:phone": "+359 2 4008080", "website": "https://example.bg",
                 "contact:email": "office@example.bg", "addr:street": "бул. Витоша"},
    },
    {   # mobile, 00 prefix
        "type": "node", "id": 3, "lat": 42.70, "lon": 23.33,
        "tags": {"name": "Автосервиз Мото", "shop": "car_repair",
                 "phone": "00359 888 123456"},
    },
    {   # several numbers in one tag -> take the first
        "type": "node", "id": 4, "lat": 42.71, "lon": 23.30,
        "tags": {"name": "Зъболекар Д-р Петров", "healthcare": "dentist",
                 "phone": "0888 111222; 02 9998877"},
    },
    {"type": "node", "id": 5, "tags": {"amenity": "bench", "phone": "0888111333"}},   # no name
    {"type": "node", "id": 6, "tags": {"name": "Няма телефон", "shop": "bakery"}},    # no phone
    {   # unusable junk in the phone tag
        "type": "node", "id": 7, "lat": 42.72, "lon": 23.31,
        "tags": {"name": "Счупен запис", "shop": "kiosk", "phone": "n/a"},
    },
    {   # exact duplicate number of id=1, different record
        "type": "node", "id": 8, "lat": 42.6978, "lon": 23.3220,
        "tags": {"name": "Ротонда (стар запис)", "amenity": "cafe", "phone": "+35929876543"},
    },
]

PLACES_FIXTURE = [
    {"id": "abc", "displayName": {"text": "Счетоводна къща Алфа"},
     "internationalPhoneNumber": "+359 2 111 2233", "primaryType": "accounting",
     "formattedAddress": "ул. Раковски 100, София",
     "websiteUri": "https://alfa.bg", "location": {"latitude": 42.69, "longitude": 23.32}},
    {"id": "def", "displayName": {"text": "Без телефон ООД"},
     "formattedAddress": "София", "location": {"latitude": 42.69, "longitude": 23.32}},
]


class TestNormalisePhone(unittest.TestCase):
    def test_bulgarian_formats_reach_e164(self):
        cases = {
            "02 987 6543": "+35929876543",
            "+359 2 4008080": "+35924008080",
            "00359 888 123456": "+359888123456",
            "0888 111222": "+359888111222",
            "(02) 981-23-45": "+35929812345",
            "359 2 9876543": "+35929876543",
        }
        for raw, want in cases.items():
            self.assertEqual(normalise_phone(raw), want, f"input {raw!r}")

    def test_multi_number_tag_takes_first(self):
        self.assertEqual(normalise_phone("0888 111222; 02 9998877"), "+359888111222")
        self.assertEqual(normalise_phone("02 9998877 / 0888111222"), "+35929998877")

    def test_unusable_input_rejected(self):
        for raw in ["", None, "n/a", "-", "0888", "+3592987654321234", "12345"]:
            self.assertIsNone(normalise_phone(raw), f"input {raw!r} should be dropped")

    def test_classification(self):
        self.assertEqual(phone_kind("+359888123456"), "mobile")
        self.assertEqual(phone_kind("+35929876543"), "sofia_landline")
        self.assertEqual(phone_kind("+442071234567"), "foreign")


class TestParsing(unittest.TestCase):
    def test_overpass_keeps_only_callable_named_records(self):
        rows = parse_overpass(OVERPASS_FIXTURE)
        self.assertEqual(len(rows), 5, [r["name"] for r in rows])
        names = {r["name"] for r in rows}
        self.assertNotIn("Няма телефон", names)   # no phone
        self.assertNotIn("Счупен запис", names)   # junk phone
        first = rows[0]
        self.assertEqual(first["phone"], "+35929876543")
        self.assertEqual(first["address"], "ул. Съборна 2")
        self.assertEqual(first["category"], "amenity")
        self.assertEqual(first["type"], "cafe")
        self.assertTrue(first["source_url"].endswith("/node/1"))

    def test_places_parsing(self):
        rows = parse_places(PLACES_FIXTURE)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["phone"], "+35921112233")
        self.assertEqual(rows[0]["source"], "google_places")


class TestDedupe(unittest.TestCase):
    def test_same_number_collapses(self):
        rows = parse_overpass(OVERPASS_FIXTURE)
        self.assertEqual(len(dedupe(rows)), 4)

    def test_suppression_list_wins(self):
        rows = parse_overpass(OVERPASS_FIXTURE)
        out = dedupe(rows, suppressed={"+359888123456"})
        self.assertNotIn("+359888123456", {r["phone"] for r in out})
        self.assertEqual(len(out), 3)


if __name__ == "__main__":
    unittest.main(verbosity=2)
