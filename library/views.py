import json
import mimetypes
import re
from functools import wraps
from pathlib import Path

from django.conf import settings as django_settings
from django.core import signing
from django.core.paginator import Paginator
from django.http import FileResponse, Http404, HttpResponse, JsonResponse, StreamingHttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from library.models import Album, Job, Operation, ParserPattern, Preset, Track
from library.services import bulk, covers, jobs, musicbrainz, search, settings_service, tools
from library.services.fields import FIELDS
from library.services.formats.registry import EXTENSIONS, adapter
from library.services.writer import write


def guarded(function):
    @wraps(function)
    @require_POST
    def wrapped(request, *args, **kwargs):
        if not request.session.get("unlocked"):
            return error(request, "Writes are disabled. Explicitly unlock first.", 403)
        try:
            return function(request, *args, **kwargs)
        except (ValueError, OSError, signing.BadSignature, KeyError, TypeError) as exc:
            return error(request, str(exc), 422)

    return wrapped


def error(request, message, status=422):
    return render(request, "library/error.html", {"error": message}, status=status)


def ids(request):
    raw = request.POST.getlist("ids")
    if not raw:
        raw = request.GET.getlist("ids")
    return [
        int(v)
        for item in raw
        for v in item.split(",")
        if re.fullmatch(r"[0-9]{1,19}", v.strip()) and 0 < int(v) < 2**63
    ]


def selected(request):
    if request.POST.get("all_filtered") == "1":
        return list(search.tracks(request.POST).values_list("pk", flat=True))
    return ids(request)


def operation_fields(request):
    result = {}
    for key in FIELDS:
        if request.POST.get("include_" + key):
            result[key] = {
                "mode": request.POST.get("mode_" + key, "replace"),
                "values": request.POST.get("field_" + key, ""),
            }
    return result


def home(request):
    if not settings_service.get("library_root"):
        return redirect("onboarding")
    if request.GET.get("view") == "tracks":
        return tracks(request)
    queryset = Album.objects.all()
    filtered = search.tracks(request.GET)
    if any(
        request.GET.get(k) for k in ["q", "format", "cover", "issue", "artist", "genre", "year", "folder"]
    ):
        queryset = queryset.filter(pk__in=filtered.values("album_group_id"))
    sort = request.GET.get("sort", "album_artist")
    if sort.removeprefix("-") not in {"album_artist", "title", "year", "updated_at", "issue_count"}:
        sort = "album_artist"
    page = Paginator(queryset.order_by(sort, "pk"), 60).get_page(request.GET.get("page"))
    return render(
        request, "library/albums.html", {"page": page, "heading": "Albums", "album_count": queryset.count()}
    )


def tracks(request):
    queryset = search.tracks(request.GET)
    page = Paginator(queryset, 100).get_page(request.GET.get("page"))
    return render(
        request, "library/tracks.html", {"page": page, "heading": "Tracks", "result_count": queryset.count()}
    )


def album(request, key):
    item = get_object_or_404(Album, key=key)
    params = request.GET.copy()
    params["album"] = str(item.pk)
    page = Paginator(search.tracks(params), 100).get_page(request.GET.get("page"))
    return render(
        request, "library/album.html", {"album": item, "tracks": page, "page": page, "heading": item.title}
    )


def folders(request):
    folder = request.GET.get("folder", "").strip("/")
    queryset = Track.objects.filter(folder__startswith=folder + "/") if folder else Track.objects.all()
    descendants = queryset.values_list("folder", flat=True).distinct()
    prefix = folder + "/" if folder else ""
    children = sorted(
        {
            prefix + value[len(prefix) :].split("/")[0]
            for value in descendants
            if value.startswith(prefix) and value != folder
        }
    )
    files = search.tracks(request.GET).filter(folder=folder)
    page = Paginator(files, 100).get_page(request.GET.get("page"))
    parent = Path(folder).parent.as_posix()
    return render(
        request,
        "library/folders.html",
        {
            "folders": children,
            "tracks": page,
            "page": page,
            "heading": folder or "Folders",
            "parent_folder": "" if parent == "." else parent,
            "folder": folder,
        },
    )


def field_groups(tags, mixed=None):
    groups = {}
    for key, field in FIELDS.items():
        groups.setdefault(field.group, []).append(
            {"field": field, "value": "; ".join(tags.get(key, [])), "mixed": mixed and key in mixed}
        )
    return groups.items()


def inspector(request, track_id):
    track = get_object_or_404(Track, pk=track_id)
    try:
        snapshot = adapter(settings_service.contained(track.path, EXTENSIONS)).read()
        tags, raw = snapshot.tags, snapshot.raw
        from library.services.writer import fingerprint

        expected = fingerprint(settings_service.contained(track.path, EXTENSIONS))
    except Exception as exc:
        return error(request, f"{track.path}: {exc}")
    return render(
        request,
        "library/inspector.html",
        {
            "track": track,
            "groups": field_groups(tags),
            "raw": raw,
            "expected": expected,
            "standalone": not request.headers.get("HX-Request"),
        },
    )


@guarded
def save_track(request, track_id):
    track = get_object_or_404(Track, pk=track_id)
    patch = {key: request.POST.get("field_" + key, "") for key in FIELDS if request.POST.get("dirty_" + key)}
    if not request.POST.get("expected"):
        raise ValueError("Reload the editor before saving.")
    _, warnings = write(track, patch, expected=request.POST["expected"])
    if not request.headers.get("HX-Request"):
        return redirect("inspector", track_id=track.pk)
    response = inspector(request, track_id)
    response["HX-Trigger-After-Swap"] = json.dumps(
        {
            "library:refresh": True,
            "toast": "Tags saved. " + (" ".join(warnings) if warnings else "Undo is available in History."),
        }
    )
    return response


@require_POST
def lock(request):
    request.session["unlocked"] = request.POST.get("unlock") == "1"
    return redirect(
        request.POST.get("next")
        if request.POST.get("next", "").startswith("/") and not request.POST.get("next", "").startswith("//")
        else "/"
    )


def onboarding(request):
    if request.method == "POST":
        try:
            settings_service.configure_root(request.POST.get("root", ""))
            job = jobs.enqueue("scan")
            return redirect("job", job_id=job.pk)
        except (ValueError, OSError) as exc:
            return render(request, "library/onboarding.html", {"error": str(exc)}, status=422)
    return render(request, "library/onboarding.html")


@require_POST
def scan_action(request):
    if Job.objects.filter(kind="scan", status__in=["queued", "running"]).exists():
        return error(request, "A scan is already queued or running.")
    return started(request, jobs.enqueue("scan"))


def started(request, job):
    if request.headers.get("HX-Request"):
        return render(request, "library/job.html", {"job": job}, status=202)
    return redirect("job", job_id=job.pk)


def job_view(request, job_id):
    job = get_object_or_404(Job, pk=job_id)
    jobs.ensure_worker()
    operation = Operation.objects.filter(pk=job.result.get("operation")).first()
    return render(
        request,
        "library/job.html",
        {"job": job, "operation": operation, "standalone": not request.headers.get("HX-Request")},
    )


@require_POST
def cancel_job(request, job_id):
    Job.objects.filter(pk=job_id, status__in=["queued", "running"]).update(cancel_requested=True)
    return redirect("job", job_id=job_id)


@guarded
def retry_job(request, job_id):
    job = get_object_or_404(Job, pk=job_id, kind="bulk")
    if job.status in {"queued", "running"}:
        raise ValueError("Wait for the job to finish.")
    operation = get_object_or_404(Operation, pk=job.result.get("operation"))
    failed = set(operation.entries.filter(status="failed").values_list("track_id", flat=True))
    plans = [plan for plan in job.payload["plans"] if plan["id"] in failed]
    return started(request, jobs.enqueue("bulk", {"plans": plans}))


def bulk_editor(request):
    selection = selected(request)
    records = list(Track.objects.filter(pk__in=selection))
    common, mixed = {}, set()
    for key in FIELDS:
        values = [t.tags.get(key, []) for t in records]
        if values and all(v == values[0] for v in values):
            common[key] = values[0]
        else:
            mixed.add(key)
    return render(
        request,
        "library/bulk.html",
        {
            "selection": selection,
            "groups": field_groups(common, mixed),
            "presets": Preset.objects.all(),
            "heading": "Edit selection",
        },
    )


@guarded
def preview_action(request):
    selection = selected(request)
    operations = operation_fields(request)
    if request.POST.get("preset"):
        operations = get_object_or_404(Preset, pk=request.POST["preset"]).fields
    cover_hash = None
    if request.FILES.get("cover"):
        data, _ = covers.normalize(request.FILES["cover"].read(11 * 1024 * 1024))
        cover_hash = covers.cache(data)
    elif request.POST.get("remove_cover"):
        cover_hash = ""
    if not operations and cover_hash is None:
        raise ValueError("Include at least one field or artwork change.")
    rows, token = bulk.preview(selection, operations, cover_hash=cover_hash)
    return render(
        request,
        "library/preview.html",
        {
            "rows": rows,
            "token": token,
            "count": len(rows),
            "threshold": settings_service.get("confirmation_threshold", 20),
        },
    )


@guarded
def apply_action(request):
    plans = bulk.decode(request.POST.get("token", ""))
    if len(plans) > int(settings_service.get("confirmation_threshold", 20)) and not request.POST.get(
        "confirm"
    ):
        raise ValueError("Confirm this large batch before applying.")
    if not plans:
        raise ValueError("No valid files to apply.")
    return started(request, jobs.enqueue("bulk", {"plans": plans}))


@guarded
def cover_action(request, track_id):
    track = get_object_or_404(Track, pk=track_id)
    if not request.POST.get("expected"):
        raise ValueError("Reload the editor before changing artwork.")
    action = request.POST.get("action")
    cover_hash = ""
    if action == "folder":
        for name in ["cover.jpg", "cover.png", "folder.jpg", "folder.png"]:
            relative = (Path(track.folder) / name).as_posix()
            try:
                path = settings_service.contained(relative, {".jpg", ".png"})
                data, _ = covers.normalize(path.read_bytes())
                cover_hash = covers.cache(data)
                break
            except FileNotFoundError:
                continue
        if not cover_hash:
            raise ValueError("No cover.jpg, cover.png, folder.jpg or folder.png found.")
    elif action == "replace":
        if not request.FILES.get("cover"):
            raise ValueError("Choose a cover image first.")
        data, _ = covers.normalize(request.FILES["cover"].read(11 * 1024 * 1024))
        cover_hash = covers.cache(data)
    elif action != "remove":
        raise ValueError("Unknown cover action.")
    write(track, {}, cover_hash=cover_hash, expected=request.POST.get("expected"))
    return redirect("inspector", track_id=track.pk)


def export_cover(request, track_id):
    track = get_object_or_404(Track, pk=track_id)
    snapshot = adapter(settings_service.contained(track.path, EXTENSIONS)).read()
    if not snapshot.cover:
        raise Http404("No front cover.")
    response = HttpResponse(snapshot.cover, content_type=snapshot.mime or "application/octet-stream")
    extension = {"image/png": "png", "image/webp": "webp"}.get(snapshot.mime, "jpg")
    response["Content-Disposition"] = f'attachment; filename="cover.{extension}"'
    return response


def history(request):
    return render(
        request,
        "library/history.html",
        {
            "operations": Paginator(Operation.objects.prefetch_related("entries"), 20).get_page(
                request.GET.get("page")
            ),
            "heading": "Undo history",
        },
    )


@guarded
def undo_action(request, operation_id):
    get_object_or_404(Operation, pk=operation_id)
    return started(request, jobs.enqueue("undo", {"operation": operation_id}))


@guarded
def undo_latest(request):
    operation = Operation.objects.filter(entries__status="success").order_by("-id").first()
    if not operation:
        raise ValueError("There are no successful operations to undo.")
    return started(request, jobs.enqueue("undo", {"operation": operation.pk}))


def quality(request):
    queryset = search.tracks(request.GET).exclude(issue_flags=[])
    counts = {}
    for flags in Track.objects.values_list("issue_flags", flat=True):
        for flag in flags:
            counts[flag] = counts.get(flag, 0) + 1
    return render(
        request,
        "library/quality.html",
        {
            "page": Paginator(queryset, 100).get_page(request.GET.get("page")),
            "issues": sorted(counts.items()),
            "heading": "Library quality",
        },
    )


def tool_page(request, kind):
    if kind not in {"parser", "numbering", "presets", "lookup"}:
        raise Http404
    return render(
        request,
        "library/tool.html",
        {
            "kind": kind,
            "heading": kind.title(),
            "selection": ids(request),
            "patterns": ParserPattern.objects.all(),
            "presets": Preset.objects.all(),
        },
    )


@guarded
def tool_preview(request, kind):
    selection = selected(request)
    records = list(Track.objects.filter(pk__in=selection).order_by("path"))
    if kind == "parser":
        patches = {
            str(t.pk): tools.parse_filename(
                t.filename, request.POST.get("template", "{track} - {artist} - {title}")
            )
            for t in records
        }
        if request.POST.get("pattern_name"):
            ParserPattern.objects.update_or_create(
                name=request.POST["pattern_name"][:100], defaults={"template": request.POST["template"]}
            )
    elif kind == "numbering":
        patches = tools.numbering(
            records,
            int(request.POST.get("start", 1)),
            request.POST.get("scope", "album"),
            bool(request.POST.get("totals")),
            bool(request.POST.get("discs")),
        )
    elif kind == "lookup":
        data = musicbrainz.release(request.POST.get("release", ""))
        patches = musicbrainz.match_release(records, data)
        included = request.POST.getlist("lookup_fields")
        patches = {
            key: {field: values for field, values in patch.items() if field in included}
            for key, patch in patches.items()
        }
        if not included:
            raise ValueError("Select lookup fields to include.")
    else:
        raise ValueError("Unknown tool.")
    cover_hash = None
    if kind == "lookup" and request.POST.get("lookup_cover"):
        cover_hash = covers.cache(
            musicbrainz.download_cover(request.POST["release"], request.POST["lookup_cover"])
        )
    rows, token = bulk.preview(selection, patches=patches, cover_hash=cover_hash)
    return render(
        request,
        "library/preview.html",
        {
            "rows": rows,
            "token": token,
            "count": len(rows),
            "threshold": settings_service.get("confirmation_threshold", 20),
        },
    )


@guarded
def preset_action(request):
    if request.POST.get("delete"):
        Preset.objects.filter(pk=request.POST["delete"]).delete()
    else:
        name = request.POST.get("name", "").strip()
        if not name:
            raise ValueError("Give the preset a name.")
        operations = operation_fields(request)
        from library.services.fields import apply_operations

        apply_operations({}, operations)
        Preset.objects.update_or_create(name=name[:100], defaults={"fields": operations})
    return redirect("tool", kind="presets")


def lookup_search(request):
    releases, message = [], ""
    try:
        if request.GET.get("query"):
            releases = musicbrainz.search(request.GET["query"])
    except ValueError as exc:
        message = str(exc)
    return render(request, "library/lookup_results.html", {"releases": releases, "error": message})


def lookup_release(request, identifier):
    try:
        data = musicbrainz.release(identifier)
        candidates, cover_error = [], ""
        try:
            candidates = musicbrainz.cover_candidates(identifier)
        except ValueError as exc:
            cover_error = str(exc)
        return render(
            request,
            "library/release.html",
            {"release": data, "candidates": candidates, "cover_error": cover_error},
        )
    except ValueError as exc:
        return error(request, str(exc))


def settings_page(request):
    return render(
        request,
        "library/settings.html",
        {
            "heading": "Settings",
            "id3_version": settings_service.get("id3_version", 4),
            "contact": settings_service.get("musicbrainz_contact", ""),
            "cover_limit": settings_service.get("cover_limit_mb", 10),
            "threshold": settings_service.get("confirmation_threshold", 20),
        },
    )


@require_POST
def settings_action(request):
    try:
        settings_service.configure_root(request.POST.get("root", ""))
        version = int(request.POST.get("id3_version", 4))
        if version not in {3, 4}:
            raise ValueError("Choose ID3 v2.3 or v2.4.")
        limit = int(request.POST.get("cover_limit", 10))
        threshold = int(request.POST.get("threshold", 20))
        if not 1 <= limit <= 10 or not 1 <= threshold <= 1000:
            raise ValueError("Cover limit must be 1–10 MB; confirmation threshold 1–1000.")
        for key, value in {
            "id3_version": version,
            "cover_limit_mb": limit,
            "confirmation_threshold": threshold,
            "musicbrainz_contact": request.POST.get("contact", "")[:200],
        }.items():
            settings_service.set_value(key, value)
    except (ValueError, OSError) as exc:
        return error(request, str(exc))
    return redirect("settings")


def health(request):
    return JsonResponse({"status": "ok", "version": "1.0.0"})


def audio(request, track_id):
    track = get_object_or_404(Track, pk=track_id)
    try:
        path = settings_service.contained(track.path, EXTENSIONS)
        size = path.stat().st_size
    except (OSError, ValueError) as exc:
        raise Http404(str(exc)) from exc
    start, end, partial = 0, size - 1, False
    range_header = request.headers.get("Range")
    if range_header:
        match = re.fullmatch(r"bytes=(\d*)-(\d*)", range_header)
        if not match or not any(match.groups()):
            response = HttpResponse(status=416)
            response["Content-Range"] = f"bytes */{size}"
            return response
        left, right = match.groups()
        if left:
            start, end = int(left), min(int(right), size - 1) if right else size - 1
        else:
            start, end = max(0, size - int(right)), size - 1
        if start > end or start >= size:
            response = HttpResponse(status=416)
            response["Content-Range"] = f"bytes */{size}"
            return response
        partial = True

    def chunks():
        with path.open("rb") as stream:
            stream.seek(start)
            remaining = end - start + 1
            while remaining > 0:
                block = stream.read(min(65536, remaining))
                if not block:
                    break
                remaining -= len(block)
                yield block

    response = StreamingHttpResponse(
        chunks(),
        status=206 if partial else 200,
        content_type=mimetypes.guess_type(path.name)[0] or "application/octet-stream",
    )
    response["Accept-Ranges"] = "bytes"
    response["Content-Length"] = max(0, end - start + 1)
    if partial:
        response["Content-Range"] = f"bytes {start}-{end}/{size}"
    return response


def thumbnail(request, digest):
    if not re.fullmatch("[a-f0-9]{64}", digest):
        raise Http404
    size = request.GET.get("size", "320")
    if size not in {"96", "320", "orig"}:
        raise Http404
    if request.headers.get("If-None-Match") == f'"{digest}-{size}"':
        return HttpResponse(status=304)
    path = (
        django_settings.STATE_DIR
        / "cache"
        / "covers"
        / digest
        / ("original" if size == "orig" else f"{size}.jpg")
    )
    if not path.is_file():
        raise Http404
    response = FileResponse(
        path.open("rb"), content_type="application/octet-stream" if size == "orig" else "image/jpeg"
    )
    response["ETag"] = f'"{digest}-{size}"'
    response["Cache-Control"] = "public, max-age=31536000, immutable"
    return response


def queue(request):
    queryset = search.tracks(request.GET)
    if request.GET.get("ids"):
        selection = ids(request)
        queryset = queryset.filter(pk__in=selection)
    data = [
        {
            "id": t.pk,
            "title": t.title or t.filename,
            "artist": t.artist,
            "album": t.album,
            "duration": t.duration,
            "cover": t.cover_hash,
        }
        for t in queryset[:1000]
    ]
    return JsonResponse({"tracks": data, "capped": queryset.count() > 1000})


def selection_ids(request):
    return JsonResponse({"ids": list(search.tracks(request.GET).values_list("pk", flat=True))})
