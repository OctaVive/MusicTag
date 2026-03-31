from __future__ import annotations

import mimetypes
import json
import re
import urllib.parse
import urllib.request
from collections import defaultdict
from pathlib import Path

from django.conf import settings
from django.http import FileResponse, HttpRequest, HttpResponseBadRequest, JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET, require_POST

from .services.file_scanner import ScanConfig, build_tree, is_safe_relative_path
from .services.tag_service import (
    TagPayload,
    remove_cover_image,
    read_audio_metadata,
    update_id3_tags_explicit,
    write_audio_metadata,
    write_cover_image,
)

SESSION_UNLOCK_KEY = "tagger_unlocked"
PRESETS_FILENAME = "presets.json"
LAST_SNAPSHOT_FILENAME = "last_snapshot.json"


def _state_dir() -> Path:
    state_dir = Path(settings.BASE_DIR) / ".musictag_state"
    state_dir.mkdir(parents=True, exist_ok=True)
    return state_dir


def _presets_file() -> Path:
    return _state_dir() / PRESETS_FILENAME


def _snapshot_file() -> Path:
    return _state_dir() / LAST_SNAPSHOT_FILENAME


def _read_json_file(path: Path, fallback):
    if not path.exists():
        return fallback
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return fallback


def _write_json_file(path: Path, data) -> None:
    path.write_text(json.dumps(data, ensure_ascii=True, indent=2), encoding="utf-8")


def _allowed_exts() -> set[str]:
    return {ext.lower() for ext in settings.SUPPORTED_AUDIO_EXTENSIONS}


def _validate_numeric_like(value: str, field_name: str):
    if value and not value.replace("/", "").isdigit():
        raise ValueError(f"{field_name} must be numeric, optionally like 1/10")


def _safe_audio_target(relative_path: str) -> Path:
    target = is_safe_relative_path(Path(settings.MUSIC_ROOT), relative_path)
    if not target.exists() or not target.is_file():
        raise ValueError("File not found")
    if target.suffix.lower() not in _allowed_exts():
        raise ValueError("Unsupported file extension")
    return target


def _snapshot_targets(paths: list[str]) -> None:
    snapshot_entries = []
    for rel in paths:
        try:
            target = _safe_audio_target(rel)
            snapshot_entries.append({"path": rel, "tags": read_audio_metadata(target)})
        except Exception:
            continue
    _write_json_file(_snapshot_file(), {"entries": snapshot_entries})


def _build_payload_from_source(source: dict[str, str]) -> TagPayload:
    def _s(key: str) -> str:
        value = source.get(key)
        if value is None:
            return ""
        return str(value).strip()

    return TagPayload(
        title=_s("TITLE"),
        artist=_s("ARTIST"),
        album=_s("ALBUM"),
        albumartist=_s("ALBUMARTIST"),
        tracknumber=_s("TRACKNUMBER"),
        genre=_s("GENRE"),
        year=_s("YEAR"),
        discnumber=_s("DISCNUMBER"),
    )


def _apply_payload(target: Path, payload: TagPayload) -> None:
    try:
        write_audio_metadata(target, payload)
    except Exception:
        update_id3_tags_explicit(target, payload)


def _parse_filename(stem: str, pattern: str) -> dict[str, str]:
    # Supported quick profiles for untagged download sets.
    if pattern == "track-title":
        match = re.match(r"^\s*(\d+)\s*[-_. ]+\s*(.+)$", stem)
        if match:
            return {"TRACKNUMBER": match.group(1), "TITLE": match.group(2).strip()}
    elif pattern == "track-artist-title":
        match = re.match(r"^\s*(\d+)\s*[-_. ]+\s*(.+?)\s*[-_. ]+\s*(.+)$", stem)
        if match:
            return {"TRACKNUMBER": match.group(1), "ARTIST": match.group(2).strip(), "TITLE": match.group(3).strip()}
    elif pattern == "artist-title":
        match = re.match(r"^\s*(.+?)\s*[-_. ]+\s*(.+)$", stem)
        if match:
            return {"ARTIST": match.group(1).strip(), "TITLE": match.group(2).strip()}
    return {"TITLE": stem.strip()}


def index(request: HttpRequest):
    request.session.setdefault(SESSION_UNLOCK_KEY, False)
    return render(
        request,
        "tagger/index.html",
        {
            "locked": not bool(request.session.get(SESSION_UNLOCK_KEY, False)),
        },
    )


@require_GET
def api_tree(request: HttpRequest):
    config = ScanConfig(
        root=Path(settings.MUSIC_ROOT),
        allowed_extensions={ext.lower() for ext in settings.SUPPORTED_AUDIO_EXTENSIONS},
    )
    try:
        tree = build_tree(config)
    except FileNotFoundError:
        return JsonResponse({"error": "Configured MUSIC_ROOT does not exist."}, status=400)
    return JsonResponse({"tree": tree, "unlocked": bool(request.session.get(SESSION_UNLOCK_KEY, False))})


@require_GET
def api_file(request: HttpRequest):
    relative_path = request.GET.get("path", "").strip()
    if not relative_path:
        return HttpResponseBadRequest("Missing file path")
    try:
        target = is_safe_relative_path(Path(settings.MUSIC_ROOT), relative_path)
    except ValueError:
        return JsonResponse({"error": "Invalid file path"}, status=400)
    if not target.exists() or not target.is_file():
        return JsonResponse({"error": "File not found"}, status=404)
    if target.suffix.lower() not in {ext.lower() for ext in settings.SUPPORTED_AUDIO_EXTENSIONS}:
        return JsonResponse({"error": "Unsupported file extension"}, status=400)

    try:
        metadata = read_audio_metadata(target)
    except ValueError as exc:
        return JsonResponse({"error": str(exc)}, status=400)
    except Exception as exc:  # noqa: BLE001
        return JsonResponse({"error": f"Failed to read metadata: {exc}"}, status=500)
    return JsonResponse({"path": relative_path, "tags": metadata})


@require_POST
def api_lock(request: HttpRequest):
    try:
        payload = json.loads(request.body.decode("utf-8"))
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON body"}, status=400)
    unlocked = bool(payload.get("unlocked", False))
    request.session[SESSION_UNLOCK_KEY] = unlocked
    return JsonResponse({"unlocked": unlocked})


@require_POST
def api_save(request: HttpRequest):
    if not bool(request.session.get(SESSION_UNLOCK_KEY, False)):
        return JsonResponse({"error": "Unlock before saving changes."}, status=403)

    relative_path = (request.POST.get("path") or "").strip()
    if not relative_path:
        return JsonResponse({"error": "Missing file path"}, status=400)
    try:
        target = _safe_audio_target(relative_path)
    except ValueError as exc:
        return JsonResponse({"error": str(exc)}, status=400)

    payload = _build_payload_from_source(request.POST)
    try:
        _validate_numeric_like(payload.tracknumber, "TRACKNUMBER")
        _validate_numeric_like(payload.discnumber, "DISCNUMBER")
    except ValueError as exc:
        return JsonResponse({"error": str(exc)}, status=400)

    try:
        _snapshot_targets([relative_path])
        _apply_payload(target, payload)

        cover = request.FILES.get("cover")
        if cover:
            write_cover_image(target, cover.name, cover.read())

        metadata = read_audio_metadata(target)
    except ValueError as exc:
        return JsonResponse({"error": str(exc)}, status=400)
    except Exception as exc:  # noqa: BLE001
        return JsonResponse({"error": f"Failed to save metadata: {exc}"}, status=500)

    return JsonResponse({"ok": True, "tags": metadata})


@require_POST
def api_save_bulk(request: HttpRequest):
    if not bool(request.session.get(SESSION_UNLOCK_KEY, False)):
        return JsonResponse({"error": "Unlock before saving changes."}, status=403)

    try:
        payload_json = json.loads(request.body.decode("utf-8"))
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON body"}, status=400)
    bulk_mode = (payload_json.get("bulk_mode") or "compilation").strip().lower()
    if bulk_mode not in {"compilation", "template"}:
        return JsonResponse({"error": "Invalid bulk_mode. Use compilation or template."}, status=400)

    paths = payload_json.get("paths") or []
    if not isinstance(paths, list) or not paths:
        return JsonResponse({"error": "No file paths provided"}, status=400)
    apply_fields = payload_json.get("apply_fields") or []
    if not isinstance(apply_fields, list) or not apply_fields:
        return JsonResponse({"error": "No apply_fields provided."}, status=400)
    apply_fields_normalized = [str(item).strip().upper() for item in apply_fields if str(item).strip()]
    if not apply_fields_normalized:
        return JsonResponse({"error": "No valid apply_fields provided."}, status=400)

    payload = _build_payload_from_source(payload_json)
    try:
        _validate_numeric_like(payload.tracknumber, "TRACKNUMBER")
        _validate_numeric_like(payload.discnumber, "DISCNUMBER")
    except ValueError as exc:
        return JsonResponse({"error": str(exc)}, status=400)

    if bulk_mode == "compilation":
        if payload.artist:
            return JsonResponse({"error": "ARTIST is not allowed in compilation mode."}, status=400)
        allowed_apply_fields = {"ALBUM", "ALBUMARTIST", "YEAR", "GENRE"}
        invalid = [field for field in apply_fields_normalized if field not in allowed_apply_fields]
        if invalid:
            return JsonResponse({"error": f"Fields not allowed in compilation mode: {', '.join(invalid)}"}, status=400)
        selected_fields = {
            "album": payload.album,
            "albumartist": payload.albumartist,
            "genre": payload.genre,
            "year": payload.year,
        }
    else:
        allowed_apply_fields = {"ALBUM", "ALBUMARTIST", "TRACKNUMBER", "GENRE", "YEAR", "DISCNUMBER", "ARTIST"}
        invalid = [field for field in apply_fields_normalized if field not in allowed_apply_fields]
        if invalid:
            return JsonResponse({"error": f"Fields not allowed in template mode: {', '.join(invalid)}"}, status=400)
        selected_fields = {
            "album": payload.album,
            "albumartist": payload.albumartist,
            "tracknumber": payload.tracknumber,
            "genre": payload.genre,
            "year": payload.year,
            "discnumber": payload.discnumber,
            "artist": payload.artist,
        }
    field_map = {
        "ALBUM": "album",
        "ALBUMARTIST": "albumartist",
        "TRACKNUMBER": "tracknumber",
        "GENRE": "genre",
        "YEAR": "year",
        "DISCNUMBER": "discnumber",
        "ARTIST": "artist",
    }
    selected_keys = {field_map[field] for field in apply_fields_normalized if field in field_map}
    non_empty_fields = {k: v for k, v in selected_fields.items() if (k in selected_keys and v != "")}
    if not non_empty_fields:
        return JsonResponse({"error": "Provide at least one non-empty bulk field."}, status=400)

    updated = 0
    failed: list[dict[str, str]] = []
    skipped = 0
    _snapshot_targets([str(path).strip() for path in paths if str(path).strip()])

    for relative_path in paths:
        try:
            rel = str(relative_path).strip()
            if not rel:
                skipped += 1
                continue
            target = _safe_audio_target(rel)

            current = read_audio_metadata(target)
            file_payload = TagPayload(
                title=current.get("TITLE", ""),
                artist=non_empty_fields.get("artist", current.get("ARTIST", "")),
                album=non_empty_fields.get("album", current.get("ALBUM", "")),
                albumartist=non_empty_fields.get("albumartist", current.get("ALBUMARTIST", "")),
                tracknumber=non_empty_fields.get("tracknumber", current.get("TRACKNUMBER", "")),
                genre=non_empty_fields.get("genre", current.get("GENRE", "")),
                year=non_empty_fields.get("year", current.get("YEAR", "")),
                discnumber=non_empty_fields.get("discnumber", current.get("DISCNUMBER", "")),
            )
            _apply_payload(target, file_payload)
            updated += 1
        except Exception as exc:  # noqa: BLE001
            failed.append({"path": str(relative_path), "error": str(exc)})

    return JsonResponse(
        {
            "ok": True,
            "updated": updated,
            "failed": failed,
            "failed_count": len(failed),
            "skipped": skipped,
        }
    )


@require_POST
def api_parser_preview(request: HttpRequest):
    try:
        payload = json.loads(request.body.decode("utf-8"))
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON body"}, status=400)
    pattern = (payload.get("pattern") or "track-title").strip()
    paths = payload.get("paths") or []
    preview = []
    for rel in paths:
        stem = Path(str(rel)).stem
        preview.append({"path": rel, "proposed": _parse_filename(stem, pattern)})
    return JsonResponse({"ok": True, "preview": preview})


@require_POST
def api_apply_map(request: HttpRequest):
    if not bool(request.session.get(SESSION_UNLOCK_KEY, False)):
        return JsonResponse({"error": "Unlock before applying changes."}, status=403)
    try:
        payload = json.loads(request.body.decode("utf-8"))
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON body"}, status=400)
    updates = payload.get("updates") or []
    if not isinstance(updates, list) or not updates:
        return JsonResponse({"error": "No updates provided"}, status=400)
    _snapshot_targets([str(u.get("path", "")).strip() for u in updates if str(u.get("path", "")).strip()])
    updated = 0
    failed = []
    for item in updates:
        rel = str(item.get("path", "")).strip()
        fields = item.get("fields") or {}
        try:
            target = _safe_audio_target(rel)
            current = read_audio_metadata(target)
            # Keep ARTIST untouched for bulk safety.
            payload_for_file = TagPayload(
                title=(fields.get("TITLE") or current.get("TITLE", "")).strip(),
                artist=current.get("ARTIST", ""),
                album=(fields.get("ALBUM") or current.get("ALBUM", "")).strip(),
                albumartist=(fields.get("ALBUMARTIST") or current.get("ALBUMARTIST", "")).strip(),
                tracknumber=(fields.get("TRACKNUMBER") or current.get("TRACKNUMBER", "")).strip(),
                genre=(fields.get("GENRE") or current.get("GENRE", "")).strip(),
                year=(fields.get("YEAR") or current.get("YEAR", "")).strip(),
                discnumber=(fields.get("DISCNUMBER") or current.get("DISCNUMBER", "")).strip(),
            )
            _apply_payload(target, payload_for_file)
            updated += 1
        except Exception as exc:  # noqa: BLE001
            failed.append({"path": rel, "error": str(exc)})
    return JsonResponse({"ok": True, "updated": updated, "failed": failed, "failed_count": len(failed)})


@require_POST
def api_auto_number(request: HttpRequest):
    if not bool(request.session.get(SESSION_UNLOCK_KEY, False)):
        return JsonResponse({"error": "Unlock before applying numbering."}, status=403)
    try:
        payload = json.loads(request.body.decode("utf-8"))
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON body"}, status=400)
    paths = [str(p).strip() for p in (payload.get("paths") or []) if str(p).strip()]
    if not paths:
        return JsonResponse({"error": "No file paths provided"}, status=400)
    start = int(payload.get("start", 1))
    pad = int(payload.get("pad", 2))
    reset_per_folder = bool(payload.get("reset_per_folder", True))
    apply_changes = bool(payload.get("apply", False))

    grouped: dict[str, list[str]] = defaultdict(list)
    if reset_per_folder:
        for path in paths:
            grouped[str(Path(path).parent)].append(path)
    else:
        grouped["ALL"] = paths[:]

    preview = []
    for _, group_paths in grouped.items():
        for idx, rel in enumerate(sorted(group_paths), start=start):
            preview.append({"path": rel, "TRACKNUMBER": str(idx).zfill(pad)})

    if not apply_changes:
        return JsonResponse({"ok": True, "preview": preview})

    _snapshot_targets(paths)
    updated = 0
    failed = []
    for item in preview:
        rel = item["path"]
        try:
            target = _safe_audio_target(rel)
            current = read_audio_metadata(target)
            file_payload = TagPayload(
                title=current.get("TITLE", ""),
                artist=current.get("ARTIST", ""),
                album=current.get("ALBUM", ""),
                albumartist=current.get("ALBUMARTIST", ""),
                tracknumber=item["TRACKNUMBER"],
                genre=current.get("GENRE", ""),
                year=current.get("YEAR", ""),
                discnumber=current.get("DISCNUMBER", ""),
            )
            _apply_payload(target, file_payload)
            updated += 1
        except Exception as exc:  # noqa: BLE001
            failed.append({"path": rel, "error": str(exc)})
    return JsonResponse({"ok": True, "updated": updated, "failed": failed, "failed_count": len(failed)})


def api_presets(request: HttpRequest):
    if request.method == "GET":
        return JsonResponse({"presets": _read_json_file(_presets_file(), [])})
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)
    try:
        payload = json.loads(request.body.decode("utf-8"))
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON body"}, status=400)
    action = (payload.get("action") or "save").strip()
    presets = _read_json_file(_presets_file(), [])

    if action == "delete":
        name = (payload.get("name") or "").strip()
        presets = [p for p in presets if p.get("name") != name]
        _write_json_file(_presets_file(), presets)
        return JsonResponse({"ok": True, "presets": presets})

    name = (payload.get("name") or "").strip()
    values = payload.get("values") or {}
    if not name:
        return JsonResponse({"error": "Preset name is required"}, status=400)
    presets = [p for p in presets if p.get("name") != name]
    presets.append({"name": name, "values": values})
    _write_json_file(_presets_file(), presets)
    return JsonResponse({"ok": True, "presets": presets})


@require_POST
def api_preview_bulk(request: HttpRequest):
    try:
        payload = json.loads(request.body.decode("utf-8"))
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON body"}, status=400)
    paths = [str(p).strip() for p in (payload.get("paths") or []) if str(p).strip()]
    proposed = _build_payload_from_source(payload)
    fields = {
        "ALBUM": proposed.album,
        "ALBUMARTIST": proposed.albumartist,
        "TRACKNUMBER": proposed.tracknumber,
        "GENRE": proposed.genre,
        "YEAR": proposed.year,
        "DISCNUMBER": proposed.discnumber,
    }
    non_empty = {k: v for k, v in fields.items() if v != ""}
    preview = []
    for rel in paths:
        try:
            current = read_audio_metadata(_safe_audio_target(rel))
            new_values = {k: non_empty.get(k, current.get(k, "")) for k in fields}
            preview.append({"path": rel, "current": {k: current.get(k, "") for k in fields}, "new": new_values})
        except Exception as exc:  # noqa: BLE001
            preview.append({"path": rel, "error": str(exc)})
    return JsonResponse({"ok": True, "preview": preview})


@require_POST
def api_undo_last(request: HttpRequest):
    if not bool(request.session.get(SESSION_UNLOCK_KEY, False)):
        return JsonResponse({"error": "Unlock before undo."}, status=403)
    snap = _read_json_file(_snapshot_file(), {"entries": []})
    entries = snap.get("entries") or []
    if not entries:
        return JsonResponse({"error": "No snapshot found."}, status=400)
    updated = 0
    failed = []
    for item in entries:
        rel = str(item.get("path", "")).strip()
        tags = item.get("tags") or {}
        try:
            target = _safe_audio_target(rel)
            payload = _build_payload_from_source(tags)
            _apply_payload(target, payload)
            updated += 1
        except Exception as exc:  # noqa: BLE001
            failed.append({"path": rel, "error": str(exc)})
    return JsonResponse({"ok": True, "updated": updated, "failed": failed, "failed_count": len(failed)})


@require_POST
def api_quality_check(request: HttpRequest):
    try:
        payload = json.loads(request.body.decode("utf-8"))
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON body"}, status=400)
    paths = [str(p).strip() for p in (payload.get("paths") or []) if str(p).strip()]
    issues = []
    by_album: dict[str, set[str]] = defaultdict(set)
    track_per_album: dict[str, dict[str, list[str]]] = defaultdict(lambda: defaultdict(list))
    for rel in paths:
        try:
            tags = read_audio_metadata(_safe_audio_target(rel))
            album_key = tags.get("ALBUM", "").strip() or "(unknown)"
            track = tags.get("TRACKNUMBER", "").strip()
            by_album[album_key].add(tags.get("ALBUMARTIST", "").strip())
            if not tags.get("ALBUM", "").strip():
                issues.append({"path": rel, "type": "missing_album"})
            if not tags.get("ARTIST", "").strip():
                issues.append({"path": rel, "type": "missing_artist"})
            if not tags.get("cover_data_url"):
                issues.append({"path": rel, "type": "missing_cover"})
            if track:
                track_per_album[album_key][track].append(rel)
        except Exception as exc:  # noqa: BLE001
            issues.append({"path": rel, "type": "read_error", "error": str(exc)})
    for album, mapping in track_per_album.items():
        for track, rels in mapping.items():
            if len(rels) > 1:
                issues.append({"album": album, "type": "duplicate_tracknumber", "track": track, "paths": rels})
    inconsistent_albumartist = [
        {"album": album, "values": sorted(v for v in values if v)}
        for album, values in by_album.items()
        if len({v for v in values if v}) > 1
    ]
    return JsonResponse({"ok": True, "issues": issues, "inconsistent_albumartist": inconsistent_albumartist})


@require_POST
def api_cover_bulk(request: HttpRequest):
    if not bool(request.session.get(SESSION_UNLOCK_KEY, False)):
        return JsonResponse({"error": "Unlock before cover updates."}, status=403)
    paths_raw = request.POST.get("paths") or "[]"
    try:
        paths = [str(p).strip() for p in json.loads(paths_raw) if str(p).strip()]
    except Exception:
        return JsonResponse({"error": "Invalid paths payload"}, status=400)
    mode = (request.POST.get("mode") or "set").strip()
    if mode not in {"set", "remove"}:
        return JsonResponse({"error": "Invalid mode"}, status=400)
    cover = request.FILES.get("cover")
    if mode == "set" and not cover:
        return JsonResponse({"error": "Cover file is required in set mode"}, status=400)

    _snapshot_targets(paths)
    updated = 0
    failed = []
    raw_bytes = cover.read() if cover else b""
    for rel in paths:
        try:
            target = _safe_audio_target(rel)
            if mode == "set":
                write_cover_image(target, cover.name, raw_bytes)
            else:
                remove_cover_image(target)
            updated += 1
        except Exception as exc:  # noqa: BLE001
            failed.append({"path": rel, "error": str(exc)})
    return JsonResponse({"ok": True, "updated": updated, "failed": failed, "failed_count": len(failed)})


@require_GET
def api_audio(request: HttpRequest):
    relative_path = request.GET.get("path", "").strip()
    if not relative_path:
        return HttpResponseBadRequest("Missing file path")
    try:
        target = _safe_audio_target(relative_path)
    except ValueError as exc:
        return JsonResponse({"error": str(exc)}, status=400)
    content_type = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
    response = FileResponse(target.open("rb"), content_type=content_type)
    response["Accept-Ranges"] = "bytes"
    return response


@require_GET
def api_lookup(request: HttpRequest):
    artist = (request.GET.get("artist") or "").strip()
    album = (request.GET.get("album") or "").strip()
    if not artist and not album:
        return JsonResponse({"error": "Provide artist and/or album"}, status=400)
    query_bits = []
    if artist:
        query_bits.append(f'artist:"{artist}"')
    if album:
        query_bits.append(f'release:"{album}"')
    query = " AND ".join(query_bits)
    url = "https://musicbrainz.org/ws/2/release/?" + urllib.parse.urlencode({"query": query, "fmt": "json", "limit": 5})
    req = urllib.request.Request(url, headers={"User-Agent": "MusicTag/1.0 (local app)"})
    try:
        with urllib.request.urlopen(req, timeout=8) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except Exception as exc:  # noqa: BLE001
        return JsonResponse({"error": f"Lookup failed: {exc}"}, status=502)

    suggestions = []
    for release in payload.get("releases", []):
        suggestions.append(
            {
                "title": release.get("title", ""),
                "date": release.get("date", ""),
                "id": release.get("id", ""),
                "artist": ", ".join(c.get("name", "") for c in release.get("artist-credit", []) if c.get("name")),
            }
        )
    return JsonResponse({"ok": True, "suggestions": suggestions})
