# NG Doors admin sizes and photos, 3 October 2026

Scope: per-product size labels and individual EUR prices, catalogue and owner-added products, public size selection, preserve unsaved edits during photo uploads, and the authorised ChatGPT replacement of all 1,638 product source-photo URLs.

## Verification

- Two clean runs each: `python test_admin_sync.py`, `node supabase/test_schema.mjs` (52 database checks), `python test_build_admin.py`, and `node test_admin_ui.mjs`.
- Browser tests render the real HTML, CSS and JavaScript at mobile and desktop widths. Supabase is explicitly mocked in those UI tests. Actual database validation and anonymous-write denial were tested separately with PGlite.
- Fixtures cover arbitrary size labels, distinct cent-accurate prices, one size, empty sizes, inherited catalogue prices, zero-price quotes, duplicate rejection, saved reload, owner-added products, wrong-password refusal, and retaining unsaved size edits across a photo upload.
- Live Supabase migration `owner_door_size_prices`, version `20261003191547`, applied successfully. Product and override row counts and content fingerprints were identical before and after (both tables currently empty). Existing RLS policies remain in place.
- The initial six-photo build using live Supabase data produced 1,037 pages and 961 product pages. `check.py` passed; public files weigh 67.6 MB (initial six-photo build), above the approximate 60 MB target and below the 70 MB ceiling.
- 1638 of 1,638 product source-photo URLs now use inspected native ChatGPT renders. 1102 native masters cover these URLs, including the initial aluminium, D, O, Z, T, KL, LCR and PVC entrance ranges. The M05/M06/M07 reference views share one accepted render after comparison; M05/M07 are exact image duplicates. Hardware, finish, panel design and frame were compared before acceptance. The 357 non-product image entries are unchanged. The pending ledger does not generate images automatically.

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

## Scope completed

All 1,638 product source-photo references have been replaced with reviewed native ChatGPT images. All 961 published catalogue products use generated cover and secondary images. The 357 installation gallery entries remain unchanged. Magic-link inbox delivery remains unverified; the direct password login was tested successfully.

Photo batch validation: final build and check pass at 60.4 MB public, with all 1638 replacement references resolvable. All 357 non-product image entries are unchanged from the original manifest. Reapplying the last image preserves its files after the source-key cleanup regression fix. Published sizes follow the existing catalogue resolution choices; native PNG masters remain available separately.

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

The 233-photo checkpoint, commit b6f6c4078008448939e6c76df1d66fbe1edff487, deployed as e1361a6f-ed3a-48da-bda6-9a3b18652e5a, finished 23:46:28 UTC. All 24 new assets for twenty-four new reference URLs match production byte for byte.

The new AVIF oak D3910 and stone-look FT013 floor pages passed actual headless Brave checks locally and on production at 390px and 1440px: image decoded, image/avif MIME type, no page errors and no horizontal overflow. Encoded color/grain comparisons and representative production screenshots were inspected.

The 249-photo checkpoint, commit ba20c6d14413cce167794e4d2624943362c6d7f5, deployed as 4c628a6c-37cf-4d60-bd5f-30e27a5e59a8, finished 23:59:35 UTC. All 18 new assets for sixteen new reference URLs match production byte for byte.

Actual owner Publish acceptance: two consecutive clean runs of live_publish_ui.mjs passed real password login, the real Publish button, HTTP 200 and the visible success message. Cloudflare deploy_hook builds on main completed successfully: 0e746607-758c-48f9-99ef-299e19dc0d0d at 00:12:32 UTC, 6e0293d2-a071-4f67-8e79-cd07edd0b4f0 at 00:16:58 UTC, and 7440b6c6-6523-4e26-961d-d4be3e4fa887 at 00:20:40 UTC on 4 October. The first test incorrectly checked a CSS class after a successful HTTP response; the check was corrected to the real data-state attribute. This was a test error. No app change was needed. The successful admin screen was inspected. Publish audit rows were kept. No product data was changed by these button checks.

The 273-photo checkpoint, commit c49a38c064922c557b695b2cf0ffc7eedad6e6af, deployed as 9434beee-be4a-4ac7-9921-55f60558cdba on 4 October. All 40 new assets for twenty-four new reference URLs match production byte for byte. Local build and checks passed at 68.3 MB public.

The 297-photo checkpoint, commit 6f876749e1af854fd42e67b74af0d6e072669986, deployed as 8a031403-12c3-4dde-a489-d5d41569f663, finished 00:54:39 UTC on 4 October. All 31 new assets for twenty-four new reference URLs match production byte for byte. Local build and checks passed at 67.2 MB public.

The 321-photo checkpoint, commit 2bdafe0664d1deed9287d429b4110044c70af2b2, deployed as 2d70d01d-c8ee-421b-b16e-13d9f766ee45, finished 01:08:02 UTC on 4 October. All 24 new assets for twenty-four new reference URLs match production byte for byte. Local build and checks passed at 67.6 MB public.

Wide hardware photos now use a compact 3:2 gallery frame. Portrait lock plates keep their tall frame. Two consecutive actual local Brave runs passed both products at 390px and 1440px, including a physical frame-height check. A first check failed because an edit to generated CSS was overwritten by the build. The source static/site.css was corrected and the rebuilt screens passed. Representative mobile wide-handle and desktop portrait-lock screenshots were inspected.

The 345-photo checkpoint, commit b884d0476c3e3da701370fa3cc17835e15c3861a, deployed as c0cf8c8f-fe4b-4e8b-8119-8aab6c04bd8e, finished 01:29:00 UTC on 4 October. All 32 new assets for twenty-four new reference URLs match production byte for byte. Actual production Brave checks passed the wide silver lever and tall brass lock plate at 390px and 1440px, including decoded AVIF, MIME, compact wide frame, no errors and no overflow. The production mobile wide-handle screenshot was inspected.

Two portrait ZEN handle candidates were withheld for excessive empty padding. Native edits reframed them into landscape photos while preserving the actual finishes and geometry; the corrected source comparisons were inspected and accepted.

The 481-reference local checkpoint finishes main photos for all 322 door-category listings and 139 of 639 flooring/trim listings. Sixty-one additional door source URLs are still pending. Every replacement was compared with its source. Two identical-source trim families reuse two native masters across 108 URLs after hashes matched at every encoded width. Mone80 914D and Mone55 860 candidates received native colour corrections before acceptance. All 357 installation-gallery image records remain unchanged.
The 481-reference checkpoint, commit 03b47be2ab62ee5da268bedb28bf8ae13f17c21c, deployed as df23c314-9d6e-4623-a45b-0fecf494ba04 at 01:58:32 UTC on 4 October. All 30 unique new public assets for 136 new source URLs match production byte for byte. Main photos for all 322 door-category listings are now published. Local build and checks passed at 67.5 MB public.
Production HTML for all thirteen newly updated door listings references the expected native assets. Checked alongside the 322-entry door catalogue.
The 613-reference checkpoint, commit a3fb17c698649bbd643efaaa34fc7fd34708efad, deployed as fc3ffafb-aef4-4513-9a43-92735548643c at 02:16:08 UTC on 4 October. All 24 unique new public assets for 132 new source URLs match production byte for byte. The two new corner shapes safely cover 110 source URLs after every available width matched. Local build and checks passed at 67.1 MB public.

Checkpoint 637: 24 additional native ChatGPT masters replace the next flooring references (B39 through B41). Each source and generated comparison was inspected for colour, grain, board layout, marble veining or hardware shape before acceptance. Clay and Navaho used additional actual product material references to remove room furniture without guessing the flooring. Build and catalogue checks pass at 67.1 MB public plus 0.62 MB admin. All 357 installation gallery files remain byte-for-byte unchanged. Full photo scope remains 1,638 references; no completion claim is made.

Production checkpoint 637 confirmed: Cloudflare deployment 3b7e7633-eecb-4ba1-b2dd-f6ab24b0c09b finished successfully at 2026-10-04T02:39:35.641543Z for commit 3d69512fc578bf08be0ce24ad5e8603909df9d41. All 24 unique newly published image assets were fetched from ngdoors.pages.dev and matched local bytes by SHA-256. This verifies 637 accepted source references from 421 native masters, including all 322 door-category primary photos and 295 of 639 flooring-category primary photos.

Checkpoint 662: 24 additional native masters replace 25 source-photo URLs (B42 through B44); one additional URL is an exact duplicate at every stored size. Reviewed new photos cover cable-channel skirting, aluminium transitions, cool grey and natural oak, and herringbone. Build and catalogue checks pass at 67.1 MB public plus 0.62 MB admin. Protected installation gallery remains unchanged.

Production checkpoint 662 confirmed: Cloudflare deployment a963be76-5f7d-41c1-831b-d19b5a92dfc8 finished successfully at 2026-10-04T02:54:56.0102Z for commit 5757b2ef031adbae237de343b3d269f5e1084156. All 24 unique newly published image assets were fetched from ngdoors.pages.dev and matched local bytes by SHA-256, covering 25 new source references. All 322 door-category primary photos and 320 of 639 flooring-category primary photos are now native renders.

Production checkpoint e56105aec2f24b5caa4f53aa200456c530770aab: 691 accepted source-photo references from 469 native masters. Cloudflare deployment d0d386cf-b0f9-4f4b-aabc-b6c4d21820ed succeeded at 2026-10-04T03:15:34.889589Z. All 24 unique new generated assets covering 29 new source references were fetched from ngdoors.pages.dev and SHA-256 matched the local files. Build and checks passed at 67.2 MB public plus 0.62 MB admin. Original references and native outputs were visually compared; 357 installation gallery photographs remain unchanged.

Visual review rejected the first EL2151 107 beech transition render as too orange. A second native ChatGPT edit used the actual original and rejected candidate to restore the muted pale honey/tan beige finish. The corrected render was compared beside the original and accepted. The rejected candidate was not applied.

Production checkpoint c5105e214d819f0b0fc1a12de1ec6da551f9c1ea: 757 accepted source-photo references from 493 native masters. Cloudflare deployment 882c832a-6a66-46dc-a85e-d4eb31cd2895 succeeded at 2026-10-04T03:29:16.451898Z. All 24 unique new assets covering 66 source references were fetched from ngdoors.pages.dev and SHA-256 matched local files. Build and checks passed at 67.1 MB public plus 0.62 MB admin.

Checkpoint 801: native product photographs from batches 51-53 passed visual comparison against the real sources. Build/check pass at 67.0 MB public plus 0.62 MB admin. Production commit a4e201799f9776da3a84f6d3f81c53743cad9be2 deployed successfully as Cloudflare deployment 6a9f05cd-e0f6-44e4-b97f-fb30287da898 at 2026-10-04 05:34:39 UTC. Live file hashes are checked separately below.
Live verification at checkpoint 801: all 24 new encoded image files covering 44 newly accepted source references matched production bytes by SHA-256. Orca status sent to Claude; no peer acknowledgement has been received.

Checkpoint 855: batches 54-55 visually matched the actual T, L and curved transition profiles, including colour and flange orientation. Build/check pass at 67.0 MB public plus 0.62 MB admin. Commit d6c30cd131a1eed5ccbea9500d2f864fae7a2f37 deployed successfully in Cloudflare deployment 6a1f2915-f185-4d96-bd88-9741ecad8e9d at 2026-10-04 05:43:28 UTC. All 32 new encoded files covering 54 newly accepted source references matched production bytes by SHA-256.

Checkpoint 887 / 1038 native masters: production commit 03fc5d1b537392f36549291c94a19b41a196d5b5, Cloudflare deployment 4aa6cc3d-a63e-4bf6-be87-cad3c89fcc76 succeeded 2026-10-04T08:01:51.444885Z. All 32 new source-photo references resolve to 32 unique assets fetched from ngdoors.pages.dev and SHA-256 matched to local files. Build and checks passed at 67.0 MB public plus 0.62 MB admin.

Checkpoint 922 / 1038 native masters: production commit 7dd59208ba7ec8998a1947e18321ee2b80ddb15b, Cloudflare deployment 26d7d0fe-d2e0-4965-990a-8a0c7289170c succeeded 2026-10-04T08:13:27.011302Z. All 35 new source-photo references resolve to 32 unique assets fetched from ngdoors.pages.dev and SHA-256 matched to local files. Build and checks passed at 66.9 MB public plus 0.62 MB admin.


Photo checkpoint 954: batches B60 and B61 added 32 native ChatGPT product photographs. All 32 were compared with their actual originals, including the close-up material references for room photographs. Review confirmed the 55mm skirting extrusion, wood grain, finish and colour. Plain white skirting remains plain white. Build and checks pass at 66.8 MB public plus 0.63 MB admin. The installation gallery remains unchanged.


Live checkpoint 954: Cloudflare deployment 1cf4e240-3ef9-4b26-9da9-9c7a3646cc95 completed successfully at 2026-10-04T08:33:56.462437Z for commit 28a590e7ce672590b7fd008721aa32b829e2b403. All 32 newly published source references resolve to 32 generated files whose live bytes match the reviewed local files by SHA-256.


Photo checkpoint 982: B62 and B63 added 25 reviewed native masters covering 28 source-photo references, including exact duplicate reuse. All 961 public catalogue items now have reviewed ChatGPT cover photographs: 322 of 322 door and hardware items, and 639 of 639 flooring and trim items. Actual material close-ups were used for room references. Chevron retained its mitred V joints. The 80mm skirting retained its two cable channels, separate mounting insert and correct plain or wood finish. All new comparisons were visually reviewed before acceptance. Build and checks pass at 66.8 MB public plus 0.63 MB admin. Secondary photographs remain pending.

Checkpoint 982: commit b7c0f5bc021ce33b3e7836db517355bc32cb7881 deployed successfully as Cloudflare production 50313bc7-a7c0-4de4-9e71-053cad1e1523 at 2026-10-04T08:48:31.650347Z. All 961 of 961 public catalogue cover photos are reviewed and deployed (322 doors and hardware, 639 flooring and trim). All 28 newly accepted references resolve to 25 native generated assets; all 25 deployed files were fetched and byte-matched to their committed local files using SHA-256.

Checkpoint 1014: commit 6dc72ec92c457dd8e23644fda0a31c3d36df823f deployed successfully as Cloudflare production b2a036f0-8f81-42ed-a2d2-af7cea5ae33f at 2026-10-04T09:04:59.88681Z. SHA-256 verification from the last proven checkpoint 954 to 1014 fetched and byte-matched 57 unique deployed image files covering 60 newly accepted source references. Checkpoint 1014 build/check passed at 67.0 MB public and 0.63 MB admin; the earlier headline weight of 66.8 MB was stale. Batches 66 and 67 add 32 native masters. Exact shared-source reuse applies the identical MONE accessory pack image to 218 source URLs only after all encoded reference widths match, bringing the accepted total to 1263 of 1638 and 734 native masters. All remaining door secondary photos have now been reviewed.

Checkpoint 1263: commit 7f8d2a632102c0b80c3179e41a1228f802a44638 deployed successfully as Cloudflare production fdbc5065-3496-428c-97f7-a24e49f6c666 at 2026-10-04T09:13:27.671217Z. All 249 newly accepted source references are served by 32 new native image files; all 32 fetched deployed files byte-match their local files by SHA-256. Build/check pass at 61.2 MB public and 0.63 MB admin. All doors and hardware secondary photos are reviewed and live. There are 375 pending flooring room/detail source references.

Production checkpoint 1311: commit 1173ae401feaaba5fa275fb5d57e2582576a01ee, Cloudflare fab3a9ef-27db-4f1c-89df-76c32d4672a5 succeeded 2026-10-04T09:34:53.806646Z. All 48 newly replaced source references / 48 encoded files byte-matched production with SHA-256. 782 native masters. Build and checks pass at 61.4 MB public + 0.63 MB admin; unchanged 70 MB hard cap. 327 source references remain. B68-B69 all 12 comparison sheets visually inspected before acceptance.

### Flooring checkpoint 1,375 - production proof

Commit faa3e8a69a39bcc1f8c514c7663476af8e52185a deployed successfully in Cloudflare 70acb5ba-1178-444c-925a-0052c64b9dca at 2026-10-04T09:57:52.565823Z. All 64 new photo references and their 64 encoded files matched the local SHA-256 bytes. Build and checks passed at 61.6 MB public plus 0.63 MB admin. 846 native masters replace 1,375 of 1,638 source-photo URLs; 263 remain. Batch 70 and 71 were checked in all sixteen comparison sheets before application. All 357 installation photos remain unchanged.

Production photo checkpoint 1439: commit 2920a51c9855ecf2e593b0af2d097c30dbecd563 deployed successfully as Cloudflare 6e8022c6-561e-420c-93e3-48e654082615 at 2026-10-04T10:15:40.73752Z. All 64 new photo references and 64 encoded files were downloaded from the production domain and matched local SHA-256 byte for byte. The checked build is 61.4 MB public plus 0.63 MB admin, with 910 native renders and 199 source photos pending.

Production checkpoint 1503/1638: commit 2691c4b9c9ae532b0d680b72c2fab5638fd531e1, Cloudflare deployment 31f1aeb0-108f-4e9d-a0b5-61c5ccfe2ec0 succeeded at 2026-10-04T10:34:28.294244Z. All 64 newly replaced source references and 64 encoded assets byte-match production. Public bundle 61.1 MB plus 0.63 MB admin; 357 installation gallery photos unchanged.

Production checkpoint 1568/1638: commit 783cf98f014780f9af0b31cb67b42578036cc812, Cloudflare deployment 98859c9f-8dd3-4d7d-b430-b6a1be8bd3bf succeeded at 2026-10-04T10:56:10.604764Z. All 65 newly replaced source references and 64 encoded assets byte-match production. Public bundle 60.7 MB plus 0.63 MB admin; 357 installation gallery photos unchanged.

Final local acceptance: 1,638 of 1,638 source-photo URLs are accepted, with zero pending. The final batches added 64 reviewed native masters, covering 70 references through exact duplicate reuse. A loft flooring candidate was rejected for showing staggered herringbone. Its native correction has the original mitred chevron joints and continuous straight spines. All final comparison sheets were visually reviewed. Build and checks pass at 60.4 MB public plus 0.63 MB admin, below the unchanged 70 MB ceiling. All full native PNGs remain preserved separately.

## Final production proof, 4 October 2026

Commit `f57f18df0ee626a4ae175205042925eeb2a760f7` deployed successfully as Cloudflare production `bf39ec5d-7023-44ef-a948-ee3a0efc3809`, finished `2026-10-04T11:17:00.484051Z`. All 1,171 distinct encoded product image files were downloaded from `https://ngdoors.pages.dev` and matched their reviewed local files by SHA-256. This covers all 1,638 accepted source-photo references, 1,102 preserved native ChatGPT masters, and all 961 published catalogue products. There are zero pending product references. The final checkpoint adds 70 references and 64 encoded assets.

The final production flooring and trim pages passed actual headless Brave checks at 390px and 1440px, including every thumbnail, AVIF decoding, correct selected-gallery state, no horizontal overflow and zero page errors. All four production screenshots were visually inspected. Earlier production acceptance proved owner password login, photo upload, per-size price save and reload, database rejection of invalid prices, anonymous-write prevention, and the actual Publish button. The existing locked desktop tab was not used as render proof. Email-link inbox completion is still unverified; direct password access works.

Owner flow: open `/admin/`, sign in, select a door, enter each size label with its own EUR price, save, then click **?????????? ?????????**. The public size picker shows the selected row's price. The build normally finishes in about three minutes. Full photo masters remain at `C:/Users/Win11/Desktop/Claudes Workspace/Outputs/ngdoors-product-renders`.
