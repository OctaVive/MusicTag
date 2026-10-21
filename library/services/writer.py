"""All mutations pass here. Full copies (never hardlinks) protect against in-place tag writes."""

import hashlib
import os
import shutil
import threading
from pathlib import Path

from django.conf import settings
from django.utils import timezone

from library.models import Operation, OperationEntry
from . import covers
from .fields import validate_patch
from .formats.registry import EXTENSIONS, adapter
from .library_index import index_file, rebuild_albums
from .settings_service import contained, get

WRITE_LOCK = threading.RLock()


def fingerprint(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def finish(operation):
    entries = operation.entries.all()
    operation.status = "partial" if entries.exclude(status="success").exists() else "success"
    operation.track_count = entries.count()
    operation.finished_at = timezone.now()
    operation.save()


def write(track, patch, *, operation=None, expected=None, cover_hash=None, restore=None, aggregate=True):
    patch, warnings = validate_patch(patch)
    if track.format in {"mp3", "wav"} and int(get("id3_version", 4)) == 3:
        warnings.append(
            "ID3v2.3 compatibility mode joins multiple values with /; prefer v2.4 for exact interoperability."
        )
    with WRITE_LOCK:
        path = contained(track.path, EXTENSIONS)
        before_fingerprint = fingerprint(path)
        if expected and before_fingerprint != expected:
            raise ValueError("File changed since preview; generate a new preview.")
        before = adapter(path).read()
        before_cover = covers.cache(before.cover)
        operation = operation or Operation.objects.create(kind="edit", summary=track.path)
        entry = OperationEntry.objects.create(
            operation=operation,
            track=track,
            path=track.path,
            before_tags=before.tags,
            before_cover=before_cover,
            before_fingerprint=before_fingerprint,
        )
        backup_dir = settings.STATE_DIR / "backups" / str(operation.pk)
        backup_dir.mkdir(parents=True, exist_ok=True)
        backup = backup_dir / str(entry.pk)
        entry.backup = str(backup.relative_to(settings.STATE_DIR))
        entry.save(update_fields=["backup"])
        mutated = False
        try:
            shutil.copy2(path, backup)
            # A complete, flushed backup must exist before opening the original for mutation.
            with backup.open("rb+") as stream:
                os.fsync(stream.fileno())
            if fingerprint(backup) != before_fingerprint or fingerprint(path) != before_fingerprint:
                raise ValueError("File changed during backup; retry with a new preview.")
            mutated = True
            if restore:
                shutil.copy2(restore, path)
            else:
                cover = covers.original(cover_hash) if cover_hash else None
                adapter(path).write(patch, cover, cover_hash is not None, version=int(get("id3_version", 4)))
            with path.open("rb+") as stream:
                os.fsync(stream.fileno())
            after = adapter(path).read()
            for key, values in patch.items():
                actual = after.tags.get(key, [])
                # ID3 normalizes numeric formatting and an absent number with a total to zero.
                if key.endswith(("NUMBER", "TOTAL")) and values and actual:
                    equal = int(values[0]) == int(actual[0])
                else:
                    equal = actual == values
                if not equal:
                    raise ValueError(f"Verification failed for {key}: expected {values!r}, read {actual!r}.")
            if cover_hash is not None and covers.cache(after.cover) != (cover_hash or ""):
                raise ValueError("Cover verification failed.")
            if restore and fingerprint(path) != fingerprint(Path(restore)):
                raise ValueError("Undo verification failed.")
            entry.after_tags = after.tags
            entry.after_cover = covers.cache(after.cover)
            entry.after_fingerprint = fingerprint(path)
            entry.status = "success"
            entry.save()
            index_file(track.path, after)
            if aggregate:
                rebuild_albums()
        except Exception as exc:
            error = str(exc)
            if mutated:
                try:
                    shutil.copy2(backup, path)
                    index_file(track.path)
                except Exception as rollback:
                    error += f" RESTORE FAILED: {rollback}. Recover manually from {backup}."
            entry.status, entry.error = "failed", error
            entry.save(update_fields=["status", "error"])
            if isinstance(exc, PermissionError):
                error = "File in use or not writable. Pause playback and retry. " + error
            finish(operation)
            raise ValueError(error) from exc
        finish(operation)
        return entry, warnings


def undo(operation_id, job=None):
    original = Operation.objects.get(pk=operation_id)
    operation = Operation.objects.create(kind="undo", summary=f"Undo operation #{original.pk}")
    if job:
        job.total = original.entries.filter(status="success").count()
        job.result = {"operation": operation.pk}
        job.save(update_fields=["total", "result"])
    with WRITE_LOCK:
        for entry in original.entries.filter(status="success").order_by("-id"):
            if job:
                job.refresh_from_db(fields=["cancel_requested"])
                if job.cancel_requested:
                    break
            try:
                if not entry.track_id:
                    raise ValueError("Track is no longer indexed. Rescan before undo.")
                backup = (settings.STATE_DIR / entry.backup).resolve(strict=True)
                if not backup.is_relative_to((settings.STATE_DIR / "backups").resolve()):
                    raise ValueError("Invalid backup path.")
                if not entry.before_fingerprint or fingerprint(backup) != entry.before_fingerprint:
                    raise ValueError("Backup integrity check failed. No file was changed.")
                write(
                    entry.track,
                    {},
                    operation=operation,
                    expected=entry.after_fingerprint,
                    restore=backup,
                    aggregate=False,
                )
            except Exception as exc:
                # Pre-write failures also remain visible in history.
                if not operation.entries.filter(path=entry.path).exists():
                    OperationEntry.objects.create(
                        operation=operation,
                        track=entry.track,
                        path=entry.path,
                        status="failed",
                        error=str(exc),
                    )
            if job:
                job.done += 1
                job.succeeded = operation.entries.filter(status="success").count()
                job.failed = job.done - job.succeeded
                job.save(update_fields=["done", "succeeded", "failed"])
        rebuild_albums()
        finish(operation)
    return operation
