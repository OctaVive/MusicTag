import re
from collections import defaultdict
from pathlib import Path

from .fields import validate_patch


def parse_filename(filename, template):
    allowed = {
        "title": "TITLE",
        "artist": "ARTIST",
        "album": "ALBUM",
        "track": "TRACKNUMBER",
        "disc": "DISCNUMBER",
        "year": "DATE",
        "albumartist": "ALBUMARTIST",
    }
    pattern, seen, offset = "", set(), 0
    for match in re.finditer(r"\{(\w+)\}", template):
        token = match.group(1).lower()
        if token not in allowed or token in seen:
            raise ValueError(f"Unknown or repeated token: {token}.")
        seen.add(token)
        pattern += re.escape(template[offset : match.start()]) + f"(?P<{token}>.+?)"
        offset = match.end()
    pattern += re.escape(template[offset:])
    if not seen:
        raise ValueError("Include tokens such as {track}, {artist}, {title}.")
    match = re.fullmatch(pattern, Path(filename).stem.replace("_", " "))
    if not match:
        raise ValueError("Filename does not match the template.")
    patch = {
        allowed[key]: [str(int(value)) if key in {"track", "disc"} and value.isdigit() else value]
        for key, value in match.groupdict().items()
    }
    return validate_patch(patch)[0]


def numbering(tracks, start=1, scope="album", totals=True, renumber_discs=False):
    if not 0 <= start <= 9999 or scope not in {"album", "folder", "disc"}:
        raise ValueError("Invalid numbering start or scope.")
    groups = defaultdict(list)
    for track in tracks:
        key = track.folder if scope == "folder" else track.album_group_id
        if scope == "disc":
            key = (key, track.disc_no)
        groups[key].append(track)
    patches = {}
    for members in groups.values():
        discs = {disc: index + 1 for index, disc in enumerate(sorted({t.disc_no for t in members}))}
        for index, track in enumerate(members, start):
            patch = {"TRACKNUMBER": [str(index)]}
            if totals:
                patch["TRACKTOTAL"] = [str(start + len(members) - 1)]
            if renumber_discs:
                patch["DISCNUMBER"] = [str(discs[track.disc_no])]
                patch["DISCTOTAL"] = [str(len(discs))]
            patches[str(track.pk)] = validate_patch(patch)[0]
    return patches
