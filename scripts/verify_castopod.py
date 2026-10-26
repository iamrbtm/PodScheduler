"""Verification for the Castopod stats integration (this project has no test suite).

Run inside the web container:
    docker compose exec -T web uv run python scripts/verify_castopod.py

Starts a fake Castopod REST API on 127.0.0.1, points CastopodSettings at it,
and exercises the admin settings page, the episode/show ID fields and the
stats JSON route. Creates throwaway rows (episode titles and show slugs
prefixed "verify-castopod") and deletes them afterwards. Any real Castopod
settings already saved are restored when the run finishes.
"""
import base64
import json
import sys
import threading
import traceback
from datetime import timedelta
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import create_app
from app.extensions import db
from app.models import CastopodSettings, Podcast, PodcastStatus, Show, User

app = create_app()
app.config["WTF_CSRF_ENABLED"] = False

TAG = "verify-castopod"
RESULTS = []

# ── fake Castopod ─────────────────────────────────────────────────────────────

API_USER, API_PASSWORD = "verify-api", "verify-secret"
FAKE = {"downloads": 42, "calls": []}


class FakeCastopod(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_GET(self):
        url = urlparse(self.path)
        query = parse_qs(url.query)
        FAKE["calls"].append((url.path, query))
        expected = "Basic " + base64.b64encode(f"{API_USER}:{API_PASSWORD}".encode()).decode()
        if self.headers.get("Authorization") != expected:
            self.send_response(401)
            self.end_headers()
            return
        if url.path == "/api/rest/v1/podcasts":
            body = [{"id": 3, "title": "Verify Castopod Show", "handle": "verify"}]
        elif url.path == "/api/rest/v1/episodes" and query.get("podcastIds") == ["3"]:
            body = [
                {"id": 7, "title": "Ep 7", "downloads_count": FAKE["downloads"], "comments_count": 2},
                {"id": 8, "title": "Ep 8", "downloads_count": 100, "comments_count": 0},
            ]
        else:
            self.send_response(404)
            self.end_headers()
            return
        data = json.dumps(body).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(data)


server = HTTPServer(("127.0.0.1", 0), FakeCastopod)
threading.Thread(target=server.serve_forever, daemon=True).start()
FAKE_URL = f"http://127.0.0.1:{server.server_port}"

# ── helpers ───────────────────────────────────────────────────────────────────


def check(name, cond, detail=""):
    RESULTS.append((name, bool(cond)))
    print(("PASS  " if cond else "FAIL  ") + name + ("" if cond or not detail else f"   -> {detail}"))


def admin():
    return User.query.filter_by(username="admin").first()


def admin_client():
    c = app.test_client()
    with c.session_transaction() as s:
        s["_user_id"] = str(admin().id)
        s["_fresh"] = True
    return c


def cleanup():
    db.session.rollback()
    for ep in Podcast.query.filter(Podcast.title.like(f"{TAG}%")).all():
        db.session.delete(ep)
    db.session.commit()
    for s in Show.query.filter(Show.feed_slug.like(f"{TAG}%")).all():
        db.session.delete(s)
    db.session.commit()


def snapshot_settings():
    s = CastopodSettings.get()
    if s is None:
        return None
    return {c: getattr(s, c) for c in ("base_url", "api_username", "api_password", "sync_enabled",
                                        "updated_at", "updated_by_id")}


def restore_settings(saved):
    db.session.rollback()
    current = CastopodSettings.get()
    if saved is None:
        if current is not None:
            db.session.delete(current)
    else:
        for k, v in saved.items():
            setattr(current, k, v)
    db.session.commit()


def age_sync(ep_id, by):
    ep = db.session.get(Podcast, ep_id)
    ep.castopod_synced_at -= by
    db.session.commit()


# ── checks ────────────────────────────────────────────────────────────────────


def run_checks():
    c = admin_client()
    if CastopodSettings.get():
        db.session.delete(CastopodSettings.get())
        db.session.commit()

    show = Show(title=f"{TAG} Show", feed_slug=f"{TAG}-show", author_name="Verify",
                owner_email="owner@verify.invalid", created_by_id=admin().id)
    db.session.add(show)
    db.session.flush()
    ep = Podcast(title=f"{TAG} episode", status=PodcastStatus.DRAFT, host_id=admin().id,
                 created_by_id=admin().id, show_id=show.id)
    db.session.add(ep)
    db.session.commit()
    ep_id, show_id = ep.id, show.id
    stats_url = f"/podcasts/{ep_id}/castopod-stats.json"

    def stats(refresh=False):
        r = c.get(stats_url + ("?refresh=1" if refresh else ""))
        return r.get_json() if r.status_code == 200 else {"http": r.status_code}

    check("stats route reports not_configured with no settings", stats().get("state") == "not_configured")
    page = c.get(f"/podcasts/{ep_id}").get_data(as_text=True)
    check("detail page hides tiles when sync is off", 'id="castopodStats"' not in page)

    check("settings page renders", c.get("/admin/settings/castopod").status_code == 200)
    check("admin dashboard links to Castopod", "/admin/settings/castopod" in c.get("/admin/").get_data(as_text=True))

    form = {"base_url": FAKE_URL + "/", "api_username": API_USER, "api_password": "wrong", "sync_enabled": "on"}
    c.post("/admin/settings/castopod", data=form)
    html = c.post("/admin/settings/castopod/test").get_data(as_text=True)
    check("connection test reports bad credentials", "rejected the API username" in html)

    c.post("/admin/settings/castopod", data={**form, "api_password": API_PASSWORD})
    c.post("/admin/settings/castopod", data={**form, "api_password": ""})
    s = CastopodSettings.get()
    check("blank password keeps the saved one", s.api_password == API_PASSWORD)
    check("trailing slash stripped from URL", s.base_url == FAKE_URL)
    html = c.post("/admin/settings/castopod/test").get_data(as_text=True)
    check("connection test lists podcasts with IDs", "Verify Castopod Show" in html and "ID 3" in html)

    st = stats()
    check("stats route reports both IDs missing",
          st.get("state") == "not_linked" and st.get("missing_episode_id") and st.get("missing_show_id"), st)
    page = c.get(f"/podcasts/{ep_id}").get_data(as_text=True)
    check("detail page shows tiles when sync is on", 'id="castopodStats"' in page)

    check("show form has Castopod Podcast ID field",
          'name="castopod_podcast_id"' in c.get(f"/admin/shows/{show_id}/edit").get_data(as_text=True))
    check("episode form has Castopod Episode ID field",
          'name="castopod_episode_id"' in c.get(f"/podcasts/{ep_id}/edit").get_data(as_text=True))
    db.session.get(Show, show_id).castopod_podcast_id = 3
    db.session.commit()
    r = c.post(f"/podcasts/{ep_id}/edit", data={
        "title": f"{TAG} episode", "host_id": admin().id, "show_id": show_id,
        "status": "draft", "duration_minutes": 60, "castopod_episode_id": 7,
    })
    db.session.expire_all()
    check("episode edit form saves Castopod Episode ID",
          r.status_code == 302 and db.session.get(Podcast, ep_id).castopod_episode_id == 7, r.status_code)

    n = len(FAKE["calls"])
    st = stats()
    ok = st.get("state") == "ok" and st["stats"] == {**st["stats"], "downloads": 42, "show_downloads": 142, "comments": 2}
    check("stats fetched from the show's episode list", ok, st)
    check("list call asks for a whole show", FAKE["calls"][-1][1].get("limit") == ["1000"])

    FAKE["downloads"] = 50
    check("second load served from cache", stats()["stats"]["downloads"] == 42 and len(FAKE["calls"]) == n + 1)
    check("refresh throttled within a minute", stats(refresh=True)["stats"]["downloads"] == 42)
    age_sync(ep_id, timedelta(minutes=5))
    check("refresh refetches after a minute", stats(refresh=True)["stats"]["downloads"] == 50)
    FAKE["downloads"] = 60
    age_sync(ep_id, timedelta(hours=2))
    check("stale cache refetched after an hour", stats()["stats"]["downloads"] == 60)

    db.session.get(Podcast, ep_id).castopod_episode_id = 99
    db.session.commit()
    st = stats()
    check("relinking to a missing episode errors and drops old stats",
          st.get("state") == "error" and "wasn't found" in (st.get("error") or "") and st.get("stats") is None, st)

    db.session.get(Podcast, ep_id).castopod_episode_id = 7
    db.session.commit()
    stats()
    age_sync(ep_id, timedelta(hours=2))
    server.shutdown()
    server.server_close()
    st = stats()
    check("Castopod offline returns error plus cached stats",
          st.get("state") == "error" and "Couldn't reach" in (st.get("error") or "")
          and (st.get("stats") or {}).get("downloads") == 60, st)


def main():
    with app.app_context():
        cleanup()  # leftovers from a crashed run
        saved = snapshot_settings()
        try:
            run_checks()
        except Exception:
            traceback.print_exc()
            check("run_checks raised", False)
        finally:
            cleanup()
            restore_settings(saved)
    failed = [n for n, ok in RESULTS if not ok]
    print(f"\n{len(RESULTS) - len(failed)}/{len(RESULTS)} passed")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
