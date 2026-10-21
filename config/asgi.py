import os
from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
application = get_asgi_application()
from library.services.jobs import bootstrap  # noqa: E402 -- Django must initialize before model imports.

bootstrap()
