# Individual catalogue photo removal

The owner can now remove each existing catalogue photograph from a product. Previously, only uploaded photographs had a removal button. The complete original gallery now appears in the admin panel, each with an accessible “Изтрий снимка” button.

## Behaviour

- Removing a photograph saves that product's exclusion list. Other products using the same photograph are unaffected.
- Removing the last photograph leaves the product available, with “Снимка не е добавена” in its image area.
- “Върни каталожните снимки” restores the original gallery without resetting price, size, badge or visibility edits.
- Uploaded replacements retain their existing replacement behaviour. Deleting the last upload leaves an empty gallery instead of silently restoring old photographs.
- Failed writes keep the current gallery and allow a retry. Photo changes preserve unsaved form values. Photo uploads, saves and resets cannot overlap within a row.
- Changes reach public pages through the existing “Публикувай промените” workflow.

## Implementation and deployment order

Worktree: `C:/Users/Win11/orca/workspaces/New-folder/ngdoors-delete-photos`, branch `ngdoors-delete-photos`, based on `5415cc37`.

1. Apply `supabase/excluded_images.sql` to the existing Supabase project. This adds a validated JSON array column with an empty default; it does not remove existing rows or files. The complete setup schema includes the same migration.
2. Publish the changed builder, admin script, generated catalogue and `static/no-photo.svg` together. The checked-in `site/` output was rebuilt from current public Supabase data after all fixture tests.
3. Verify the real signed-in owner flow: remove one original, reload, publish, check its product page, and restore if the change was only a verification action.

The migration must precede the updated panel. Original catalogue files remain available for shared products and restoration. This is per-product removal, not permanent erasure of a shared asset URL.

## Evidence

On 2026-10-07, both live `/admin/admin.js` and `/admin/index.html` returned HTTP 200 and their SHA-256 values exactly matched this branch's unmodified base. The fix therefore starts from the currently deployed admin implementation.

- Regression before the implementation: `python test_build_admin.py` failed eight new photo assertions, including removal, deleting the last image and missing individual admin photographs.
- `python test_build_admin.py`: ALL PASS after the implementation. Exercises actual generated door and floor pages, unchanged photo order, last-photo removal, retained products, restoration source data, and existing size/price behaviour. Includes the full `check.py` site check.
- `node supabase/test_schema.mjs`: ALL 66 PASS. Executes real PostgreSQL through PGlite with mocked Supabase auth/storage schemas. Covers schema/migration idempotence, admin writes, anonymous/non-admin restrictions, malformed exclusion arrays, public build reads and restoration.
- `python test_admin_sync.py`: ALL PASS, including preservation of exclusions through the actual publishing data loader.
- `node test_admin_ui.mjs`: PASS in fresh headless Brave sessions, including consecutive clean runs. Uses an explicitly mocked Supabase service. Exercises individual original removal, the last photo, reload persistence, rejected saves, recovery, restoration, uploaded-image deletion and preservation of size edits.
- Browser checks at 390, 768 and 1440 pixels: no horizontal overflow, loaded original thumbnails and no JavaScript page errors. Images: `verification/admin-photo-delete-390.png`, `verification/admin-photo-delete-768.png`, `verification/admin-photo-delete-1440.png`, and `verification/product-no-photo-390.png`.
- Final `python build.py` read production data successfully: 961 products, 1,037 pages and 357 gallery photos. `python check.py`: ALL CHECKS PASS. The existing advisory size warning remains: 60.4 MB versus the approximate 60 MB target.
- Source `git diff --check`: clean. Production output changes are limited to the admin script/catalogue and the added empty-photo asset.

## Review boundaries

Bad results explicitly checked: a removed photo returning after reload or publishing; deletion hiding the whole door; resetting unrelated price/size edits; deleting a shared original from storage; and a failed save falsely removing its thumbnail.

The strongest reason against immediate deployment is the new database dependency: deploying the panel without first applying the migration makes photo saves fail. The migration is ready and tested locally, but has not been applied to production.

Not verified: real owner-authenticated production deletion, production storage removal, or a production publish containing the new exclusion field. These require the deployment and a real owner session. Mock browser persistence is not production persistence proof.

Unrelated work left alone: authentication, the publish service, catalogue photography, prices, and public navigation. Screenshot capture now finishes CSS animations to avoid capturing the existing mobile navigation halfway through a viewport transition.

Local implementation and checks are ready. Production deployment awaits the owner's explicit approval under the saved deployment instruction.
