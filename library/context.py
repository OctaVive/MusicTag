from library.models import Job, Track
from library.services.settings_service import get


def shell(request):
    return {
        "base_template": "library/fragment.html"
        if request.headers.get("HX-Request")
        else "library/base.html",
        "unlocked": request.session.get("unlocked", False),
        "library_root": get("library_root", ""),
        "track_count": Track.objects.count(),
        "active_jobs": Job.objects.filter(status__in=["queued", "running"]).order_by("id"),
        "current_view": request.path,
    }
