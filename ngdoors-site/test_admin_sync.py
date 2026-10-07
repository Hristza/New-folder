# -*- coding: utf-8 -*-
"""Self-check for admin_sync.config() and pagination. Run: python test_admin_sync.py

The failure this guards: a broken or half-written configuration read as "not
configured", which builds catalogue-only and silently undoes her saved edits.
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
    for k in ("NGDOORS_SUPABASE_URL", "NGDOORS_SUPABASE_KEY"):
        os.environ.pop(k, None)
    os.environ.update(env or {})
    try:
        return ("ok", a.config())
    except SystemExit as e:
        return ("exit", str(e))


U, K = "https://x.supabase.co", "sb_publishable_x"
# nothing configured anywhere -> catalogue-only is correct
assert cfg() == ("ok", None)
assert cfg(json.dumps({"supabase_url": "", "supabase_key": ""})) == ("ok", None)
# env alone works, with the file absent or malformed-free
assert cfg(env={"NGDOORS_SUPABASE_URL": U, "NGDOORS_SUPABASE_KEY": K}) == ("ok", {"url": U, "key": K})
# env beats file
assert cfg(json.dumps({"supabase_url": "https://old.supabase.co", "supabase_key": "old"}),
           {"NGDOORS_SUPABASE_URL": U, "NGDOORS_SUPABASE_KEY": K})[1] == {"url": U, "key": K}
# fail closed: malformed file, non-object, half config, non-https
assert cfg("{not json")[0] == "exit"
assert cfg("[]")[0] == "exit"
assert cfg("{not json", {"NGDOORS_SUPABASE_URL": U, "NGDOORS_SUPABASE_KEY": K})[0] == "exit"
assert cfg(json.dumps({"supabase_url": U, "supabase_key": ""}))[0] == "exit"
assert cfg(env={"NGDOORS_SUPABASE_KEY": K})[0] == "exit"
assert cfg(json.dumps({"supabase_url": "http://x.supabase.co", "supabase_key": K}))[0] == "exit"

# a secret key would be published in every page: refuse it, from file or env
import base64


def jwt(role):
    b = lambda d: base64.urlsafe_b64encode(json.dumps(d).encode()).decode().rstrip("=")
    return b({"alg": "HS256"}) + "." + b({"role": role, "iss": "supabase"}) + ".sig"


assert cfg(json.dumps({"supabase_url": U, "supabase_key": "sb_secret_abc"}))[0] == "exit"
assert cfg(env={"NGDOORS_SUPABASE_URL": U, "NGDOORS_SUPABASE_KEY": jwt("service_role")})[0] == "exit"
assert cfg(env={"NGDOORS_SUPABASE_URL": U, "NGDOORS_SUPABASE_KEY": "not-a-key"})[0] == "exit"
assert cfg(env={"NGDOORS_SUPABASE_URL": U, "NGDOORS_SUPABASE_KEY": jwt("anon")})[0] == "ok"

# pagination: 1234 rows served 500 at a time must all come back, in order
rows = [{"i": i} for i in range(1234)]
seen = []


class Resp(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *x):
        return False


def fake_open(req, timeout=0):
    q = dict(p.split("=") for p in req.full_url.split("?", 1)[1].split("&"))
    off, lim = int(q["offset"]), int(q["limit"])
    seen.append(off)
    return Resp(json.dumps(rows[off:off + lim]).encode())


a.urllib.request.urlopen = fake_open
got = a._get({"url": U, "key": K}, "/rest/v1/t?select=*&order=id.asc")
assert got == rows, len(got)
assert seen == [0, 500, 1000], seen
# exactly one full page must still ask for the next (empty) one
rows = [{"i": i} for i in range(500)]
seen.clear()
assert a._get({"url": U, "key": K}, "/rest/v1/t?select=*") == rows and seen == [0, 500]
# Saved per-product exclusions survive the same real loader used by publishing.
excluded = ['https://catalogue.test/photo.jpg']
a.config = lambda: {"url": U, "key": K}
a._get = lambda config, path: [{"product_key": "door:123", "images": [], "excluded_images": excluded}] if 'product_overrides?' in path else []
assert a.load()['overrides']['door:123']['excluded_images'] == excluded
print("test_admin_sync: ALL PASS")
