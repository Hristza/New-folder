"""One live RLS/size-price exercise; credentials arrive through stdin, never files."""
import json
import sys
import urllib.error
import urllib.request
import uuid

credentials = json.loads(sys.stdin.readline())
url = "https://glrijbqwbykcinhgjeys.supabase.co/rest/v1/product_overrides"
key = "door:codex-size-check-" + uuid.uuid4().hex
headers = {"apikey": credentials["public_key"], "Content-Type": "application/json",
           "Authorization": "Bearer " + credentials["access_token"], "Prefer": "return=representation"}


def call(method, suffix="", body=None, authenticated=True):
    h = dict(headers)
    if not authenticated:
        h.pop("Authorization")
    request = urllib.request.Request(url + suffix, method=method, headers=h,
                                    data=None if body is None else json.dumps(body).encode())
    try:
        with urllib.request.urlopen(request, timeout=45) as response:
            text = response.read().decode()
            return response.status, json.loads(text) if text else None
    except urllib.error.HTTPError as error:
        return error.code, json.loads(error.read().decode())


prices = [{"size": "91 x 213", "price": 245.50}, {"size": "101 x 223", "price": 307.01}]
try:
    status, data = call("POST", body={"product_key": key, "hidden": True, "size_prices": prices})
    assert status == 201 and data[0]["size_prices"] == prices, ("save", status)
    status, data = call("GET", "?product_key=eq." + key + "&select=product_key,size_prices")
    assert status == 200 and data[0]["size_prices"] == prices, ("readback", status)
    status, data = call("PATCH", "?product_key=eq." + key,
                        {"size_prices": [{"size": "91 x 213", "price": -1}]})
    assert status == 400 and data.get("code") == "23514", ("invalid-price", status)
    status, data = call("PATCH", "?product_key=eq." + key,
                        {"size_prices": [{"size": "hacked", "price": 1}]}, authenticated=False)
    assert status in (401, 403) or (status == 200 and data == []), ("anonymous-write", status)
    status, data = call("GET", "?product_key=eq." + key + "&select=size_prices")
    assert status == 200 and data[0]["size_prices"] == prices, ("unchanged-after-denial", status)
    print("LIVE PASS: owner save/readback, invalid-price constraint, anonymous write denied")
finally:
    status, data = call("DELETE", "?product_key=eq." + key)
    assert status in (200, 204), ("cleanup", status)
    status, data = call("GET", "?product_key=eq." + key + "&select=product_key")
    assert status == 200 and data == [], ("cleanup-readback", status)
    print("CLEANUP PASS: temporary hidden test record removed")
