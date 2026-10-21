from django.core import signing

from library.models import Track
from .fields import apply_operations, validate_patch
from .formats.registry import adapter, EXTENSIONS
from .settings_service import contained
from .writer import fingerprint
from . import covers


def preview(ids, operations=None, patches=None, cover_hash=None):
    rows, plans = [], []
    for track in Track.objects.filter(pk__in=ids):
        try:
            path = contained(track.path, EXTENSIONS)
            expected = fingerprint(path)
            snapshot = adapter(path).read()
            before = snapshot.tags
            patch = (
                validate_patch(patches[str(track.pk)])[0]
                if patches is not None
                else apply_operations(before, operations or {})
            )
            changes = {
                k: {"before": before.get(k, []), "after": v}
                for k, v in patch.items()
                if before.get(k, []) != v
            }
            before_cover = covers.cache(snapshot.cover)
            effective_cover = cover_hash if cover_hash is not None and cover_hash != before_cover else None
            if changes or effective_cover is not None:
                plans.append(
                    {
                        "id": track.pk,
                        "patch": {key: patch[key] for key in changes},
                        "expected": expected,
                        "cover_hash": effective_cover,
                    }
                )
            rows.append(
                {
                    "track": track,
                    "changes": changes,
                    "cover_changed": effective_cover is not None,
                    "before_cover": before_cover,
                    "after_cover": effective_cover,
                }
            )
        except Exception as exc:
            rows.append({"track": track, "error": str(exc)})
    if not rows:
        raise ValueError("Select at least one track.")
    return rows, signing.dumps({"plans": plans}, salt="bulk-preview", compress=True)


def decode(token):
    return signing.loads(token, salt="bulk-preview", max_age=1800)["plans"]
