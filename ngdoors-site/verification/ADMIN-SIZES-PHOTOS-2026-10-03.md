# NG Doors admin sizes and photos, 3 October 2026

Scope: per-product size labels and individual EUR prices, catalogue and owner-added products, public size selection, preserve unsaved edits during photo uploads, and begin the authorised ChatGPT product-photo replacement.

## Verification

- Two clean runs each: `python test_admin_sync.py`, `node supabase/test_schema.mjs` (52 database checks), `python test_build_admin.py`, and `node test_admin_ui.mjs`.
- Browser tests render the real HTML, CSS and JavaScript at mobile and desktop widths. Supabase is explicitly mocked in those UI tests. Actual database validation and anonymous-write denial were tested separately with PGlite.
- Fixtures cover arbitrary size labels, distinct cent-accurate prices, one size, empty sizes, inherited catalogue prices, zero-price quotes, duplicate rejection, saved reload, owner-added products, wrong-password refusal, and retaining unsaved size edits across a photo upload.
- Live Supabase migration `owner_door_size_prices`, version `20261003191547`, applied successfully. Product and override row counts and content fingerprints were identical before and after (both tables currently empty). Existing RLS policies remain in place.
- A final build using live Supabase data produced 1,037 pages and 961 product pages. `check.py` passed; public files weigh 67.6 MB (initial six-photo build), above the approximate 60 MB target and below the 70 MB ceiling.
- Fifty-seven of 1,638 product source-photo URLs have been replaced with inspected native ChatGPT renders. The initial aluminium range, a second honey-oak M00, MZ-2, S1, Multi Super, the D entrance series the complete O and Z entrance series and initial T front/back views are replaced. Fifty-five native renders cover these fifty-seven URLs; the original M05/M06/M07 references depict the same door views, and M05/M07 are exact image duplicates. Reference hardware, finish, panel design and frame were compared before acceptance. Real installation gallery photos are unchanged. Remaining images are recorded as pending in `renders/manifest.json`; the ledger is not an automatic rendering worker.

## Production acceptance

- Commit `69be97cad9c8afd5e37b5e4364ca4bb2fca30047` deployed successfully: Cloudflare Pages deployment `ebd4849c-d124-4244-91a2-4e8ea4d3207f`, finished 19:42:18 UTC. Six initial replacement photos match production byte for byte. The current editor and all 961 catalogue records are present.
- The twenty-five-photo checkpoint, commit `fc597c4545238131d21546a4b6ee092a88672c35`, deployed successfully as `b7698c29-9713-4958-925d-d804688cea4a`, finished 20:28:50 UTC. All twenty-three distinct replacement WebP assets match production byte for byte.
- Owner account `ngbuildings@abv.bg` received a new password at the user's explicit request. The password was given to the user and is not stored in repository files. Both a real Auth API login and a real headless Brave form login succeeded with admin access.
- `verification/live_size_roundtrip.py` passed authenticated save/readback, invalid negative-price rejection, and anonymous update prevention. Its temporary hidden override was removed and absence verified.
- `verification/live_admin_ui.mjs` passed against production without mocks: owner password login, mobile/desktop render, upload, two individual size prices (245.50 and 307.01 EUR), save, and reload with exact cent values. Its temporary hidden product and uploaded media were removed. Production screenshots were inspected.
- Existing user Brave was inspected through the accessibility tree; the current catalogue and size editor are present. Windows was locked, so its attempted desktop capture showed the lock screen and was not used as a page-render proof. The separate headless Brave acceptance test supplied actual live page screenshots.
- Claude was sent the deployment handoff for his separately owned `notify` email work. Transport receipt exists; no acknowledgement has been received for this handoff.

- The forty-one-photo checkpoint, commit `f075b1e8b13aa10e46efed3bf41fa0056a1c79d4`, deployed successfully as `1f528d34-400e-4dac-9bea-ef4c15330c5b`, finished 20:47:03 UTC. All sixteen new assets match production byte for byte.

## Remaining work

Publish the next accepted images and finish replacing the remaining product reference URLs (1,581 pending at this checkpoint). The replacement queue contains 1,638 URLs with 1,103 distinct references when grouped by original dimensions and 600px bytes; the automatic reuse rule additionally requires every available reference resolution to match. The queue is not a background rendering worker. Magic-link inbox delivery has not been verified; the tested direct password route provides immediate access.

Photo batch validation: final build and check pass at 68.0 MB public, with all 57 replacement references resolvable. All 357 non-product image entries are unchanged from the original manifest. Reapplying the last image preserves its files after the source-key cleanup regression fix. Published sizes follow the existing catalogue resolution choices; native PNG masters remain available separately.

One Z-02 candidate was rejected because it invented a large pull handle. A corrected native render was inspected and accepted with the original fittings.
