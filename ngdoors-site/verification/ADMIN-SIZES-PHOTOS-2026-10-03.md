# NG Doors admin sizes and photos, 3 October 2026

Scope: per-product size labels and individual EUR prices, catalogue and owner-added products, public size selection, preserve unsaved edits during photo uploads, and begin the authorised ChatGPT product-photo replacement.

## Verification

- Two clean runs each: `python test_admin_sync.py`, `node supabase/test_schema.mjs` (52 database checks), `python test_build_admin.py`, and `node test_admin_ui.mjs`.
- Browser tests render the real HTML, CSS and JavaScript at mobile and desktop widths. Supabase is explicitly mocked in those UI tests. Actual database validation and anonymous-write denial were tested separately with PGlite.
- Fixtures cover arbitrary size labels, distinct cent-accurate prices, one size, empty sizes, inherited catalogue prices, zero-price quotes, duplicate rejection, saved reload, owner-added products, wrong-password refusal, and retaining unsaved size edits across a photo upload.
- Live Supabase migration `owner_door_size_prices`, version `20261003191547`, applied successfully. Product and override row counts and content fingerprints were identical before and after (both tables currently empty). Existing RLS policies remain in place.
- A final build using live Supabase data produced 1,037 pages and 961 product pages. `check.py` passed; public files weigh 67.6 MB (initial six-photo build), above the approximate 60 MB target and below the 70 MB ceiling.
- 233 of 1,638 product source-photo URLs now use inspected native ChatGPT renders. 231 native masters cover these URLs, including the initial aluminium, D, O, Z, T, KL, LCR and PVC entrance ranges. The M05/M06/M07 reference views share one accepted render after comparison; M05/M07 are exact image duplicates. Hardware, finish, panel design and frame were compared before acceptance. The 357 non-product image entries are unchanged. The pending ledger does not generate images automatically.

## Production acceptance

- Commit `69be97cad9c8afd5e37b5e4364ca4bb2fca30047` deployed successfully: Cloudflare Pages deployment `ebd4849c-d124-4244-91a2-4e8ea4d3207f`, finished 19:42:18 UTC. Six initial replacement photos match production byte for byte. The current editor and all 961 catalogue records are present.
- The twenty-five-photo checkpoint, commit `fc597c4545238131d21546a4b6ee092a88672c35`, deployed successfully as `b7698c29-9713-4958-925d-d804688cea4a`, finished 20:28:50 UTC. All twenty-three distinct replacement WebP assets match production byte for byte.
- Owner account `ngbuildings@abv.bg` received a new password at the user's explicit request. The password was given to the user and is not stored in repository files. Both a real Auth API login and a real headless Brave form login succeeded with admin access.
- `verification/live_size_roundtrip.py` passed authenticated save/readback, invalid negative-price rejection, and anonymous update prevention. Its temporary hidden override was removed and absence verified.
- `verification/live_admin_ui.mjs` passed against production without mocks: owner password login, mobile/desktop render, upload, two individual size prices (245.50 and 307.01 EUR), save, and reload with exact cent values. Its temporary hidden product and uploaded media were removed. Production screenshots were inspected.
- Existing user Brave was inspected through the accessibility tree; the current catalogue and size editor are present. Windows was locked, so its attempted desktop capture showed the lock screen and was not used as a page-render proof. The separate headless Brave acceptance test supplied actual live page screenshots.
- Claude was sent the deployment handoff for his separately owned `notify` email work. Transport receipt exists; no acknowledgement has been received for this handoff.

- The forty-one-photo checkpoint, commit `f075b1e8b13aa10e46efed3bf41fa0056a1c79d4`, deployed successfully as `1f528d34-400e-4dac-9bea-ef4c15330c5b`, finished 20:47:03 UTC. All sixteen new assets match production byte for byte.

- The fifty-seven-photo checkpoint, commit `6bef4f231212ac298c4b4ba05cadd4c620f22f52`, deployed as `d21b0c9f-0114-4f41-97ff-d20c0f259746`, finished 20:58:14 UTC. All sixteen new assets match production byte for byte.
- The seventy-three-photo checkpoint, commit `99ab262063525220373c8f16001ad49c9ebf5982`, deployed as `e0cc1ed9-2a3c-4cae-b7b3-a58c1ad559df`, finished 21:14:49 UTC. All nineteen new assets for its sixteen new reference URLs match production byte for byte.
- The eighty-nine-photo checkpoint, commit `2ff280c7622eb2424ef0ecca262557272a08153e`, deployed as `2e0cf7df-c823-4ef4-a37e-22ac01082e88`, finished 21:35:54 UTC. All nineteen new assets for sixteen new reference URLs match production byte for byte.
- The 105-photo checkpoint, commit `5b655cfcca8a4a0c2d6d5e415623002eb63ffbb4`, deployed as `7514dfc5-61d7-4bbb-846a-34a2b7205239`, finished 21:47:04 UTC. All twenty-five new assets for sixteen new reference URLs match production byte for byte.
- The 121-photo checkpoint, commit `578dea75dfdaf85542b9dcd6aff8970e6d94e3ac`, deployed as `a60d80f3-ccdc-4141-8ac6-bb58ab7ff35e`, finished 21:57:52 UTC. All twenty-one new assets for sixteen new reference URLs match production byte for byte.
- The 137-photo checkpoint, commit `5fab16311648cbe7fe412f80b1796fd6d08074c2`, deployed as `9769afe4-af6d-4848-9594-923c4131fe52`, finished 22:09:14 UTC. All eighteen new assets for sixteen new reference URLs match production byte for byte.
- The 153-photo checkpoint, commit `55e225af88d678389ad558c1598e4caad12466a8`, deployed as `6d4a4b0b-5eb8-4ce6-b22f-129296d0723f`, finished 22:25:41 UTC. All eighteen new assets for sixteen new reference URLs match production byte for byte.
- The live T 901 product page passed real headless Brave checks: both generated front/back images loaded, thumbnail selection switched the main image, and desktop/mobile screenshots were inspected. No horizontal overflow or page errors were observed.

## Remaining work

Publish the next accepted images and finish replacing the remaining product reference URLs (1,405 pending at this checkpoint). Main photos for remaining catalogue products are being prioritised before additional views. The full replacement queue contains 1,638 URLs with 1,103 distinct references when grouped by original dimensions and 600px bytes; the automatic reuse rule additionally requires every available reference resolution to match. The queue is not a background rendering worker. Magic-link inbox delivery has not been verified; the tested direct password route provides immediate access.

Photo batch validation: final build and check pass at 69.8 MB public, with all 233 replacement references resolvable. All 357 non-product image entries are unchanged from the original manifest. Reapplying the last image preserves its files after the source-key cleanup regression fix. Published sizes follow the existing catalogue resolution choices; native PNG masters remain available separately.

One Z-02 candidate was rejected because it invented a large pull handle. A corrected native render was inspected and accepted with the original fittings.

One wenge WIN candidate was rejected for a missing peephole. Its corrected native render was inspected and accepted.

The first eight flooring finishes now have inspected native renders. Their WebP copies use quality 75 to fit the unchanged site size ceiling; full native PNGs remain preserved. The encoded wood and stone previews were inspected. Missing-asset regeneration and idempotent initialization preserve the chosen encoding quality and identical bytes.

The live Check One 2077 oak and STONEX FT015 HANOI stone pages passed real headless Brave checks at 390px and 1440px: new image loaded, no horizontal overflow, no page errors. Their production screenshots were inspected.

New unpublished batches use AVIF quality 55 after the 177-photo build exceeded the unchanged 70 MB ceiling. Previously published WebP files are unchanged. Native PNG masters remain unchanged and preserved separately. Two clean fixture builds passed with AVIF-aware asset paths. Missing-file regeneration reproduced identical AVIF bytes; two initializations preserved all accepted asset hashes. Real local headless Brave checks passed at 390px and 1440px for wood and white doors: AVIF decoded, MIME type image/avif, no page errors or horizontal overflow. Representative screenshots were inspected.

Two SL207 metallic-walnut candidates were rejected for inventing vertical grid strokes. A third native render made from the higher-resolution original was inspected and accepted with the original four vertical strokes and sparse horizontal bars.

A read-only contact sheet helper compares source photos and native renders in four-product groups. It does not change either image. All eight images in the latest batch were inspected beside their original references before acceptance.

The 193-photo checkpoint, commit 679145df9cf66c91abe265047dc27e7e4fe081ab, deployed as f6bab7d8-abab-409e-a418-41f5f50395d2, finished 23:17:28 UTC. All fifty-one new assets for forty new reference URLs match production byte for byte. Production headless Brave checks passed for AVIF wood and white doors at 390px and 1440px: decoded images, image/avif MIME type, no page errors, no horizontal overflow. Representative production screenshots were inspected.

Four Model 132D1 native candidates were rejected because their embossed grid had more than the original ten rows. A fifth native edit from the original preserved exactly three columns and ten rows and was inspected and accepted.

The 209-photo checkpoint, commit 186b049c9c982c0b1453a11a94fd1026cb31dfd4, deployed as de64631d-5d15-4e1b-bdf0-c76896fa372a, finished 23:31:56 UTC. All 16 new assets for sixteen new reference URLs match production byte for byte.
