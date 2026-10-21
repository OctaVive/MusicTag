import hashlib
import os
import re
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

from django.db import transaction

from library.models import Album, Track
from . import covers
from .formats.registry import EXTENSIONS, adapter
from .settings_service import contained, root


def first(tags, key):
    return next(iter(tags.get(key, [])), "")


def issues(tags, has_cover, error=""):
    flags = [
        "missing_" + key.lower()
        for key in ["TITLE", "ARTIST", "ALBUM", "ALBUMARTIST", "TRACKNUMBER", "DISCNUMBER"]
        if not first(tags, key)
    ]
    if not has_cover:
        flags.append("missing_cover")
    if error:
        flags.append("read_error")
    return flags


def index_file(relative, snapshot=None):
    path = contained(relative, EXTENSIONS)
    stat = path.stat()
    error = ""
    try:
        snapshot = snapshot or adapter(path).read()
        tags, cover = snapshot.tags, covers.cache(snapshot.cover)
        info = snapshot.info
    except Exception as exc:
        tags, cover, info, error = {}, "", {}, str(exc)
    parent = Path(relative).parent.as_posix()
    values = {
        "filename": path.name,
        "folder": "" if parent == "." else parent,
        "format": path.suffix[1:].lower(),
        "size": stat.st_size,
        "mtime": stat.st_mtime_ns,
        "tags": tags,
        "has_cover": bool(cover),
        "cover_hash": cover,
        "read_error": error,
        **info,
    }
    for column, key in {
        "title": "TITLE",
        "artist": "ARTIST",
        "album": "ALBUM",
        "album_artist": "ALBUMARTIST",
        "date": "DATE",
        "genre": "GENRE",
        "catalog_number": "CATALOGNUMBER",
    }.items():
        values[column] = first(tags, key)
    for column, key in {"track_no": "TRACKNUMBER", "disc_no": "DISCNUMBER"}.items():
        try:
            values[column] = int(first(tags, key) or 0)
        except ValueError:
            values[column] = 0
    values["issue_flags"] = issues(tags, bool(cover), error)
    return Track.objects.update_or_create(path=Path(relative).as_posix(), defaults=values)[0]


def normalized(value):
    return re.sub(r"[^\w]+", " ", unicodedata.normalize("NFKC", value).casefold()).strip()


def rebuild_albums():
    groups = defaultdict(list)
    tracks = list(Track.objects.all())
    fallback = defaultdict(set)
    for track in tracks:
        fallback[(track.folder, normalized(track.album))].add(track.album_artist or track.artist)
    for track in tracks:
        artist = track.album_artist
        if not artist:
            artists = fallback[(track.folder, normalized(track.album))] - {""}
            artist = next(iter(artists)) if len(artists) == 1 else "Compilation"
        identity = (
            (normalized(artist), normalized(track.album))
            if track.album and artist != "Compilation"
            else (track.folder, normalized(track.album))
        )
        key = hashlib.sha256(repr(identity).encode()).hexdigest()
        groups[key].append((track, artist))
    keep = []
    with transaction.atomic():
        for key, members in groups.items():
            ordered = sorted((t for t, _ in members), key=lambda t: (t.disc_no, t.track_no, t.path))
            lead = ordered[0]
            art = next((t for t in ordered if t.has_cover), lead)
            numbers = Counter((t.disc_no, t.track_no) for t in ordered if t.track_no)
            inconsistent = [
                column
                for column in ["album_artist", "date", "genre"]
                if len({getattr(t, column) for t in ordered}) > 1
            ]
            for track in ordered:
                flags = issues(track.tags, track.has_cover, track.read_error)
                if track.track_no and numbers[(track.disc_no, track.track_no)] > 1:
                    flags.append("duplicate_tracknumber")
                flags += ["inconsistent_" + column for column in inconsistent]
                track.issue_flags = flags
            album, _ = Album.objects.update_or_create(
                key=key,
                defaults={
                    "title": lead.album or "Unknown album",
                    "album_artist": members[0][1],
                    "year": lead.date[:4],
                    "genre": lead.genre,
                    "label": first(lead.tags, "LABEL"),
                    "catalog_number": lead.catalog_number,
                    "track_count": len(ordered),
                    "disc_count": max(t.disc_no for t in ordered) or 1,
                    "duration": sum(t.duration for t in ordered),
                    "cover_hash": art.cover_hash,
                    "cover_track_id": art.pk if art.has_cover else None,
                    "issue_count": sum(len(t.issue_flags) for t in ordered),
                },
            )
            keep.append(album.pk)
            for track in ordered:
                track.album_group = album
        Track.objects.bulk_update(tracks, ["album_group", "issue_flags"], batch_size=500)
        Album.objects.exclude(pk__in=keep).delete()


def scan(job=None):
    base = root()
    known = {t.path: (t.size, t.mtime) for t in Track.objects.only("path", "size", "mtime")}
    files, walk_errors = [], []

    def walk_error(error):
        walk_errors.append(str(error))

    for folder, dirs, names in os.walk(base, followlinks=False, onerror=walk_error):
        dirs[:] = [d for d in dirs if not (Path(folder) / d).is_symlink()]
        for name in names:
            path = Path(folder) / name
            if path.suffix.lower() in EXTENSIONS and not path.is_symlink():
                files.append(path.relative_to(base).as_posix())
    if job:
        job.total = len(files)
        job.save(update_fields=["total"])
    seen, cancelled, failed, changed = set(), False, 0, 0
    for relative in files:
        if job:
            job.refresh_from_db(fields=["cancel_requested"])
            if job.cancel_requested:
                cancelled = True
                break
        seen.add(relative)
        try:
            path = contained(relative, EXTENSIONS)
            stat = path.stat()
            if known.get(relative) != (stat.st_size, stat.st_mtime_ns):
                track = index_file(relative)
                changed += 1
                if track.read_error:
                    failed += 1
        except (OSError, ValueError):
            failed += 1
        if job:
            job.done += 1
            job.failed = failed
            job.succeeded = job.done - failed
            job.save(update_fields=["done", "failed", "succeeded"])
    if not cancelled and not walk_errors:
        Track.objects.exclude(path__in=seen).delete()
    rebuild_albums()
    return {
        "discovered": len(files),
        "changed": changed,
        "failed": failed,
        "cancelled": cancelled,
        "walk_errors": walk_errors,
    }
