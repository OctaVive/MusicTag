"""Explicit online requests only. No automatic metadata writes."""

import json
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

from django.core.cache import cache

from .settings_service import get

_lock = threading.Lock()
_last_request = 0.0


def request_json(url):
    global _last_request
    cached = cache.get(url)
    if cached is not None:
        return cached
    contact = get("musicbrainz_contact", "")
    if not contact:
        raise ValueError("Set a MusicBrainz contact email or URL in Settings before lookup.")
    with _lock:
        time.sleep(max(0, 1.05 - (time.monotonic() - _last_request)))
        _last_request = time.monotonic()
        request = urllib.request.Request(
            url, headers={"User-Agent": f"MusicTag/1.0 ({contact})", "Accept": "application/json"}
        )
        try:
            with urllib.request.urlopen(request, timeout=12) as response:
                data = json.loads(response.read(4 * 1024 * 1024))
        except (OSError, ValueError, urllib.error.HTTPError) as exc:
            raise ValueError(f"Metadata lookup unavailable (offline or rate limited): {exc}") from exc
    cache.set(url, data, 3600)
    return data


def search(query):
    return request_json(
        "https://musicbrainz.org/ws/2/release/?"
        + urllib.parse.urlencode({"query": query[:300], "fmt": "json", "limit": 20})
    ).get("releases", [])


def release(identifier):
    import uuid

    identifier = str(uuid.UUID(identifier))
    return request_json(
        f"https://musicbrainz.org/ws/2/release/{identifier}?inc=recordings+artist-credits+labels+release-groups&fmt=json"
    )


def cover_candidates(identifier):
    import uuid

    return request_json(f"https://coverartarchive.org/release/{uuid.UUID(identifier)}").get("images", [])


def download_cover(identifier, image_id):
    import uuid

    if not str(image_id).isdigit():
        raise ValueError("Invalid Cover Art Archive image ID.")

    class ArchiveRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            parsed = urllib.parse.urlparse(newurl)
            host = parsed.hostname or ""
            if parsed.scheme != "https" or not (
                host == "archive.org" or host.endswith(".archive.org") or host == "coverartarchive.org"
            ):
                raise ValueError("Artwork server returned an unsafe redirect.")
            return super().redirect_request(req, fp, code, msg, headers, newurl)

    url = f"https://coverartarchive.org/release/{uuid.UUID(identifier)}/{image_id}"
    opener = urllib.request.build_opener(ArchiveRedirect())
    request = urllib.request.Request(
        url, headers={"User-Agent": f"MusicTag/1.0 ({get('musicbrainz_contact', '')})"}
    )
    try:
        with opener.open(request, timeout=15) as response:
            data = response.read(10 * 1024 * 1024 + 1)
    except OSError as exc:
        raise ValueError(f"Artwork download unavailable: {exc}") from exc
    from .covers import normalize

    return normalize(data)[0]


def match_release(tracks, data):
    from difflib import SequenceMatcher

    result = {}
    credits = [
        c.get("name", c.get("artist", {}).get("name", ""))
        for c in data.get("artist-credit", [])
        if isinstance(c, dict)
    ]
    candidates = [
        (medium, recording) for medium in data.get("media", []) for recording in medium.get("tracks", [])
    ]
    used = set()
    for track in tracks:

        def score(item):
            medium, candidate = item
            number = int(candidate.get("position", 0)) == track.track_no and int(
                medium.get("position", 1)
            ) == (track.disc_no or 1)
            duration = abs(candidate.get("length", 0) / 1000 - track.duration) < 3
            title = SequenceMatcher(
                None, track.title.casefold(), candidate.get("title", "").casefold()
            ).ratio()
            return number * 10 + duration * 3 + title

        available = [item for item in candidates if item[1].get("id") not in used]
        if not available:
            break
        medium, candidate = max(available, key=score)
        used.add(candidate.get("id"))
        patch = {
            "TITLE": [candidate.get("title", "")],
            "ALBUM": [data.get("title", "")],
            "ALBUMARTIST": credits,
            "DATE": [data.get("date", "")],
            "TRACKNUMBER": [str(candidate.get("position", 0))],
            "TRACKTOTAL": [str(medium.get("track-count", 0))],
            "DISCNUMBER": [str(medium.get("position", 1))],
            "MUSICBRAINZ_ALBUMID": [data["id"]],
            "MUSICBRAINZ_TRACKID": [candidate.get("id", "")],
        }
        labels = data.get("label-info", [])
        if labels:
            patch["LABEL"] = [labels[0].get("label", {}).get("name", "")]
            patch["CATALOGNUMBER"] = [labels[0].get("catalog-number", "")]
        result[str(track.pk)] = patch
    return result
