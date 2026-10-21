from django.core.management.base import BaseCommand
from library.models import Track
from library.services import covers


class Command(BaseCommand):
    help = "Rebuild missing cached renditions from cached original artwork."

    def handle(self, **options):
        count = 0
        for digest in Track.objects.exclude(cover_hash="").values_list("cover_hash", flat=True).distinct():
            try:
                covers.cache(covers.original(digest))
                count += 1
            except OSError as exc:
                self.stderr.write(str(exc))
        self.stdout.write(f"Rebuilt artwork for {count} covers.")
