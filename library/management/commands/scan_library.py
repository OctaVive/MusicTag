from django.core.management.base import BaseCommand
from library.services.library_index import scan
from library.services.writer import WRITE_LOCK


class Command(BaseCommand):
    help = "Incrementally index the configured library. Stop the web server before running maintenance."

    def handle(self, **options):
        with WRITE_LOCK:
            self.stdout.write(str(scan()))
