# MusicTag

A local, server-rendered workspace for browsing and editing music files. Python 3.12+, Django 5.2, SQLite, Mutagen, and Pillow; no Node build, CDN, telemetry, accounts, or remote streaming service.

## Run locally

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python manage.py migrate
python manage.py runserver 127.0.0.1:8000 --noreload
```

On Linux/macOS, activate with `source .venv/bin/activate`. Open **http://127.0.0.1:8000**, enter the absolute path to a music folder, and scan. The initial scan runs in a background thread with real progress. Subsequent server starts queue an incremental scan. Static assets are included and served locally, even with `DEBUG=false`.

**Local single-user application, not a public service.** Keep the loopback binding. The write lock is an accident-prevention guard, **not authentication**. Do not expose it through port forwarding or a reverse proxy. An explicit `ALLOWED_HOSTS` list is required for any host other than localhost. Do not run multiple application processes or simultaneous maintenance commands against the same state directory.

## Everyday use

- Browse **Albums**, **Tracks**, or **Folders**. Search, filter, sort, and paginate indexed data; no audio directory walks during browsing.
- Click a track to inspect all canonical fields, technical metadata, and raw tags. Unlock writes in the header before editing. Multi-value chips accept Enter/comma; paste semicolons or newlines.
- **Save** writes only dirty fields. **Revert** resets the form; failures keep entered values intact. `Ctrl+S` saves. A changed-on-disk file must be reloaded before saving.
- Select tracks with checkboxes, Ctrl/Cmd-click, Shift-click, or “Select all filtered.” **Edit selection** offers shared/mixed values, per-field inclusion, and Replace/Add/Remove/Clear operations.
- Review the server-generated **Preview**, then **Apply**. Only changed files are queued. Signed previews expire after 30 minutes. Files with any byte changes since preview are refused, never silently overwritten. More than 20 changed files require confirmation (configurable).
- Jobs show progress and per-file failures; cancellation happens between files. Retry uses the original fingerprints, so externally modified failures require a **new preview**.
- Replace/remove/import folder artwork in the inspector; export downloads the original cover. Album-wide covers use the same bulk editor. Non-front picture roles are preserved.
- Filename parsing, scoped numbering, named presets, quality filters, MusicBrainz release matching and Cover Art Archive import all feed the same preview/write pipeline.
- **History → Undo** restores exact pre-write bytes, including unknown metadata and artwork. Undo is itself undoable. Undo refuses files changed since the operation.
- Play tracks, albums, filtered views, folders, or selections. The persistent player supports HTTP ranges, seek, volume, queue, shuffle, repeat, and Media Session. A queue is capped at 1,000 tracks to bound browser payloads. Browser codec support determines which files play; no transcoding is performed.
- `?` lists shortcuts. Themes (light/dark/system), accents (indigo/teal/amber), and density are browser-local settings.

## Formats and fields

**MP3 (ID3), FLAC (Vorbis comments), WAV (ID3)** are enabled. All registry fields round-trip in the default ID3v2.4 mode, including ordered artist/genre/composer lists, native track/disc totals, dates with precision, credits, lyrics, sort names, ReplayGain, and identifiers. See `library/services/fields.py` for the single registry and `library/services/formats/base.py` for mappings. Unknown tags are preserved by patch writes.

ID3v2.3 compatibility mode joins multi-values with `/` (ambiguous for literal slashes). Some v2.4-only fields or date precision cannot survive that conversion; verification rejects and rolls back lossy changes rather than silently dropping them. Prefer v2.4. MP4/M4A/M4B and OGG/Opus remain **v1.1**, as specified in the plan.

## Safety and state

State defaults to `.musictag_state/` beside `manage.py`, **outside the music root**. It contains the index/session database, a generated persistent secret, hash-addressed cover originals/renditions, and full-file backups. Set `MUSICTAG_STATE` in `.env` to use another location; see `.env.example`.

Every mutation is serialized: validate → contain path → re-read/fingerprint → record operation → **copy and flush full backup** → patch → flush and verify → index → record success. Hardlinks are intentionally not used: in-place tag writers would corrupt a hardlinked backup. Backup integrity is checked again before undo. Permission/file-in-use failures and rollback errors remain visible in history. Keep enough free disk space for full copies of edited files.

The database is an index for file metadata, **but it also holds undo history and backup references**. Removing it does not remove your embedded tags, but does lose application history. Back up the entire state directory if you need to retain undo. A configured root cannot be changed once tracks/history exist: use separate state directories for separate libraries to prevent history being applied to the wrong root.

Preview drift protection hashes the entire audio file. This is deliberately conservative and adds I/O for large files. It does not lock out another external tag editor; avoid editing the same files simultaneously. The application is not a substitute for a separate library backup or a power-loss-safe filesystem.

### Crash recovery

After an interrupted process, active jobs/pending writes require explicit recovery. **Stop the server first.**

```sh
python manage.py recover_operations
python manage.py recover_operations --restore
python manage.py scan_library
```

Recovery restores pending writes only from integrity-checked backups, marks interrupted jobs failed, and requires a rescan. It refuses missing/corrupt backups. Inspect the reported paths manually if recovery cannot proceed. Never delete backups to resolve an error.

### Maintenance

With the web server stopped:

```sh
python manage.py scan_library
python manage.py rebuild_thumbnails
python manage.py gc_cache --dry-run
python manage.py gc_cache
```

GC retains the latest 200 operations **and** all operations newer than 30 days, then removes unreferenced backups/covers (with a one-hour grace for cover previews). Schedule this manually or with Task Scheduler/cron while the server is stopped. `MUSICTAG_WORKER=false` plus `python manage.py run_worker` is available for a manually managed worker; do not also enable the automatic worker.

## Online lookup

Everything except explicit lookup works offline. Set a MusicBrainz contact email or URL in Settings, search releases, inspect a release and its track list, select fields/optional cover, and preview. Requests use an identifying User-Agent, timeout, cache, and 1-request/second JSON throttle. Artwork downloads have a size limit and restricted HTTPS archive redirects. Metadata is never applied automatically. Network failures do not change files. Review matches, especially compilations and alternate editions.

## Docker (optional)

```sh
# Set MUSIC_FOLDER to your host music folder in .env.
docker compose up --build
```

Open localhost:8000 and choose **`/music`** in onboarding (the container path, not your host path). Music is mounted read/write; state has its own persistent volume. The container runs one Gunicorn process with four request threads and one write worker. Host port is loopback-only. Docker execution is not verified in this environment.

## Development and verification

```sh
python -m pip install -r requirements-dev.txt
python manage.py check
python manage.py makemigrations --check --dry-run
python -m ruff check .
python -m pytest
```

Optional browser smoke (temporary state and copied generated silence only):

```sh
python -m pip install playwright
python -m playwright install chromium
python scripts/browser_smoke.py
```

Unit/integration tests run without network access. The audio fixtures are generated silence (CC0); tests redirect library/state paths to temporary folders. The browser smoke checks onboarding, scan, single save, bulk preview/apply, undo, playback wiring, and 1024/1920px layouts. CI defines Windows/Linux and Python 3.12/3.13 jobs. Full external-player interoperability, Firefox media keys, Docker/Linux execution, accessibility auditing, and 50k-library performance still require release validation.

See **[IMPLEMENTATION.md](IMPLEMENTATION.md)** for the implemented scope and remaining plan gaps. This is a runnable implementation, **not a claim that every v1.0 release acceptance criterion is complete**.

## Troubleshooting

- **File in use / permission denied:** pause playback (the inspector releases its own target stream before saving), close other players/editors, check permissions, and retry. On Windows, antivirus or another process may still hold the file.
- **Changed since preview:** rescan/reopen, make a new preview, and review it. No force-overwrite shortcut is provided.
- **No artwork thumbnail:** malformed embedded art is retained but may not have a rendition. Replace it with a valid JPEG/PNG/WebP. Uploads are normalized to JPEG, capped at 3,000px and 10 MB maximum input.
- **Lookup unavailable:** verify contact settings/network access, or continue offline. No lookup is required for local edits.
- **Audio won’t play:** browser codec support varies, especially WAV encodings. Tags can still be edited; there is no transcoder.
- **Missing static assets:** run `python manage.py collectstatic --noinput`, then restart. Vendored HTMX/Alpine are in `library/static/library/vendor/`.
- **Database busy:** only one serving process/worker is supported. Stop duplicate servers or maintenance jobs; SQLite uses WAL and a 30-second busy timeout.
