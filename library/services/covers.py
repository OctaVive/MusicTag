import hashlib
import io
import warnings

from django.conf import settings
from PIL import Image, ImageOps


def cache(data):
    if not data:
        return ""
    digest = hashlib.sha256(data).hexdigest()
    folder = settings.STATE_DIR / "cache" / "covers" / digest
    folder.mkdir(parents=True, exist_ok=True)
    original = folder / "original"
    if not original.exists():
        original.write_bytes(data)
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(data)) as source:
                source.load()
                for size in [96, 320]:
                    target = folder / f"{size}.jpg"
                    if not target.exists():
                        image = ImageOps.exif_transpose(source).convert("RGB")
                        image.thumbnail((size, size))
                        image.save(target, "JPEG", quality=85)
    except (OSError, ValueError, Image.DecompressionBombError, Image.DecompressionBombWarning):
        pass  # Bad embedded artwork must not prevent reading audio metadata.
    return digest


def original(digest):
    if not digest:
        return None
    if len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
        raise ValueError("Invalid cover hash.")
    return (settings.STATE_DIR / "cache" / "covers" / digest / "original").read_bytes()


def normalize(data):
    from .settings_service import get

    if len(data) > int(get("cover_limit_mb", 10)) * 1024 * 1024:
        raise ValueError("Cover exceeds the configured upload limit.")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(data)) as image:
                if image.format not in {"JPEG", "PNG", "WEBP"}:
                    raise ValueError("Use a JPEG, PNG or WebP image.")
                image.load()
                image = ImageOps.exif_transpose(image).convert("RGB")
                image.thumbnail((3000, 3000))
                stream = io.BytesIO()
                image.save(stream, "JPEG", quality=92)
                return stream.getvalue(), "image/jpeg"
    except (OSError, Image.DecompressionBombError, Image.DecompressionBombWarning) as exc:
        raise ValueError("Invalid or unsafe cover image.") from exc
