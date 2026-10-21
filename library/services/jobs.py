import threading
import time

from django.conf import settings
from django.db import close_old_connections
from django.utils import timezone

from library.models import Job, Operation, OperationEntry, Track

_guard = threading.Lock()
_thread = None
_bootstrapped = False


def bootstrap():
    """Called once by the serving entry point, never by migrate/test/maintenance."""
    global _bootstrapped
    if not settings.MUSICTAG_WORKER or _bootstrapped:
        return
    _bootstrapped = True
    from django.db import OperationalError
    from .settings_service import get

    try:
        # A crash can leave an incomplete write. Recovery must be deliberate, not automatic.
        if (
            Job.objects.filter(status="running").exists()
            or OperationEntry.objects.filter(status="pending").exists()
        ):
            return
        if get("library_root") and not Job.objects.filter(kind="scan", status="queued").exists():
            enqueue("scan")
        elif Job.objects.filter(status="queued").exists():
            ensure_worker()
    except OperationalError:
        pass  # First install may not have migrated yet.


def enqueue(kind, payload=None):
    job = Job.objects.create(kind=kind, payload=payload or {})
    ensure_worker()
    return job


def ensure_worker():
    global _thread
    if not settings.MUSICTAG_WORKER:
        return
    with _guard:
        if _thread is None or not _thread.is_alive():
            if (
                Job.objects.filter(status="running").exists()
                or OperationEntry.objects.filter(status="pending").exists()
            ):
                return  # Explicit crash recovery required; never overlap another worker.
            _thread = threading.Thread(target=worker, daemon=True, name="musictag-worker")
            _thread.start()


def run(job):
    from .library_index import scan, rebuild_albums
    from .writer import WRITE_LOCK, write, finish, undo

    try:
        if job.kind == "scan":
            with WRITE_LOCK:
                job.result = scan(job)
        elif job.kind == "undo":
            operation = undo(job.payload["operation"], job=job)
            job.result = {"operation": operation.pk}
            job.done = operation.track_count
            job.succeeded = operation.entries.filter(status="success").count()
            job.failed = job.total - job.succeeded
        elif job.kind == "bulk":
            plans = job.payload["plans"]
            operation = Operation.objects.create(kind="bulk", summary=f"Batch edit · {len(plans)} tracks")
            job.total = len(plans)
            job.result = {"operation": operation.pk}
            job.save()
            for plan in plans:
                job.refresh_from_db(fields=["cancel_requested"])
                if job.cancel_requested:
                    break
                try:
                    track = Track.objects.get(pk=plan["id"])
                    write(
                        track,
                        plan["patch"],
                        operation=operation,
                        expected=plan["expected"],
                        cover_hash=plan.get("cover_hash"),
                        aggregate=False,
                    )
                    job.succeeded += 1
                except Exception as exc:
                    job.failed += 1
                    track = Track.objects.filter(pk=plan["id"]).first()
                    if not operation.entries.filter(track_id=plan["id"]).exists():
                        OperationEntry.objects.create(
                            operation=operation,
                            track=track,
                            path=track.path if track else str(plan["id"]),
                            status="failed",
                            error=str(exc),
                        )
                job.done += 1
                job.save(update_fields=["done", "succeeded", "failed"])
            with WRITE_LOCK:
                rebuild_albums()
            finish(operation)
        else:
            raise ValueError("Unknown job kind.")
        job.refresh_from_db(fields=["cancel_requested"])
        job.status = "cancelled" if job.cancel_requested else "completed"
    except Exception as exc:
        job.status, job.error = "failed", str(exc)
    job.finished_at = timezone.now()
    job.save()


def worker(once=False):
    idle = 0
    while True:
        close_old_connections()
        job = Job.objects.filter(status="queued").order_by("id").first()
        if job and Job.objects.filter(pk=job.pk, status="queued").update(status="running"):
            run(job)
            idle = 0
        else:
            idle += 1
        if once or idle > 120:
            close_old_connections()
            return
        time.sleep(0.5)
