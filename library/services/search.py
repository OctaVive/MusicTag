from django.db.models import Q
from library.models import Track


def tracks(params):
    queryset = Track.objects.all()
    for term in params.get("q", "").split()[:10]:
        query = Q()
        for column in ["title", "artist", "album_artist", "album", "genre", "catalog_number", "filename"]:
            query |= Q(**{column + "__icontains": term})
        queryset = queryset.filter(query)
    for param, column in {
        "format": "format",
        "artist": "artist",
        "genre": "genre",
        "year": "date__startswith",
        "folder": "folder",
        "album": "album_group_id",
    }.items():
        if params.get(param):
            if param == "album":
                try:
                    if not 0 < int(params[param]) < 2**63:
                        return queryset.none()
                except ValueError:
                    return queryset.none()
            queryset = queryset.filter(**{column: params[param]})
    if params.get("cover") in {"yes", "no"}:
        queryset = queryset.filter(has_cover=params["cover"] == "yes")
    if params.get("issue"):
        queryset = queryset.filter(issue_flags__icontains='"' + params["issue"] + '"')
    sorts = []
    allowed = {
        "title",
        "artist",
        "album",
        "album_artist",
        "date",
        "genre",
        "duration",
        "format",
        "track_no",
        "disc_no",
        "path",
        "indexed_at",
    }
    for sort in params.get("sort", "album_artist,album,disc_no,track_no,path").split(",")[:5]:
        if sort.removeprefix("-") in allowed:
            sorts.append(sort)
    return queryset.order_by(*(sorts or ["path"]), "pk")
