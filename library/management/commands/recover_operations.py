import shutil
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from library.models import Job, OperationEntry
from library.services.settings_service import contained
from library.services.formats.registry import EXTENSIONS
from library.services.writer import fingerprint, finish


class Command(BaseCommand):
    help = "After a crash, inspect pending writes; --restore restores backups. STOP the web server first."

    def add_arguments(self, parser):
        parser.add_argument("--restore", action="store_true")

    def handle(self, **options):
        for entry in OperationEntry.objects.filter(status="pending"):
            self.stdout.write(f"Pending #{entry.pk}: {entry.path} backup={entry.backup}")
            if options["restore"]:
                path = contained(entry.path, EXTENSIONS)
                backup = (settings.STATE_DIR / entry.backup).resolve()
                if fingerprint(path) != entry.before_fingerprint:
                    if (
                        not entry.backup
                        or not backup.is_file()
                        or not backup.is_relative_to((settings.STATE_DIR / "backups").resolve())
                        or not entry.before_fingerprint
                        or fingerprint(backup) != entry.before_fingerprint
                    ):
                        raise CommandError(
                            f"Missing or invalid backup for entry #{entry.pk}; inspect manually before continuing."
                        )
                    shutil.copy2(backup, path)
                entry.status, entry.error = (
                    "failed",
                    "Interrupted write restored after a crash; rescan required.",
                )
                entry.save()
                finish(entry.operation)
        if options["restore"]:
            Job.objects.filter(status="running").update(
                status="failed",
                error="Interrupted process. Review history, rescan, and generate a new preview.",
                finished_at=timezone.now(),
            )
            self.stdout.write("Run scan_library before restarting the web server.")
