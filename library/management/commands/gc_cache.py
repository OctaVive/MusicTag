import shutil
from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db.models import Q
from django.utils import timezone
from library.models import Album, Job, Operation, OperationEntry, Track


class Command(BaseCommand):
    help = "Prune operations older than 30 days except the latest 200; remove unreferenced backups/covers. Stop the server first."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, **options):
        if Job.objects.filter(status__in=["queued", "running"]).exists():
            self.stderr.write("Refusing maintenance while jobs are active.")
            return
        keep = list(Operation.objects.values_list("pk", flat=True)[:200])
        expired = (
            Operation.objects.exclude(pk__in=keep)
            .exclude(status="running")
            .filter(created_at__lt=timezone.now() - timedelta(days=30))
        )
        self.stdout.write(f"{expired.count()} expired operations.")
        if options["dry_run"]:
            return
        expired.delete()
        operation_ids = {str(pk) for pk in Operation.objects.values_list("pk", flat=True)}
        backup_root = settings.STATE_DIR / "backups"
        if backup_root.exists():
            for folder in backup_root.iterdir():
                if (
                    folder.is_dir()
                    and folder.name.isdigit()
                    and folder.name not in operation_ids
                    and not folder.is_symlink()
                ):
                    shutil.rmtree(folder)
        referenced = set(Track.objects.values_list("cover_hash", flat=True)) | set(
            Album.objects.values_list("cover_hash", flat=True)
        )
        for before, after in OperationEntry.objects.filter(
            Q(before_cover__gt="") | Q(after_cover__gt="")
        ).values_list("before_cover", "after_cover"):
            referenced.update([before, after])
        # Preview tokens may still reference uploads for 30 minutes.
        cache_root = settings.STATE_DIR / "cache" / "covers"
        cutoff = (timezone.now() - timedelta(hours=1)).timestamp()
        if cache_root.exists():
            for folder in cache_root.iterdir():
                if (
                    len(folder.name) == 64
                    and folder.name not in referenced
                    and folder.stat().st_mtime < cutoff
                    and not folder.is_symlink()
                ):
                    shutil.rmtree(folder)
