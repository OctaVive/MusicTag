# Implementation status

The product plan in `musictag-v1-plan.md` remains the target specification. This file separates working functionality from remaining release work; the original proposed plan has not been overwritten.

## Implemented

- Django 5.2 scaffold, migrations, SQLite WAL, environment settings, loopback setup, vendored HTMX 2.0.8/Alpine 3.14.9, offline static serving, CI configuration, Docker configuration.
- All specified data models, canonical field registry plus script, MP3/FLAC/WAV read/patch adapters, raw tag inspector, technical information, artwork cache/renditions and conditional requests.
- Incremental background scans, startup scan, orphan cleanup (not on cancelled/incomplete walks), read-error indexing, album materialization, quality issue computation.
- Album grid/detail, indexed folder navigation, paginated tracks, URL search/filters/sort, shared inspector, selection and mixed-value bulk forms.
- Dirty-only save/revert, multi-value chips, write lock on UI/server, validation, full-file copy backups, fingerprint guards, verification, failure restoration, integrity-checked undo/redo, explicit crash-recovery command.
- Cover replacement/removal, folder image import, original-cover download, bulk cover preview/apply, CAA candidate selection and import.
- Signed expiring bulk previews, per-field Replace/Add/Remove/Clear, no-op skipping, asynchronous apply, cancellation between files, partial failure reporting, retry of failed plans, large-batch confirmation.
- Filename parser/custom patterns, numbering by album/folder/disc, totals/discs, named presets (upsert/delete/apply), quality issue navigation/bulk editing, MusicBrainz release search/detail/matching and field inclusion.
- Persistent player/queue, context queues, Range/suffix Range streaming, shuffle/repeat, Media Session handlers, theme/accent/density preferences, desktop/narrow shell, shortcuts help and common shortcuts.
- Scan/worker/cache/GC/recovery commands; retention protects both latest 200 and newer-than-30-day history.
- Generated playable silence fixtures, three-format canonical matrix tests, rollback/undo/drift tests, scanner/path tests, view/CSRF/range tests, mocked network tests, optional real Chromium smoke script.

## Remaining implementation/polish from the plan

- Inline table quick-edit, optional persisted table columns, full row context menus, OS reveal-folder integration, and finer keyboard-map details. Shift+arrow selection and confirmed `Ctrl+Z` undo are implemented.
- Album density control, comprehensive facet counts/filter chips, sort-cycle UI, richer folder counts/thumbnails and subtree actions, skeletons, and fine-grained focus restoration/field-specific error placement. Form failures are currently shown in a modal with entered values preserved.
- Direct export of artwork **into** the library folder is intentionally not implemented: export is a browser download, avoiding untracked sidecar writes. Bulk cover reuse from another indexed album is not yet a dedicated UI action.
- Album/folder tables and track/quality pages are server-paginated; folder subtree selection/play controls are still limited to indexed context filters.
- Full preset editing UI (existing names are updated by saving from the bulk editor), numbering sort controls, and automatic Windows-busy retry. Single-save events now refresh the current library view.
- Job topbar indicators are initial-render snapshots; live progress is on each job screen. Interrupted operations require the documented recovery command rather than an automatic recovery UI.
- Album aggregates currently rebuild globally after single saves and once after each batch. This needs an incremental affected-album pass before claiming the single-save/50k-library performance budgets.
- Default ID3v2.4 is matrix-tested; v2.3 compatibility needs a broader interoperability matrix and version-specific capability hints for lossy fields.
- Metadata lookup candidates open image previews in a new tab; no in-app candidate thumbnail gallery yet. Matching must still be reviewed manually. Cover-only lookup currently requires a metadata field to be selected as well.
- Granular CSS/JS/view modules and inline SVG icon sprite from the suggested layout are not fully adopted; the current implementation uses consolidated CSS/views and text symbols. Alpine is vendored but the implemented client interactions are vanilla modules.
- MP4/M4A/M4B and OGG/Opus intentionally deferred to **v1.1**, per confirmed scope (despite the plan's later M6 milestone listing them).

## Verification boundaries

Verified locally on Windows/Python 3.13: Django checks/migrations, lint, unit/integration tests, and Chromium end-to-end smoke using isolated copied fixtures. The browser smoke covers the real scan worker, tag save, bulk preview/apply, undo, playback endpoint wiring, and 1024/1920px shell sizing.

Not yet verified: actual CI runs on Linux/Python 3.12, Docker execution, full keyboard-only/assistive technology audit, Firefox/OS media keys, external-player metadata interoperability, Windows locked-file integration, and timed 5k/50k performance datasets. The v1.0 definition of done is **not yet fully met**; use a separately backed-up library while completing release validation.
