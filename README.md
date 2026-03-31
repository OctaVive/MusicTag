# MusicTag

MusicTag is a Django web app for browsing a music library and editing metadata in single-track and bulk workflows.

This app was built with [Cursor](https://cursor.com/).

<img width="1533" height="883" alt="image" src="https://github.com/user-attachments/assets/6ce313db-7034-4e6a-9e53-529938c1e53f" />


## Security Warning

MusicTag is intended for local use only (localhost or trusted local network).
Do **not** expose this app directly to the public internet.

## Features

- Folder tree browser with filtering, nested selection, and resizable tree panel
- Tree UI polish: per-song thumbnail previews and modern folder icons
- Supported audio extensions: `.mp3`, `.flac`, `.wav`
- Single-track metadata edit flow
- Bulk edit flow with per-field apply checkboxes
- Bulk modes:
  - `Compilation` mode
  - `Template` mode
- Tag fields supported:
  - `TITLE`
  - `ARTIST`
  - `ALBUM`
  - `ALBUMARTIST`
  - `TRACKNUMBER`
  - `DISCNUMBER`
  - `YEAR`
  - `GENRE`
- Cover art workflows:
  - Single-track cover preview + replace
  - Optional bulk cover apply (checkbox-gated)
  - Bulk cover remove/set tools
- Advanced toolbox actions:
  - Filename parser preview/apply
  - Preset save/load/apply
  - Auto-number preview/apply
  - Bulk change preview
  - Undo last operation
  - Quality check
  - Metadata lookup
- Lock/unlock safety switch before writes
- Save progress indicator + status messaging
- Theme selector with multiple color themes affecting full UI/icons
- Spotify-style bottom player:
  - Track metadata + cover context
  - Previous/next track navigation
  - Play/pause, seek, volume controls
  - Keyboard shortcuts (space, arrows) with input-focus safeguards

## Installation (Local)

### Requirements

- Python 3.12+
- pip

### Steps

1. Clone the repository and enter it.
2. Install dependencies:
   - `pip install -r requirements.txt`
3. Run database migrations:
   - `python manage.py migrate`
4. (Optional) Configure music library root:
   - Set `MUSIC_ROOT` in `musictag/settings.py`
5. Start the server:
   - `python manage.py runserver 0.0.0.0:8000`
6. Open [http://127.0.0.1:8000](http://127.0.0.1:8000)

## Docker

1. Ensure Docker and Docker Compose are installed.
2. Provide your music path:
   - Option A: set `MUSIC_LIBRARY_PATH` (absolute path on your host)
   - Option B: put music under `./music` in this repo (default fallback)
3. Start with Docker Compose:
   - `docker compose up --build`
4. Open [http://127.0.0.1:8000](http://127.0.0.1:8000)

## Notes

- For security, file operations are constrained to `MUSIC_ROOT`.
- `.wav` metadata support depends on tags present in source files.
- This project is designed for local-network hosting only, not public web deployment.
