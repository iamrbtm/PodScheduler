"""Verification for the participant portal (this project has no test suite).

Run inside the web container:
    docker compose exec -T web uv run python scripts/verify_portal.py
    docker compose exec -T web uv run python scripts/verify_portal.py --keep   # leave fixtures, print portal URLs

Creates throwaway rows (guest emails @verify.invalid, episode titles prefixed
"verify-portal") in the real database and deletes them afterwards. Mail is
suppressed and never sent.
"""
import sys
import traceback
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import create_app
from app.extensions import db, mail
from app.models import (
    InvitationStatus, Participant, ParticipantRole, Podcast, PodcastParticipant,
    PodcastStatus, Show, User,
)

app = create_app()
app.config["WTF_CSRF_ENABLED"] = False
# Keep the first request from re-reading the DB's real SMTP settings (that
# reloader calls mail.init_app again and would un-suppress sending).
app._mail_settings_loaded = True
app.extensions["mail"].suppress = True
assert app.extensions["mail"].suppress is True, "refusing to run with mail sending enabled"

TAG = "verify-portal"
RESULTS = []
CHECKS = []
_n = [0]


def register(fn):
    CHECKS.append(fn)
    return fn


def check(name, cond, detail=""):
    RESULTS.append((name, bool(cond)))
    print(("PASS  " if cond else "FAIL  ") + name + ("" if cond or not detail else f"   -> {detail}"))


def admin():
    return User.query.filter_by(username="admin").first()


def make_show():
    _n[0] += 1
    show = Show(
        title=f"{TAG} Show {_n[0]}", feed_slug=f"{TAG}-show-{_n[0]}", author_name="Verify Author",
        owner_email="owner@verify.invalid", created_by_id=admin().id,
        cover_image_url="http://localhost/media/verify-cover.jpg",
    )
    db.session.add(show)
    db.session.commit()
    return show


def make_episode(**kw):
    _n[0] += 1
    data = dict(
        title=f"{TAG} episode {_n[0]}", status=PodcastStatus.SCHEDULED,
        host_id=admin().id, created_by_id=admin().id,
        recording_date=datetime(2026, 10, 1, 14, 30),   # a Thursday
        scheduled_date=datetime(2026, 10, 20, 6, 0), duration_minutes=45,
    )
    data.update(kw)
    ep = Podcast(**data)
    db.session.add(ep)
    db.session.commit()
    return ep


def make_guest(name="Alice"):
    _n[0] += 1
    guest = Participant(name=f"{name} Verify", email=f"{name.lower()}{_n[0]}@verify.invalid",
                        created_by_id=admin().id)
    db.session.add(guest)
    db.session.commit()
    return guest


def add_slot(guest, episode, status="pending", invited=True,
             role=ParticipantRole.ROUNDTABLE, message=None):
    pp = PodcastParticipant(podcast_id=episode.id, participant_id=guest.id,
                            participant_role=role, message=message)
    db.session.add(pp)
    if invited:
        pp.mark_invited()
    if status == "accepted":
        pp.accept()
    elif status == "declined":
        pp.decline()
    db.session.commit()
    return pp


def admin_client():
    c = app.test_client()
    with c.session_transaction() as s:
        s["_user_id"] = str(admin().id)
        s["_fresh"] = True
    return c


def cleanup():
    db.session.rollback()
    for g in Participant.query.filter(Participant.email.like("%@verify.invalid")).all():
        db.session.delete(g)
    for ep in Podcast.query.filter(Podcast.title.like(f"{TAG}%")).all():
        db.session.delete(ep)
    db.session.commit()
    for s in Show.query.filter(Show.feed_slug.like(f"{TAG}%")).all():
        db.session.delete(s)
    db.session.commit()


# ── checks ────────────────────────────────────────────────────────────────────

@register
def check_models():
    from app.models import GuestQuestion
    a, b = make_guest("Alice"), make_guest("Bob")
    check("portal_token generated on insert", a.portal_token and len(a.portal_token) >= 32)
    check("portal tokens are unique", a.portal_token != b.portal_token)
    old = a.portal_token
    a.regenerate_portal_token()
    db.session.commit()
    check("regenerate_portal_token changes the token", a.portal_token != old)
    ep = make_episode(guest_prep_info="Bring a headset.")
    db.session.expire_all()
    check("Podcast.guest_prep_info round-trips", db.session.get(Podcast, ep.id).guest_prep_info == "Bring a headset.")
    pp = add_slot(a, ep)
    q = GuestQuestion(podcast_participant_id=pp.id, question="What mic?")
    db.session.add(q)
    db.session.commit()
    check("guest question links to its slot", pp.questions.count() == 1 and q.email_sent is False)
    nulls = db.session.execute(db.text("SELECT count(*) FROM participants WHERE portal_token IS NULL")).scalar()
    check("no participant lacks a portal_token", nulls == 0)


# ── runner ────────────────────────────────────────────────────────────────────

def main():
    keep = "--keep" in sys.argv
    with app.app_context():
        cleanup()  # leftovers from a crashed run
        try:
            for fn in CHECKS:
                try:
                    fn()
                except Exception:
                    traceback.print_exc()
                    check(fn.__name__ + " raised", False)
                db.session.rollback()
        finally:
            if keep:
                print("\n--keep: fixtures left in place; rerun without --keep to clean up.")
            else:
                cleanup()
    failed = [n for n, ok in RESULTS if not ok]
    print(f"\n{len(RESULTS) - len(failed)}/{len(RESULTS)} passed")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
