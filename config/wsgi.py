import os
from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
application = get_wsgi_application()
from library.services.jobs import bootstrap  # noqa: E402 -- Django must initialize before model imports.

bootstrap()
