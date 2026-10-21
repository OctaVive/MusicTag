import pytest
from django.test import Client

from library.models import Track
from library.services.writer import fingerprint


@pytest.mark.django_db
def test_onboarding_health(client):
    assert client.get("/").status_code == 302
    assert client.get("/onboarding").status_code == 200
    assert client.get("/api/health").json()["status"] == "ok"


@pytest.mark.django_db
@pytest.mark.parametrize(
    "url",
    [
        "/",
        "/tracks",
        "/folders",
        "/quality",
        "/history",
        "/settings",
        "/tools/parser",
        "/tools/numbering",
        "/tools/presets",
        "/tools/lookup",
    ],
)
def test_pages_and_fragments(indexed, client, url):
    response = client.get(url)
    assert response.status_code == 200
    assert b"<!doctype html>" in response.content
    fragment = client.get(url, HTTP_HX_REQUEST="true")
    assert fragment.status_code == 200
    assert b"<!doctype html>" not in fragment.content


@pytest.mark.django_db
def test_inspector_save_guard_validation_and_csrf(indexed, client, unlocked):
    track = Track.objects.get(format="wav")
    assert client.get(f"/ui/inspector/track/{track.pk}").status_code == 200
    payload = {"field_TITLE": "Edited", "dirty_TITLE": "1", "expected": fingerprint(indexed / track.path)}
    session = client.session
    session["unlocked"] = False
    session.save()
    assert client.post(f"/actions/tracks/{track.pk}/save", payload).status_code == 403
    session["unlocked"] = True
    session.save()
    assert client.post(f"/actions/tracks/{track.pk}/save", payload, HTTP_HX_REQUEST="true").status_code == 200
    track.refresh_from_db()
    assert track.title == "Edited"
    assert (
        client.post(
            f"/actions/tracks/{track.pk}/save",
            {"field_DATE": "bad", "dirty_DATE": "1", "expected": fingerprint(indexed / track.path)},
        ).status_code
        == 422
    )
    csrf = Client(enforce_csrf_checks=True)
    assert csrf.post("/actions/lock", {"unlock": "1"}).status_code == 403
    assert client.get(f"/actions/tracks/{track.pk}/save").status_code == 405


@pytest.mark.django_db
def test_range_audio(indexed, client):
    track = Track.objects.get(format="wav")
    path = indexed / track.path
    url = f"/api/audio/{track.pk}"
    response = client.get(url, HTTP_RANGE="bytes=10-29")
    assert response.status_code == 206
    assert response["Content-Length"] == "20"
    assert b"".join(response.streaming_content) == path.read_bytes()[10:30]
    suffix = client.get(url, HTTP_RANGE="bytes=-10")
    assert b"".join(suffix.streaming_content) == path.read_bytes()[-10:]
    assert client.get(url, HTTP_RANGE="bytes=999999999-").status_code == 416
    assert client.get(url, HTTP_RANGE="bytes=0-1,4-5").status_code == 416


@pytest.mark.django_db
def test_bulk_preview_tamper_and_queue(indexed, unlocked):
    selection = list(Track.objects.values_list("pk", flat=True))
    response = unlocked.post(
        "/actions/bulk/preview",
        {"ids": selection, "include_ALBUM": "1", "field_ALBUM": "New"},
        HTTP_HX_REQUEST="true",
    )
    assert response.status_code == 200
    assert b"Review your changes" in response.content
    assert unlocked.post("/actions/bulk/apply", {"token": "tampered"}).status_code == 422
    assert len(unlocked.get("/api/player/queue").json()["tracks"]) == 3
    assert len(unlocked.get("/api/selection").json()["ids"]) == 3


@pytest.mark.django_db
@pytest.mark.parametrize(
    "url",
    [
        "/tracks?sort=--title",
        "/?sort=--title",
        "/api/player/queue?album=not-a-number",
        "/api/player/queue?album=999999999999999999999999999",
        "/api/player/queue?ids=²",
    ],
)
def test_malformed_query_is_not_server_error(indexed, client, url):
    assert client.get(url).status_code == 200
