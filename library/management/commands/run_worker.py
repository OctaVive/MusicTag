from django.core.management.base import BaseCommand
from library.services.jobs import worker


class Command(BaseCommand):
    help = "Run the queue worker (do not run alongside the automatic in-process worker)."

    def add_arguments(self, parser):
        parser.add_argument("--once", action="store_true")

    def handle(self, **options):
        worker(once=options["once"])
