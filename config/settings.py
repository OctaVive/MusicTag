import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")
STATE_DIR = Path(os.environ.get("MUSICTAG_STATE", BASE_DIR / ".musictag_state")).resolve()
STATE_DIR.mkdir(parents=True, exist_ok=True)
secret_file = STATE_DIR / "secret.key"
if not secret_file.exists():
    import secrets

    try:
        with secret_file.open("x") as stream:
            stream.write(secrets.token_urlsafe(48))
        secret_file.chmod(0o600)
    except FileExistsError:
        pass
SECRET_KEY = os.environ.get("SECRET_KEY") or secret_file.read_text()
DEBUG = os.environ.get("DEBUG", "false").lower() == "true"
ALLOWED_HOSTS = os.environ.get("ALLOWED_HOSTS", "localhost,127.0.0.1,[::1]").split(",")
INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "django.contrib.sessions",
    "django.contrib.staticfiles",
    "library.apps.LibraryConfig",
]
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]
ROOT_URLCONF = "config.urls"
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": ["django.template.context_processors.request", "library.context.shell"]
        },
    }
]
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": STATE_DIR / "library.sqlite3",
        "OPTIONS": {"timeout": 30},
    }
}
STATIC_URL = "/static/"
STATIC_ROOT = STATE_DIR / "static"
STATIC_ROOT.mkdir(parents=True, exist_ok=True)
WHITENOISE_USE_FINDERS = True  # Source checkout works offline without a build/collectstatic step.
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedStaticFilesStorage"},
}
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
USE_TZ = True
TIME_ZONE = "UTC"
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Strict"
CSRF_COOKIE_SAMESITE = "Strict"
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
DATA_UPLOAD_MAX_MEMORY_SIZE = 12 * 1024 * 1024
DATA_UPLOAD_MAX_NUMBER_FIELDS = 100_000  # Explicit selections can contain a large local library.
FILE_UPLOAD_MAX_MEMORY_SIZE = 2 * 1024 * 1024
MUSICTAG_WORKER = os.environ.get("MUSICTAG_WORKER", "true").lower() == "true"
