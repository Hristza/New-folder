# -*- coding: utf-8 -*-
"""Self-check for admin_sync.config() and load(). Run: python test_admin_sync.py

The failure this guards: a broken configuration, or an API that answers garbage,
read as "nothing to apply", which builds catalogue-only and silently undoes her edits.
"""
import io
import json
import os
import tempfile

import admin_sync as a


def cfg(file_body=None, env=None):
    d = tempfile.mkdtemp()
    a.CONFIG = os.path.join(d, "admin_config.json")
    if file_body is not None:
        io.open(a.CONFIG, "w", encoding="utf-8").write(file_body)
    os.environ.pop("NGDOORS_API_URL", None)
    os.environ.update(env or {})
    try:
        return ("ok", a.config())
    except SystemExit as e:
        return ("exit", str(e))


U = "https://api.test"
# nothing configured anywhere -> catalogue-only is correct
assert cfg() == ("ok", None)
assert cfg(json.dumps({"api_url": ""})) == ("ok", None)
assert cfg(json.dumps({"api_url": U + "/"})) == ("ok", {"url": U})
# env alone works, and beats the file
assert cfg(env={"NGDOORS_API_URL": U}) == ("ok", {"url": U})
assert cfg(json.dumps({"api_url": "https://old.test"}), {"NGDOORS_API_URL": U})[1] == {"url": U}
# fail closed: malformed file, non-object, non-https
assert cfg("{not json")[0] == "exit"
assert cfg("[]")[0] == "exit"
assert cfg("{not json", {"NGDOORS_API_URL": U})[0] == "exit"
assert cfg(json.dumps({"api_url": "http://api.test"}))[0] == "exit"
os.environ.pop("NGDOORS_API_URL", None)


class Resp(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *x):
        return False


def serve(body):
    a.urllib.request.urlopen = lambda req, timeout=0: Resp(json.dumps(body).encode())


# an answer missing a list is an error, not an empty catalogue
serve({"overrides": [], "products": []})
try:
    a._get({"url": U}, "/public-data")
    raise AssertionError("partial answer accepted")
except ValueError:
    pass

# load(): photos become /media/ URLs with a manifest row; exclusions survive
excluded = ["https://catalogue.test/photo.jpg"]
ph = {"s": "catalogue/abcdef12-600.webp", "l": "catalogue/abcdef12-1200.webp", "w": 1200, "h": 900}
serve({"overrides": [{"product_key": "door:123", "images": [ph], "excluded_images": excluded}],
       "products": [], "photos": [{"album": "A", "photo": ph}], "settings": [{"key": "phone", "value": "1"}]})
a.config = lambda: {"url": U}
d = a.load()
big = U + "/media/catalogue/abcdef12-1200.webp"
assert d["overrides"]["door:123"]["excluded_images"] == excluded
assert d["overrides"]["door:123"]["images"] == [big]
assert d["images"][big]["urls"][600] == U + "/media/catalogue/abcdef12-600.webp"
assert d["photos"][0]["url"] == big and d["settings"] == {"phone": "1"}

# unreachable API -> the build stops
def down(req, timeout=0):
    raise OSError("connection refused")
a.urllib.request.urlopen = down
try:
    a.load()
    raise AssertionError("built without her edits")
except SystemExit:
    pass
print("test_admin_sync: ALL PASS")
