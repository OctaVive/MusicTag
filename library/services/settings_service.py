from pathlib import Path

from django.conf import settings

from library.models import AppSetting


def get(key, default=None):
    item = AppSetting.objects.filter(pk=key).first()
    return item.value if item else default


def set_value(key, value):
    AppSetting.objects.update_or_create(key=key, defaults={"value": value})


def root():
    value = get("library_root")
    if not value:
        raise ValueError("Choose a library folder in Settings first.")
    return Path(value).resolve(strict=True)


def configure_root(value):
    candidate = Path(value).expanduser().resolve(strict=True)
    state = settings.STATE_DIR.resolve()
    if not candidate.is_dir():
        raise ValueError("The library root must be a directory.")
    if state == candidate or state.is_relative_to(candidate) or candidate.is_relative_to(state):
        raise ValueError("Library and application state directories must not overlap.")
    current = get("library_root")
    if current and Path(current).resolve() != candidate:
        from library.models import Job, Operation, Track

        if Job.objects.filter(status__in=["queued", "running"]).exists():
            raise ValueError("Wait for active jobs before changing the library root.")
        if Track.objects.exists() or Operation.objects.exists():
            raise ValueError(
                "Use a separate MUSICTAG_STATE directory for a different library (history is root-specific)."
            )
    set_value("library_root", str(candidate))


def contained(relative, extensions=None):
    base = root()
    relative = Path(relative)
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError("Only relative paths inside the library are allowed.")
    target = (base / relative).resolve(strict=True)
    if not target.is_relative_to(base) or not target.is_file():
        raise ValueError("File is outside the library or is not a regular file.")
    if extensions and target.suffix.lower() not in extensions:
        raise ValueError("Unsupported file format.")
    return target
