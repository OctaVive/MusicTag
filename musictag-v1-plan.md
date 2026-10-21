# MusicTag v1 — Product & Implementation Plan

**Status:** proposed greenfield plan
**Date:** 2026-10-21
**Starting point:** empty project. No code, schema, templates, or runtime state from any earlier implementation is reused. Music files are the only imported data, discovered by scanning.

**Confirmed direction:** local web app · Django server-rendered · complete UI redesign · hybrid album-art + track-table browser · expanded tag set.

---

## Contents

1. Product definition
2. Users and core workflows
3. Scope
4. Experience design
5. Tag system
6. Architecture
7. Data model
8. Server routes
9. Project layout
10. Design system
11. Build milestones
12. Testing and quality
13. Performance budgets
14. Risks
15. Decisions and assumptions
16. Definition of done

---

## 1. Product definition

MusicTag is a local-only web application for browsing a music library and editing the metadata embedded in audio files. It is built for people who keep their music as files and folders, and who need to correct or complete tags in bulk without risking their library.

**The product promise:** *safe, fast metadata editing over a real folder of music, with every change previewable and reversible.*

### Success criteria

- Open the app, scan a 20,000-track library, and find any album in under 5 seconds.
- Fix an entire album's artist, album artist, year, genre, and cover in under a minute.
- Edit a single track's tags and save without leaving the keyboard.
- Every write is previewable (for batches), validated, backed up, and undoable.
- Nothing outside the configured library root can be read or written.
- The app works fully offline and installs with `pip install -r requirements.txt`.

### Product principles

1. **Files are the source of truth.** The database is an index; tags live in the files. Deleting the DB must never lose metadata.
2. **Preview before write.** Bulk operations produce a concrete before/after diff; nothing is written until the user confirms.
3. **Explicit saves.** No silent background tag changes. Dirty state is visible.
4. **Reversible by design.** Every write records before/after tags and covers in a multi-level undo history.
5. **Server-rendered, locally owned.** HTML from Django, fragment updates with HTMX, no SPA build chain, no CDN, no telemetry.
6. **Boring, durable tech.** Python, Django, SQLite, mutagen, Pillow. One process, one database, predictable behavior.
7. **Density over decoration.** The UI is a tool: readable tables, strong keyboard support, restrained color.
8. **Format-aware, not format-blind.** Fields that a format cannot store are disabled with an explanation rather than silently discarded.

---

## 2. Users and core workflows

### Primary user

A local music collector with roughly 1,000–50,000 audio files across albums, compilations, and loose tracks. They know their folder structure, care about correct album artist/date/cover data, and occasionally need to repair messy download sets. Single user, single machine, no account.

### Core workflows

| # | Workflow | Outcome |
|---|---|---|
| 1 | **Onboard** — choose library folder, scan, review summary | Library is indexed and browsable |
| 2 | **Browse by art** — album grid, filters, album detail | Find an album visually, see quality issues |
| 3 | **Browse/filter tracks** — dense table, search, facets | Find problem tracks quickly |
| 4 | **Edit one track** — inspector, change fields, save | Tags and cover updated |
| 5 | **Bulk edit a selection** — mixed values, per-field apply, preview, apply | Consistent album/artist data across many files |
| 6 | **Fix covers** — replace/remove/import from folder, album-wide | Consistent artwork |
| 7 | **Repair filenames** — parse patterns into artist/title/track | Untagged download sets become usable |
| 8 | **Renumber** — track/disc numbers, totals, scope | Albums play in order |
| 9 | **Audit quality** — missing tags/art, duplicate numbers, inconsistent albums | Actionable issue list with bulk fixes |
| 10 | **Look up metadata** — MusicBrainz release search, cover candidates, field-by-field apply | Complete album metadata from a trusted source |
| 11 | **Audition** — play a track/album while editing | Confidence before writing |
| 12 | **Recover** — undo a mistaken batch | Files restored |

---

## 3. Scope

### v1.0

- **Library:** configurable root, background scan/index, incremental rescan, album/track/folder views, global search, filters, sorting, pagination.
- **Formats:** MP3 (ID3v2.3/2.4), FLAC, WAV (ID3 chunk).
- **Tags:** the expanded canonical set in §5, with multi-value support and per-format capabilities.
- **Editing:** single-track inspector, explicit save/revert, validation, cover replace/remove/export/import, lock guard.
- **Bulk:** explicit selection, per-field apply with multi-value operations, server-generated preview diff, background apply job with per-file results, cancel, retry-failed.
- **Safety:** operation history with multi-level undo (tags + covers), backup-before-write, verify-after-write, path containment.
- **Tools:** filename parser, auto-numbering, presets, quality report, MusicBrainz + Cover Art Archive lookup, history.
- **Player:** persistent bottom bar, queue from the current view/album, seek, volume, shuffle/repeat, Media Session.
- **Shell:** onboarding, settings, light/dark/system themes with three accents, keyboard shortcuts, operation log, toasts.
- **Delivery:** local development server, optional Docker, loopback binding, docs.

### v1.1 (planned after v1.0 is stable)

- MP4/M4A/M4B and OGG/Opus adapters (registry-driven, same test matrix).
- Additional artwork roles (back, booklet, artist).
- Optional filesystem watcher for automatic rescans.
- FTS5-backed search if `LIKE` stops meeting latency targets.
- Saved filter views.

### Explicitly out of scope

- Accounts, multi-user sync, public internet hosting.
- Streaming/transcoding server, remote clients, mobile apps.
- Playlists, scrobbling, recommendations.
- Duplicate-file deletion, audio fingerprinting, automatic BPM/key detection.
- Lyrics or artwork downloading beyond the explicit MusicBrainz/CAA lookup.
- Renaming or moving files (kept separate because it changes undo and safety semantics).

---

## 4. Experience design

### 4.1 Application shell

```
┌────────────────────────────────────────────────────────────────────────────┐
│ MusicTag   Library ▾   [ Search…                              ]  Scan · 🔒  │
│                                                         theme · settings    │
├───────────┬────────────────────────────────────────────────┬───────────────┤
│ Albums    │  MAIN VIEW                                     │ INSPECTOR     │
│ Tracks    │                                                │               │
│ Folders   │  Albums: cover grid                            │  ┌─────────┐  │
│           │  Tracks: dense table                           │  │  cover  │  │
│ Filters   │  Folders: lazy tree                            │  └─────────┘  │
│ ───────   │                                                │  Title        │
│ Format    │                                                │  Artist       │
│ Has art   │                                                │  Album        │
│ Missing   │                                                │  … advanced   │
│ Issues    │                                                │               │
│           │                                                │  Save Revert  │
├───────────┴────────────────────────────────────────────────┴───────────────┤
│ ▶  cover · Title — Artist · Album   ⏮ ▶ ⏭   ──────●────  2:41 / 4:05  🔊  │
└────────────────────────────────────────────────────────────────────────────┘
```

- Three panes: navigation rail, main view, inspector.
- The rail collapses to icons; the inspector collapses or overlays at narrower widths.
- Main view and inspector scroll independently; the player and top bar are fixed.
- All navigation is URL-driven (`?view=tracks&q=…&sort=artist&page=2`), so refresh, bookmarking, and back/forward work.
- The interface is desktop-first (target 1280–1920px), usable at 1024px, single-column below 900px.

### 4.2 Top bar

- **Search:** global, debounced (200 ms), matches title, artist, album artist, album, genre, catalog number, filename; `/` focuses it.
- **Scan control:** shows idle / scanning (processed/total) / last scan age. Opens a scan panel with cancel and rescan.
- **Lock:** clearly labeled `Writes enabled` / `Writes disabled`; unlocking requires an explicit click and shows a warning banner while writes are enabled.
- **Theme:** light / dark / system toggle plus accent palette (indigo, teal, amber).
- **Settings** and **Undo history** entry points.

### 4.3 Navigation rail

- View switcher: **Albums**, **Tracks**, **Folders**.
- Filters that compose across views: format, has cover, missing fields, issue type, folder, year/decade, genre, artist.
- Active filters shown as removable chips; a "Clear all" action.
- Counts next to filters, from indexed data.
- Library root path at the bottom with a settings link.

### 4.4 Albums view

- Responsive cover grid (default 6 columns at 1440px; density control).
- Card: cover (lazy, cached rendition), album title, album artist, year, track count, duration, issue badge.
- Sorting: artist, album, year, recently added, issue count; direction toggle.
- Filters: artist facet, genre, decade, format, missing art/issues.
- Actions: open detail, play album, add all tracks to selection.
- Empty state explains how to scan; loading state uses skeleton cards.

**Album grouping rule**
- Key = normalized album artist (casefolded, trimmed, punctuation-light) + normalized album title.
- Tracks with an album but no album artist group under the album artist if consistent, otherwise under the folder with a "Compilation" treatment.
- Tracks with no album group under "Unknown album", keyed by folder.
- Grouping is recomputed on scan and after writes that touch album fields.

**Album detail**
- Header: large cover, album/album artist/date/genre/label/catalog/release type, total duration, issue summary.
- Track table for the album with disc/track columns.
- "Edit album fields" opens a bulk-style editor that applies selected fields to all tracks with preview.
- Cover actions: replace all, remove all, export to folder, use folder image.

### 4.5 Tracks view

- Server-paginated table, 100 rows/page default, with sticky header and "Load more" or page navigation.
- Default columns: Disc/Track, Title, Artist, Album, Year, Genre, Duration, Format, Issues.
- Optional columns: album artist, track total, disc total, composer, BPM, key, comment, bitrate, sample rate, path. Choice persisted per user in `localStorage`.
- Sortable indexed columns, multi-sort (asc → desc → none), URL state.
- Inline quick edit on double-click or `Enter` for: title, artist, album, album artist, year, genre, track, disc. Advanced fields open the inspector.
- Row states: normal, hover, selected, playing, dirty, error, locked.
- Selection: row checkbox, `Ctrl/Cmd+click` toggle, `Shift+click` range, `Select all filtered`.
- Row context menu: play, edit, select album, copy path, reveal folder, set/remove cover, undo last change for track.
- Keyboard: `j`/`k` move, `Enter` edit, `Space` play, `Esc` clear.

### 4.6 Folders view

- Lazy tree: each expansion requests one level from the index, not the disk.
- Folder row: name, track count, cover thumbnail, issue count.
- File row: name, title/artist summary, duration, format, cover thumbnail.
- Actions: play folder, select all tracks below, rescan folder, import folder cover.
- Selecting a file loads it in the inspector and player without altering an existing bulk selection.

### 4.7 Inspector — single track

Sections (collapsed state remembered):

1. **Artwork** — preview, replace, remove, export, use folder image.
2. **Track** — title, subtitle, artists, track/disc number + totals, BPM, key, ISRC.
3. **Release** — album, album artists, date, original date, release type/status, media, label, catalog number, barcode, copyright.
4. **Credits** — composers, conductor, lyricist.
5. **Classification** — genres, mood, language, script.
6. **Notes** — comment, lyrics.
7. **Sort names** — title, artist, album, album artist.
8. **ReplayGain** — track/album gain and peak.
9. **Identifiers** — MusicBrainz track/release/artist/album artist/release group/work IDs, AcoustID.
10. **File** — path, format, duration, bitrate, sample rate, channels, size, modified time.
11. **Raw tags** — collapsible, read-only debug view of everything read from the file.

Behaviors:
- Multi-value fields use chip inputs: Enter/comma adds, Backspace removes, paste splits on `;` and newlines.
- Dirty fields are marked; header shows `Unsaved changes` and Save is enabled.
- Save (`Ctrl+S`) submits only dirty fields; Revert restores the last read values.
- While locked, inputs are read-only, Save is disabled, and a banner explains why.
- Field-level validation is inline; server validation errors are attached to fields.
- A failed save leaves values intact and reports the reason.
- Navigating away with unsaved changes prompts for confirmation.
- A track that fails to parse shows a read error with the file path and does not crash the view.

### 4.8 Inspector — multi-selection (bulk)

- Shows a shared value, or **Mixed** when values differ, for every field.
- Each field has an include checkbox and, for multi-value fields, an operation: **Replace**, **Add**, **Remove**, **Clear**.
- Smart initial state: album/album artist/year/genre included; title/track/disc/artist/composer excluded; everything advanced excluded. If all selected tracks share a value, that value is prefilled.
- A sticky bulk bar summarizes: `N tracks · M fields · K changes`, with **Preview**, **Apply**, **Select none**.
- **Preview** generates a server-rendered diff: per file, current → proposed, with no-op files, conflicts, and validation failures called out. A preview token captures each file's tag fingerprint; apply refuses files that changed since preview unless the user confirms.
- **Apply** enqueues a job: real progress, cancel between files, result list with failures and **Retry failed**.
- Applying to more than 20 files requires an explicit confirmation.
- Bulk cover changes are part of the same flow (upload, reuse album art, or remove).

### 4.9 Tools

| Screen | Functionality |
|---|---|
| **Filename parser** | Token templates like `{track} - {artist} - {title}`, separator normalization, built-in presets, saved custom patterns, live preview table, apply through the standard preview/apply pipeline. |
| **Auto-numbering** | Options: start, pad width, scope (folder/album/disc), write totals, sort by filename or index order, renumber discs. Preview then apply. |
| **Presets** | Named sets of field values/operations. Create from the current editor or selection, edit, delete, apply with preview. |
| **Quality report** | Filters by issue type/album/folder. Issues: missing title/artist/album/album artist, missing cover, duplicate track numbers, inconsistent album artist/year/genre within an album, missing track/disc numbers, read errors. Row links open the track/album; bulk fixes for the common cases. |
| **Metadata lookup** | MusicBrainz release search; release detail with track list; Cover Art Archive candidates; automatic track matching by number → duration → title; field-by-field preview; apply selected fields; 1 request/second throttle and offline-safe errors. |
| **Undo history** | Every write operation with timestamp, kind, counts, affected files; restore any operation (tags + covers); prune by age/count. |
| **Settings** | Library root, rescan, formats, ID3 version preference, cover size limit, write-confirmation threshold, MusicBrainz contact, theme/density, cache maintenance. |

### 4.10 Player

- Fixed bottom bar: cover, title, artist – album, previous/play/next, seek with elapsed/total, volume, shuffle, repeat, queue.
- Queue is built from the context that started playback: album detail, current filtered track list, folder, or selection.
- Auto-advance on end; repeat all/one; shuffle keeps the current track first.
- Real HTTP Range streaming so seeking is immediate and reliable.
- Media Session metadata/controls for OS media keys.
- Persists volume, repeat/shuffle, and the last queue; does not auto-play on startup.
- Keyboard: `Space`, `Shift+←/→` for tracks, `←/→` seek 5 s, `↑/↓` volume, `M` mute.

### 4.11 Feedback and safety

- Toasts for every action; long operations also write to an **operation log** with per-file details.
- Job progress is real (processed/total), never simulated.
- Locked writes are blocked in the UI and the server.
- Destructive batch actions require confirmation.
- Errors never clear the form or hide the cause.
- Every successful write creates an undo entry before the next action can start.

### 4.12 Keyboard map

`/` search · `g a` albums · `g t` tracks · `g f` folders · `j/k` next/previous row · `Shift+↑/↓` extend selection · `Enter` edit · `Space` play · `Ctrl+S` save · `Ctrl+Z` undo last operation · `Esc` close/clear · `?` shortcuts.

### 4.13 Theming and visual language

- Neutral surfaces, one accent, minimal gradients; content (art, titles, numbers) carries the interface.
- Light, dark, and system modes via `data-theme`; three accent options via `data-accent`; applied before first paint.
- System font stack; 13px table text, 14px form text, tabular numerals for track/duration.
- Compact density (32px rows) and comfortable (40px), switchable.
- Inline SVG sprite for icons; no icon fonts or external assets.
- Focus rings, 4.5:1 contrast, aria-live for job/toast updates, keyboard-operable chips and menus, reduced-motion support.

---

## 5. Tag system

### 5.1 Canonical registry

A single Python registry defines every supported field: key, label, group, data type, whether it is multi-value, whether it appears in quick edit, which formats support it, and the per-format mapping. Views, forms, templates, validation, lookup, previews, and tests all read from this registry.

**Core fields**

| Field | Type | Multi | Notes |
|---|---|---|---|
| `TITLE` | text | no | Required by UI convention; empty allowed but flagged |
| `SUBTITLE` | text | no | |
| `ARTIST` | text | yes | First value used for display/sort |
| `ALBUMARTIST` | text | yes | Drives album grouping when present |
| `ALBUM` | text | no | |
| `TRACKNUMBER` | int 0–9999 | no | |
| `TRACKTOTAL` | int 0–9999 | no | Normalized per format |
| `DISCNUMBER` | int 0–9999 | no | |
| `DISCTOTAL` | int 0–9999 | no | |
| `DATE` | date | no | `YYYY`, `YYYY-MM`, `YYYY-MM-DD` |
| `ORIGINALDATE` | date | no | |
| `GENRE` | text | yes | Autocomplete from library values |
| `COMPOSER` | text | yes | |
| `COMMENT` | long text | no | |
| `LYRICS` | long text | no | |
| `BPM` | decimal 0–999 | no | |
| `KEY` | text | no | |
| `LANGUAGE` | text | no | ISO 639 hint |
| `MOOD` | text | no | |
| `ISRC` | text | no | 12-char warning |
| `LABEL` | text | no | |
| `CATALOGNUMBER` | text | no | |
| `BARCODE` | text | no | Digits warning |
| `MEDIA` | text | no | e.g. CD, Digital Media |
| `RELEASETYPE` | text | no | Album, EP, Single, Compilation |
| `RELEASESTATUS` | text | no | Official, Promotional, Bootleg |
| `COPYRIGHT` | text | no | |
| `ENCODEDBY` | text | no | |
| `CONDUCTOR` | text | no | |
| `LYRICIST` | text | yes | |

**Advanced fields**

| Field | Type | Multi |
|---|---|---|
| `TITLESORT` | text | no |
| `ARTISTSORT` | text | no |
| `ALBUMSORT` | text | no |
| `ALBUMARTISTSORT` | text | no |
| `REPLAYGAIN_TRACK_GAIN` | gain | no |
| `REPLAYGAIN_TRACK_PEAK` | decimal | no |
| `REPLAYGAIN_ALBUM_GAIN` | gain | no |
| `REPLAYGAIN_ALBUM_PEAK` | decimal | no |
| `MUSICBRAINZ_TRACKID` | uuid | no |
| `MUSICBRAINZ_ALBUMID` | uuid | no |
| `MUSICBRAINZ_ARTISTID` | uuid | no |
| `MUSICBRAINZ_ALBUMARTISTID` | uuid | no |
| `MUSICBRAINZ_RELEASEGROUPID` | uuid | no |
| `MUSICBRAINZ_WORKID` | uuid | no |
| `ACOUSTID_ID` | text | no |

Artwork is a separate capability, not a text field: one front cover per file, with replace/remove/export semantics.

### 5.2 Format mapping (v1.0)

| Canonical | MP3 (ID3) | FLAC (Vorbis) | WAV (ID3) |
|---|---|---|---|
| TITLE | TIT2 | TITLE | TIT2 |
| SUBTITLE | TIT3 | SUBTITLE / VERSION | TIT3 |
| ARTIST | TPE1 (multi in v2.4) | ARTIST | TPE1 |
| ALBUMARTIST | TPE2 | ALBUMARTIST | TPE2 |
| ALBUM | TALB | ALBUM | TALB |
| TRACKNUMBER / TRACKTOTAL | TRCK `n/total` | TRACKNUMBER + TRACKTOTAL | TRCK |
| DISCNUMBER / DISCTOTAL | TPOS `n/total` | DISCNUMBER + DISCTOTAL | TPOS |
| DATE | TDRC | DATE | TDRC |
| ORIGINALDATE | TDOR | ORIGINALDATE | TDOR |
| GENRE | TCON | GENRE | TCON |
| COMPOSER | TCOM | COMPOSER | TCOM |
| CONDUCTOR | TPE3 | CONDUCTOR | TPE3 |
| LYRICIST | TEXT | LYRICIST | TEXT |
| COMMENT | COMM | COMMENT | COMM |
| LYRICS | USLT | LYRICS | USLT |
| BPM | TBPM | BPM | TBPM |
| KEY | TKEY | KEY | TKEY |
| LANGUAGE | TLAN | LANGUAGE | TLAN |
| MOOD | TMOO | MOOD | TMOO |
| ISRC | TSRC | ISRC | TSRC |
| LABEL | TPUB | LABEL | TPUB |
| CATALOGNUMBER | TXXX:CATALOGNUMBER | CATALOGNUMBER | TXXX:CATALOGNUMBER |
| BARCODE | TXXX:BARCODE | BARCODE | TXXX:BARCODE |
| MEDIA | TMED | MEDIA | TMED |
| RELEASETYPE / STATUS | TXXX:RELEASETYPE / TXXX:RELEASESTATUS | RELEASETYPE / RELEASESTATUS | same as MP3 |
| COPYRIGHT | TCOP | COPYRIGHT | TCOP |
| ENCODEDBY | TENC / TSSE | ENCODED-BY / ENCODER | TENC / TSSE |
| Sort names | TSOT, TSOP, TSOA, TSO2 | TITLESORT, ARTISTSORT, ALBUMSORT, ALBUMARTISTSORT | same as MP3 |
| ReplayGain | TXXX:REPLAYGAIN_* | REPLAYGAIN_* | same as MP3 |
| MusicBrainz IDs | TXXX:MusicBrainz * Id | MUSICBRAINZ_* | same as MP3 |
| Front cover | APIC type 3 | FLAC picture block | APIC type 3 |

**v1.1 formats:** MP4/M4A/M4B use `©nam`, `©ART`, `aART`, `©alb`, `trkn`, `disk`, `©day`, `©gen`, `©wrt`, `©cmt`, `©lyr`, `tmpo`, `covr`, sort atoms `sonm/soar/soal/soaa`, and `----:com.apple.iTunes:*` for the long tail. OGG/Opus use Vorbis comments, with `R128_*` gain fields when ReplayGain is absent. The registry will carry these mappings; unsupported fields are hidden/disabled with a capability note.

### 5.3 Read/write semantics

- **Read** returns canonical key → list of strings plus capability metadata and raw tags for debugging.
- **Write** is a patch: only dirty fields are applied. Existing values for untouched fields, unknown frames/atoms, and other tag blocks are preserved.
- **Multi-value:** all values in order; single-value fields take the first value. ID3v2.4 is the default; a v2.3 compatibility mode joins multiple values with `/` and warns.
- **Totals:** if the file stores `n/total`, split on read; write back in the native slot.
- **Dates:** preserve the original precision; do not invent month/day.
- **Validation:** reject invalid numbers/dates/gains before writing; warnings (ISRC, barcode, UUID shape) do not block.
- **Unsupported field/format combinations** are disabled in the UI and rejected by the API with a clear message.
- **Cover:** replace all front-cover entries; preserve other picture roles; normalize uploads to JPEG/PNG/WebP with a size limit.
- **Write pipeline:** re-read from disk → record before state → back up → patch → verify by re-reading → update index → record undo entry. On any failure, restore the backup and report the file.
- **Windows:** if a file is locked by playback, return a clear "file in use" error; the UI pauses the active stream for the target and offers retry.

### 5.4 Validation summary

| Type | Rule |
|---|---|
| Integer | 0–9999, no signs |
| Date | `YYYY`, `YYYY-MM`, or `YYYY-MM-DD`; reject impossible dates |
| BPM | 0–999, up to one decimal |
| Gain | Signed decimal, optional ` dB` |
| Peak | Non-negative decimal |
| ISRC | 12 characters, uppercase; malformed values warn |
| Barcode | 8–14 digits; malformed values warn |
| UUID fields | Standard UUID shape; malformed values warn |
| Text | Trim, collapse NULs; title/artist/album ≤ 1024 chars; comment/lyrics ≤ 64 KB |

---

## 6. Architecture

### 6.1 Stack

| Layer | Choice | Why |
|---|---|---|
| Runtime | Python 3.12+ | Matches mutagen and Django support |
| Web | Django 5.2 LTS | Server-rendered forms, sessions, migrations, admin |
| DB | SQLite (WAL) | Single local user; zero setup; good enough with an index |
| Tag I/O | mutagen | Format coverage and mature frame/comment APIs |
| Images | Pillow | Cover thumbnails and format normalization |
| Interactivity | HTMX 2 (vendored) | Server-rendered fragments, no SPA/build step |
| Client state | Alpine 3 (vendored) | Selection, chips, panels, menus, toasts only |
| Player | Vanilla ES module | Audio/queue/Media Session are client-only concerns |
| Jobs | DB-backed queue + one worker thread | No Celery/Redis for a local app |
| Tests | pytest + pytest-django (+ optional Playwright) | Fast matrix tests and end-to-end smoke |

No Node, no bundler, no CDN. Vendor `htmx.min.js` and `alpine.min.js` under `static/vendor/` with pinned versions.

### 6.2 Component view

```
Browser
  ├─ Django templates (pages + fragments) ← HTMX swaps
  ├─ Alpine: selection, chips, panels, toasts
  └─ Player module ── GET /api/audio/<id> (Range) ──┐
                                                    │
Django views ── services ── models (SQLite)         │
  │               │                                 │
  │               ├─ fields registry                │
  │               ├─ format adapters (id3/flac/wav) │
  │               ├─ writer (validate→backup→verify)│
  │               ├─ scanner/index                  │
  │               ├─ covers cache ── /api/thumb ────┘
  │               ├─ jobs worker
  │               ├─ undo operations
  │               └─ MusicBrainz client
  │
  └─ filesystem: MUSIC_ROOT (audio files)
     cache/backups: .musictag_state/ (outside MUSIC_ROOT)
```

### 6.3 Project structure

A fresh Django project, not a patch over an existing app.

```
manage.py
pyproject.toml
requirements.txt
README.md
Dockerfile
docker-compose.yml
.env.example

config/
  settings.py
  urls.py
  asgi.py
  wsgi.py

library/
  apps.py
  models.py
  admin.py
  urls.py
  templatetags/
    tagfields.py
    querystring.py
  views/
    onboarding.py
    library.py
    album.py
    inspector.py
    actions.py
    bulk.py
    tools/
      parser.py
      numbering.py
      presets.py
      quality.py
      lookup.py
      history.py
      settings.py
    player.py
    fragments.py
  services/
    fields.py
    formats/
      base.py
      registry.py
      id3.py
      flac.py
      wav.py
      mp4.py          # v1.1
      vorbis.py       # v1.1
    library_index.py
    albums.py
    covers.py
    writer.py
    undo.py
    jobs.py
    parser.py
    numbering.py
    quality.py
    musicbrainz.py
    search.py
    thumbnails.py
    settings_service.py
  templates/library/
    base.html
    shell.html
    onboarding.html
    pages/
      albums.html
      album.html
      tracks.html
      folders.html
      quality.html
      parser.html
      numbering.html
      presets.html
      lookup.html
      history.html
      settings.html
    partials/
      topbar.html
      rail.html
      album_grid.html
      album_card.html
      track_table.html
      track_row.html
      folder_tree.html
      inspector_track.html
      inspector_bulk.html
      field_group.html
      chips.html
      bulk_bar.html
      bulk_preview.html
      job_progress.html
      player.html
      toasts.html
      pagination.html
      modal.html
  static/library/
    vendor/htmx.min.js
    vendor/alpine.min.js
    css/
      tokens.css
      base.css
      layout.css
      components.css
      library.css
      inspector.css
      player.css
    js/
      app.js
      selection.js
      inspector.js
      player.js
      shortcuts.js
      panels.js
    icons.svg
  management/commands/
    scan_library.py
    rebuild_thumbnails.py
    run_worker.py
    gc_cache.py
  migrations/
  tests/
    fixtures/               # tiny, redistributable audio files
    test_fields.py
    test_formats_id3.py
    test_formats_flac.py
    test_formats_wav.py
    test_writer.py
    test_undo.py
    test_scanner.py
    test_albums.py
    test_search.py
    test_parser.py
    test_numbering.py
    test_quality.py
    test_views_library.py
    test_views_actions.py
    test_jobs.py
    test_musicbrainz.py
```

### 6.4 Database (SQLite)

**`Track`**
- `id`, `path` (unique relative path), `filename`, `folder`, `format`, `size`, `mtime`, `indexed_at`
- `duration`, `bitrate`, `sample_rate`, `channels`
- Promoted, indexed tag columns for browsing: `title`, `artist`, `album`, `album_artist`, `genre`, `date`, `track_no`, `disc_no`, `catalog_number`
- `has_cover`, `cover_hash`
- `tags` JSON (canonical key → list of values; source for advanced fields and multi-values)
- `issue_flags` (bitmask/JSON computed at scan/write)
- `read_error` (text, null when healthy)

**`Album`** (materialized index)
- `id`, `key` (unique grouping key), `title`, `album_artist`, `year`, `genre`, `label`, `catalog_number`
- `track_count`, `disc_count`, `duration`, `cover_hash`, `cover_track_id`
- `issue_count`, `updated_at`

**`Operation`** — `id`, `kind`, `status`, `summary`, `track_count`, `created_at`, `finished_at`
**`OperationEntry`** — `operation`, `track`, `before_tags`, `after_tags`, `before_cover`, `after_cover`, `status`, `error`
**`Job`** — `id`, `kind`, `status`, `total`, `done`, `succeeded`, `failed`, `payload`, `result`, `error`, timestamps
**`Preset`** — `id`, `name`, `fields` JSON, timestamps
**`ParserPattern`** — `id`, `name`, `template`, `builtin`
**`AppSetting`** — `key`, `value` JSON (library root, ID3 preference, thresholds, MusicBrainz contact, theme defaults)

Django sessions store only the unlock flag. No tag data is stored outside the DB and files.

### 6.5 Scan and index

- Scan is a job; total is discovered while walking, progress is per file.
- For each supported file: skip when `(mtime, size)` matches; otherwise read tags/duration/cover, compute the cover hash/cache rendition, upsert the track.
- Update affected albums after the walk; remove tracks whose files no longer exist; remove empty albums.
- First run: onboarding asks for a path, validates it, scans, shows counts and format breakdown.
- Startup: if a root is configured, enqueue an incremental scan once (guarded against dev autoreload double-start). A manual "Rescan" is always available.
- Folder view reads the index, not the filesystem.
- Hashing covers avoids duplicate cache entries across tracks/albums.

### 6.6 Write pipeline

All writes — single, bulk, covers, parser, numbering, presets, lookup, undo — go through one service:

1. Resolve and validate the path under `MUSIC_ROOT`, plus format capability.
2. Validate the patch against the registry.
3. Re-read the file from disk; build before-state (tags + cover).
4. Create `Operation` and `OperationEntry` rows.
5. Copy the file to `.musictag_state/backups/<operation>/<n>` (hardlink or copy).
6. Apply the patch with the adapter; flush; verify by re-reading and comparing the changed fields.
7. On failure: restore the backup and mark the entry failed.
8. On success: update the index and albums, refresh cover cache, record after-state.
9. Return per-file results. Cover cache entries referenced by operations are retained until pruning.
10. Serialize writes through a single writer lock so two jobs cannot touch a file at once.

### 6.7 Jobs

- DB-backed queue. A worker thread atomically claims a queued job, updates progress after every file, and supports cancellation between files.
- One worker by default. Jobs are safe under multiple Django processes because claiming is atomic, but the documented deployment is one process (Docker: one gunicorn worker with threads).
- Job kinds: scan, bulk tag write, bulk covers, quality report, metadata import.
- HTMX polls `/ui/jobs/<id>` every 500 ms while running; completion triggers library/inspector refresh and a toast.
- Result details live in `OperationEntry`; the job result includes counts and a small failure sample.

### 6.8 Undo

- Every write produces an operation with before/after state.
- The history page lists operations newest-first; **Undo** restores tags and covers for every entry.
- Undo is itself an operation, so it can be undone.
- Partial restores are reported per file; nothing is hidden.
- Retention: 30 days or 200 operations, whichever is larger; backups/covers pruned only when unreferenced.

### 6.9 Search and filters

- Global search over promoted columns + filename with `icontains`, debounced 200 ms and capped results.
- Filters are combinable; counts come from aggregate queries on indexed columns.
- Issue filters use `issue_flags`; duplicate track-number queries group by album key + disc + track.
- FTS5 is a v1.1 upgrade path if `LIKE` latency exceeds the budget.

### 6.10 Covers and thumbnails

- Cache under `.musictag_state/cache/covers/<sha256>/` with renditions: 96px, 320px, original.
- Serve via `/api/thumb/<hash>?size=96|320|orig` with `ETag`, `Cache-Control: immutable` for hash URLs.
- Album covers come from the first track (by disc/track) with art; folder images are considered when no embedded art exists.
- Extract to folder writes `cover.jpg/png`; import from folder embeds it.
- GC removes cache entries not referenced by tracks/albums/operations.

### 6.11 Security and local operation

- Bind `127.0.0.1` by default; LAN use requires an explicit host/port and an allow-list.
- No authentication in v1; single-user local assumption. A warning explains this and recommends loopback.
- Every path input is resolved and contained under the library root; extension allow-list enforced.
- Cover uploads limited by content type and size; CSRF on all writes; Django autoescaping everywhere.
- `DEBUG=False` by default; secrets/contact settings via env with sane local defaults.
- The unlock flag is a deliberate safety guard against accidental writes, not a security boundary.

### 6.12 Performance strategy

- Index once; never walk the filesystem for page requests.
- Promoted columns + indexes; list queries select only needed columns; no N+1 inspector queries.
- Server-side pagination; no full-library payloads to the browser.
- Thumbnails as separate cached requests; never base64 in HTML.
- Debounced search; capped result sets with "refine your search".
- Album aggregates maintained incrementally after writes.
- One write worker; batch operations stream progress instead of blocking requests.

---

## 7. Server routes

### 7.1 Pages

| Route | Purpose |
|---|---|
| `/` | Shell + default view (albums) |
| `/albums/<key>` | Album detail |
| `/tracks` | Track table (`q`, `sort`, `page`, `cols`, filters) |
| `/folders` | Folder browser |
| `/quality` | Quality report |
| `/tools/parser` | Filename parser |
| `/tools/numbering` | Auto-numbering |
| `/tools/presets` | Presets |
| `/tools/lookup` | Metadata lookup |
| `/history` | Undo history |
| `/settings` | App settings |
| `/onboarding` | First-run setup |

### 7.2 HTML fragments (HTMX)

`/ui/albums`, `/ui/albums/<key>/tracks`, `/ui/tracks`, `/ui/tracks/rows`, `/ui/folders`, `/ui/folders/<path>`, `/ui/inspector/track/<id>`, `/ui/inspector/bulk`, `/ui/bulk/preview`, `/ui/bulk/result`, `/ui/jobs/<id>`, `/ui/quality/issues`, `/ui/history/list`, `/ui/search`, `/ui/topbar`, `/ui/toasts`.

### 7.3 Actions (POST, HTML + `HX-Trigger`)

`/actions/lock`, `/actions/scan`, `/actions/scan/cancel`, `/actions/tracks/<id>/save`, `/actions/tracks/<id>/cover`, `/actions/tracks/<id>/undo`, `/actions/bulk/preview`, `/actions/bulk/apply`, `/actions/bulk/covers`, `/actions/albums/<key>/apply`, `/actions/parser/preview|apply`, `/actions/numbering/preview|apply`, `/actions/presets` (CRUD), `/actions/presets/<id>/apply`, `/actions/quality/fix`, `/actions/lookup/search|apply`, `/actions/history/<id>/undo`, `/actions/settings`, `/actions/cache/rebuild`.

### 7.4 JSON endpoints

| Route | Purpose |
|---|---|
| `/api/audio/<id>` | Audio stream with `Range`, `206`, `Content-Range` |
| `/api/thumb/<hash>` | Cover rendition (`size` query) |
| `/api/player/queue` | Queue metadata for the current context |
| `/api/health` | Local health/version check |

### 7.5 Conventions

- POST + CSRF for all state changes.
- Success: re-render the changed fragment and fire `library:refresh` / `inspector:refresh` / `toast` events.
- Validation failure: `422` with the field group re-rendered and inline errors.
- Locked write: `403` with a banner fragment.
- Job started: `202` + progress fragment that polls until done.
- No JSON list rendering in the UI; HTML is the interface.

---

## 8. Design system

### 8.1 Tokens

- **Color:** `--bg`, `--surface`, `--surface-raised`, `--border`, `--text`, `--text-muted`, `--accent`, `--accent-contrast`, `--danger`, `--warning`, `--success`, plus row/hover/selected states. Light and dark values; accents override a small subset.
- **Spacing:** 4px base scale (4/8/12/16/24/32/48).
- **Radius:** 4px controls, 8px cards, 12px panels.
- **Type:** system stack; sizes 11/12/13/14/16/20/28; weights 400/500/600; tabular numerals for data.
- **Elevation:** borders and subtle shadows only; no glow effects.
- **Motion:** 120–160 ms transitions; respect `prefers-reduced-motion`.

### 8.2 Components

Buttons (primary/secondary/ghost/danger/icon), inputs, select, combobox, date input, number+total pair, chips, checkbox, segmented control, table, album card, badge, banner, toast, modal, drawer, tooltip, skeleton, progress bar, empty state, pagination.

### 8.3 Rules

- One primary action per region (Save in the inspector, Apply in the bulk bar).
- Disabled controls explain why (tooltip or inline note), especially format-unsupported fields.
- No color-only status; pair with text or icon.
- Every list has empty, loading, and error states.
- Focus is never lost after fragment swaps; HTMX focus restoration is handled explicitly.

---

## 9. Build milestones

Each milestone leaves a runnable app and a demo. Order is dependency-driven: index before browsing, writer/undo before bulk, bulk before tools.

### M0 — Project foundation

**Build**
- Scaffold Django project and `library` app; settings split; `.env.example`; `pyproject.toml`; ruff/pytest config; CI workflow.
- SQLite WAL; base template, tokens, layout shell, vendored HTMX/Alpine, icon sprite.
- Health page; onboarding page skeleton; empty-state components; toast mechanism.
- Test fixtures (tiny MP3/FLAC/WAV) and CI test run.

**Acceptance**
- Fresh clone → install → migrate → run → onboarding renders.
- No external network assets; app loads offline.
- Tests and lint pass in CI.

### M1 — Index and read-only library

**Build**
- Models/migrations: Track, Album, AppSetting; admin.
- Field registry (metadata, labels, types, capabilities).
- Format adapters: ID3 (MP3/WAV), FLAC read; cover extraction; capability flags.
- Scanner job, incremental rescan, album aggregation, issue flags.
- Cover cache + thumbnail endpoint; Range audio endpoint.
- Album grid, album detail, track table (read-only), folder tree, search/filters/sorting/pagination.
- Player basics: play track, seek, next/previous within the visible list.

**Acceptance**
- Scan a fixture library of 5,000 tracks; browse all three views; search/sort/filter.
- No base64 covers in HTML; thumbnails requested separately and cached.
- Seeking works on a 10-minute file.
- First scan shows progress; second scan of unchanged files is fast.

### M2 — Editing and covers

**Build**
- Write adapters for MP3/FLAC/WAV; patch semantics; multi-value read/write; validation.
- Writer service: backup, patch, verify, restore on failure; Windows busy handling.
- Inspector: grouped fields, chips, dirty tracking, explicit save/revert, keyboard save.
- Lock/unlock flow and server enforcement.
- Cover replace/remove/export/import from folder; cache refresh.
- Single-track operation records and undo-last.
- Track read errors surfaced.

**Acceptance**
- Round-trip every canonical field on each format.
- Multi-value values survive; unknown tags survive.
- Cover set/replace/remove works on all v1 formats.
- Save is blocked when locked; validation errors are field-specific; undo restores tags + cover.
- Failed write restores the original file and reports the cause.

### M3 — Selection, bulk editing, undo

**Build**
- Explicit selection model and bulk bar; mixed-value inspector; per-field include and operation modes; smart defaults.
- Bulk preview diff with per-file fingerprint token and drift detection.
- Bulk apply job: progress, cancel, per-file results, retry failed.
- Bulk covers (upload/reuse/remove) through preview/apply.
- Undo history page; multi-level restore; retention/pruning.
- Operation log and toasts with failure details.

**Acceptance**
- Preview matches applied output exactly; only included fields change.
- Files modified between preview and apply are skipped or require confirmation.
- 500-file apply shows real progress, can be cancelled, and each result is inspectable.
- Partial failures do not abort the batch; retry works.
- Undo restores tags and covers and can itself be undone.

### M4 — Tools

**Build**
- Filename parser: templates, presets, preview table, apply.
- Auto-numbering: scope/start/pad/totals/discs, preview/apply.
- Presets: create/edit/delete/apply with preview.
- Quality report: issue filters, navigation to tracks/albums, bulk fixes.
- MusicBrainz search, release detail, track matching, CAA candidates, throttling, field preview/apply.
- Settings page: root, ID3 preference, thresholds, contact, cache tools.
- Operation log page.

**Acceptance**
- Parser writes artist/title/track correctly from templates; preview equals apply.
- Numbering produces expected plans for folder, album, and disc scopes.
- Presets apply with preview and per-field selection.
- Quality report lists every issue category and fixes the common ones.
- Lookup works online with throttling and fails cleanly offline.

### M5 — Player and shell polish

**Build**
- Queue model from album/view/folder/selection; auto-advance, shuffle, repeat.
- Queue drawer, Media Session, persisted volume/queue.
- Keyboard map, shortcuts help, focus management, density toggle.
- Responsive behavior for 1024–1280px; inspector drawer.
- Empty states, skeletons, error boundaries, onboarding refinement.

**Acceptance**
- Queue order matches its originating context; auto-advance and repeat behave correctly.
- Keyboard-only flow: search → open album → edit → save → select multiple → preview → apply → undo.
- No layout breakage at 1024px or 1920px.
- Media keys work in Chrome and Firefox.

### M6 — Additional formats

**Build**
- MP4/M4A/M4B and OGG/Opus adapters with capability metadata, cover handling, and mapping.
- Extend format matrix tests and fixtures.
- Settings toggle/status for experimental formats until green.

**Acceptance**
- Same field round-trip matrix passes for new formats.
- Fields unsupported by a format are visibly disabled, never dropped silently.
- Mixed-format bulk apply behaves correctly.

### M7 — Hardening and release

**Build**
- Performance pass: query counts, album aggregates, pagination, index verification.
- Security pass: path containment tests, uploads, host/debug defaults, CSRF coverage.
- Full test sweep + optional Playwright flows; accessibility review.
- README, setup, screenshots, Docker (one worker), release checklist.
- Cache/backup GC command and scheduling guidance.

**Acceptance**
- Fresh install → scan → edit → bulk → undo works on Windows and Linux.
- Performance budgets in §12 met on the reference dataset.
- Tests/lint green; docs complete; no dead endpoints or templates.

---

## 10. Testing and quality

### Layers

- **Unit:** registry, validation, mapping, parser, numbering, grouping, search, quality rules.
- **Adapter matrix:** every canonical field × every supported format; multi-value order; unknown-tag preservation; cover add/replace/remove; date precision; totals normalization.
- **Writer:** backup created, verify-after-write, restore on injected failure, Windows-busy retry, operation records, index/album refresh.
- **Scanner:** incremental skip/update, orphan cleanup, unreadable file handling, cancellation, path containment.
- **Views/HTMX:** full page vs. fragment, CSRF, locked writes (403), validation (422), OOB refreshes, pagination/sort/filter URL state.
- **Bulk/jobs:** preview=apply, drift detection, partial failure, cancel, retry, progress counts.
- **Undo:** multi-level, cover restore, undo-of-undo, pruning, partial failure.
- **External:** MusicBrainz client with recorded fixtures; no live network in CI.
- **End-to-end (optional):** Playwright for onboarding, browse, edit, bulk apply, undo, play/seek.

### Test data

- Tiny, redistributable audio fixtures for each format (silence with known tags).
- A fixture library generator for performance tests (synthetic files + tags, no real audio needed for index-only tests).
- No test writes outside temporary directories; backups/cache redirected to a temp state dir.

### Manual acceptance script (release)

1. Fresh install, set library root, scan.
2. Browse albums; open an album; play a track; seek; next/previous.
3. Edit title/artist/genre on one track; save; reload; verify in an external player.
4. Replace and remove a cover; export cover to folder; re-import.
5. Select an album's tracks; bulk-set album artist, year, genre; preview; apply; verify.
6. Parse filenames from a messy folder; preview; apply.
7. Auto-number an album with totals; verify.
8. Run quality report; fix a duplicate track number.
9. Lookup an album; apply date/label/cover.
10. Undo the last three operations; verify tags and covers restored.
11. Lock; confirm writes are blocked; unlock.
12. Check keyboard-only flow and 125% zoom.

---

## 11. Performance budgets

Reference dataset: 50,000 tracks, 4,000 albums, 20% with embedded art, on a local SSD.

| Operation | Target |
|---|---|
| App shell render | < 150 ms |
| Album grid page (60 cards) | < 300 ms |
| Track table page (100 rows) | < 200 ms |
| Search response (debounced) | < 250 ms |
| Inspector load | < 150 ms |
| Thumbnail response (cached) | < 50 ms |
| First scan (50k tracks) | progress visible within 1 s; complete in minutes, not hours |
| Incremental scan (no changes) | < 5 s |
| Single-track save | < 300 ms + write time |
| Bulk apply | linear; continuous progress; UI remains responsive |
| Cover cache size | bounded; GC supported |
| SQLite size | roughly < 100 MB for 50k tracks |

---

## 12. Risks and mitigations

| Risk | Mitigation |
|---|---|
| Windows locks files during playback | Detect `PermissionError`, return a clear error, pause target playback, retry once in bulk jobs |
| Tag loss on write | Patch-only writes, preserve unknown frames, backup + verify + restore, round-trip tests |
| Large library scan/index | Background job, incremental mtime/size checks, indexed queries, pagination |
| Format quirks (ID3v2.3, WAV, MP4) | Adapter isolation, capability flags, fixture matrix, disable unsupported fields |
| Multi-value portability | Canonical list model; format-specific write rules; warnings on lossy compatibility modes |
| Backups consume disk | Prune by operation age/count; hardlink where possible; cache GC command |
| Job model with multiple processes | Atomic DB claim; documented single-worker deployment; lazy worker restart |
| HTMX/Alpine complexity | Strict boundary: server owns data, Alpine owns ephemeral UI; one fragment per region; E2E smoke tests |
| Lookup rate limits/offline | 1 req/s, timeout, cached responses, explicit apply, offline-safe errors |
| Cover art copyright/wrong art | Local-only tool; user chooses art; no automatic online writes |
| Search latency at 50k+ | Indexed promoted columns; FTS5 fallback planned in v1.1 |

---

## 13. Decisions and assumptions

1. **Local web app, single user.** No auth in v1; bind to loopback by default; document LAN caution.
2. **Server-rendered HTML** with HTMX fragments; Alpine only for ephemeral UI state. No SPA, no build step, no CDN.
3. **Explicit save** in the inspector; no auto-save. Bulk requires preview → apply.
4. **The database is an index, not a store.** Tags and covers are read from/written to files; deleting the DB triggers a rescan, not data loss.
5. **Patch writes only.** Untouched fields are never rewritten.
6. **Expanded tags** as listed in §5; MP3/FLAC/WAV in v1.0, MP4/OGG/Opus in v1.1.
7. **Hybrid UI:** albums (art) + tracks (table) + folders (tree), sharing one inspector and one player.
8. **Bulk model:** per-field inclusion plus multi-value operations; no artificial "compilation/template" mode switch.
9. **Undo is mandatory** for every write, including covers; undo is itself undoable.
10. **Themes:** light/dark/system plus three accents; no bespoke full palettes.
11. **No legacy compatibility.** The build is greenfield; there is no migration from earlier schemas or JSON state.
12. **One application process** is the supported deployment (plus threads); Docker runs a single worker.

---

## 14. Definition of done (v1.0)

- All v1.0 scope items implemented and documented.
- Every canonical field round-trips on MP3, FLAC, and WAV with multi-value and cover tests.
- Bulk preview and apply are exact, drift-aware, cancellable, and undoable.
- No write can occur outside the library root or without an undo record.
- Keyboard-only browsing/editing/bulk/undo flow works end to end.
- Performance budgets met on the 50k reference dataset.
- App works offline; no external runtime assets.
- Fresh install, Docker run, scan, edit, bulk, and undo verified on Windows and Linux.
- README covers setup, local-only warning, formats, backup/undo behavior, and troubleshooting.
- Lint and full test suite green; no known data-loss bugs.
