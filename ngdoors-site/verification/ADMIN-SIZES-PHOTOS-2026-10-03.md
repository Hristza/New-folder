# NG Doors admin sizes and photos, 3 October 2026

Scope: per-product size labels and individual EUR prices, catalogue and owner-added products, public size selection, preserve unsaved edits during photo uploads, and begin the authorised ChatGPT product-photo replacement.

## Verification

- Two clean runs each: `python test_admin_sync.py`, `node supabase/test_schema.mjs` (52 database checks), `python test_build_admin.py`, and `node test_admin_ui.mjs`.
- Browser tests render the real HTML, CSS and JavaScript at mobile and desktop widths. Supabase is explicitly mocked in those UI tests. Actual database validation and anonymous-write denial were tested separately with PGlite.
- Fixtures cover arbitrary size labels, distinct cent-accurate prices, one size, empty sizes, inherited catalogue prices, zero-price quotes, duplicate rejection, saved reload, owner-added products, wrong-password refusal, and retaining unsaved size edits across a photo upload.
- Live Supabase migration `owner_door_size_prices`, version `20261003191547`, applied successfully. Product and override row counts and content fingerprints were identical before and after (both tables currently empty). Existing RLS policies remain in place.
- A final build using live Supabase data produced 1,037 pages and 961 product pages. `check.py` passed; public files weigh 67.6 MB, above the approximate 60 MB target and below the 70 MB ceiling.
- Six of 1,638 unique product source photos have been replaced with inspected native ChatGPT renders. M00 has two views; M01 to M04 have one each. Reference hardware, finish, panel design and frame were compared before acceptance. Real installation gallery photos are unchanged. Remaining images are recorded as pending in `renders/manifest.json`; the ledger is not an automatic rendering worker.

## Pending live proof

Deployment, a real login for the owner account, live save/readback of size-price data, and delivery of the remaining 1,632 product source-photo renders. The local mocked login test does not establish receipt of a magic-link email or the mother's ability to enter the production panel.
