"""Read-only client for a self-hosted Castopod instance's REST API.

Castopod's REST API (api/rest/v1/, off by default) exposes podcasts and
episodes but no analytics endpoints — the only listener metric it returns is
each episode's `downloads_count`. Unique listeners, top countries, etc. live
only in Castopod's own admin UI, behind a session login, so they aren't
pulled here.

Stats are cached on the Podcast row for CACHE_TTL so the episode detail page
doesn't call Castopod on every load.
"""
import base64
import json
from datetime import datetime, timedelta, timezone
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .extensions import db
from .models.castopod_settings import CastopodSettings

API_PREFIX = "/api/rest/v1/"
TIMEOUT_SECONDS = 10
CACHE_TTL = timedelta(hours=1)
MIN_REFRESH_INTERVAL = timedelta(minutes=1)
# Castopod's list endpoint defaults to 10 results; ask for enough to cover a
# whole show so the episode lookup and the show total both see every episode.
EPISODE_LIST_LIMIT = 1000


class CastopodError(Exception):
    pass


def _utcnow():
    # DateTime columns in this app are naive; keep comparisons naive UTC.
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _get(settings, path, params=None):
    url = settings.base_url.rstrip("/") + API_PREFIX + path
    if params:
        url += "?" + urlencode(params)
    req = Request(url, headers={"Accept": "application/json"})
    if settings.api_username:
        creds = f"{settings.api_username}:{settings.api_password or ''}".encode()
        req.add_header("Authorization", "Basic " + base64.b64encode(creds).decode())
    try:
        with urlopen(req, timeout=TIMEOUT_SECONDS) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except HTTPError as exc:
        if exc.code == 401:
            raise CastopodError("Castopod rejected the API username/password.") from exc
        if exc.code == 404:
            raise CastopodError(
                "Castopod returned 404 — check the URL and that restapi.enabled=true is set in Castopod's .env."
            ) from exc
        raise CastopodError(f"Castopod returned HTTP {exc.code}.") from exc
    except (URLError, TimeoutError, OSError) as exc:
        reason = getattr(exc, "reason", exc)
        raise CastopodError(f"Couldn't reach Castopod: {reason}") from exc
    except ValueError as exc:
        raise CastopodError("Castopod returned something that isn't JSON.") from exc


def list_podcasts(settings):
    """[{id, title, handle}] for every podcast on the instance."""
    data = _get(settings, "podcasts")
    return [
        {"id": p.get("id"), "title": p.get("title"), "handle": p.get("handle")}
        for p in data
        if isinstance(p, dict)
    ]


def fetch_episode_stats(settings, castopod_podcast_id, castopod_episode_id):
    """Pull one episode's counts plus its show's total downloads.

    Uses the list endpoint filtered to the show rather than episodes/<id>:
    Castopod caches the single-episode lookup indefinitely, so its
    downloads_count goes stale, while the list query reads the table directly.
    """
    episodes = _get(
        settings,
        "episodes",
        {"podcastIds": castopod_podcast_id, "limit": EPISODE_LIST_LIMIT},
    )
    episodes = [e for e in episodes if isinstance(e, dict)]
    match = next((e for e in episodes if e.get("id") == castopod_episode_id), None)
    if match is None:
        raise CastopodError(
            f"Episode {castopod_episode_id} wasn't found in Castopod podcast {castopod_podcast_id}."
        )
    return {
        "downloads": int(match.get("downloads_count") or 0),
        "comments": int(match.get("comments_count") or 0),
        "show_downloads": sum(int(e.get("downloads_count") or 0) for e in episodes),
        "castopod_title": match.get("title"),
        "podcast_id": castopod_podcast_id,
        "episode_id": castopod_episode_id,
    }


def get_stats(podcast, force=False):
    """Stats payload for the episode detail page (JSON-serialisable dict).

    `state` is one of: not_configured, not_linked, ok, error. On error, any
    previously cached stats are still returned alongside the message.
    """
    settings = CastopodSettings.get()
    if settings is None or not settings.is_configured:
        return {"state": "not_configured"}

    show = podcast.show
    if not podcast.castopod_episode_id or show is None or not show.castopod_podcast_id:
        return {
            "state": "not_linked",
            "missing_show_id": show is None or not show.castopod_podcast_id,
            "missing_episode_id": not podcast.castopod_episode_id,
        }

    cached = podcast.castopod_stats_json
    if cached and (
        cached.get("podcast_id") != show.castopod_podcast_id
        or cached.get("episode_id") != podcast.castopod_episode_id
    ):
        # Linked to a different Castopod episode since the last sync
        podcast.castopod_stats_json = None
        podcast.castopod_synced_at = None
        cached = None

    now = _utcnow()
    age = now - podcast.castopod_synced_at if podcast.castopod_synced_at else None
    fresh = age is not None and age < CACHE_TTL
    too_soon = age is not None and age < MIN_REFRESH_INTERVAL
    if cached and (too_soon or (fresh and not force)):
        return _payload("ok", podcast)

    try:
        stats = fetch_episode_stats(settings, show.castopod_podcast_id, podcast.castopod_episode_id)
    except CastopodError as exc:
        return _payload("error", podcast, error=str(exc))

    podcast.castopod_stats_json = stats
    podcast.castopod_synced_at = now
    db.session.commit()
    return _payload("ok", podcast)


def _payload(state, podcast, error=None):
    synced = podcast.castopod_synced_at
    return {
        "state": state,
        "error": error,
        "stats": podcast.castopod_stats_json,
        "synced_at": synced.replace(tzinfo=timezone.utc).isoformat() if synced else None,
    }
