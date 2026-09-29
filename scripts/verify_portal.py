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


@register
def check_guest_prep_form():
    show = make_show()
    ep = make_episode(show_id=show.id, notes="internal only")
    c = admin_client()
    page = c.get(f"/podcasts/{ep.id}/edit").get_data(as_text=True)
    check("episode form has the guest prep field", 'name="guest_prep_info"' in page)
    r = c.post(f"/podcasts/{ep.id}/edit", data={
        "title": ep.title, "host_id": ep.host_id, "status": "scheduled", "show_id": show.id,
        "duration_minutes": 45, "notes": "internal only",
        "guest_prep_info": "Arrive 15 minutes early.",
    })
    check("saving the form redirects", r.status_code == 302, str(r.status_code))
    db.session.expire_all()
    check("guest_prep_info saved", db.session.get(Podcast, ep.id).guest_prep_info == "Arrive 15 minutes early.")
    detail = c.get(f"/podcasts/{ep.id}").get_data(as_text=True)
    check("producer detail page shows guest prep info", "Arrive 15 minutes early." in detail)


@register
def check_portal_pages():
    alice, bob, carol, dave, erin = (make_guest(n) for n in ("Alice", "Bob", "Carol", "Dave", "Erin"))
    show = make_show()
    ep1 = make_episode(show_id=show.id, title=f"{TAG} Alpha", notes="SECRET-PRODUCTION-NOTES",
                       guest_prep_info="Bring a headset.", description="Desc Alpha", topic="Topic Alpha")
    ep2 = make_episode(title=f"{TAG} Beta", guest_prep_info="PREP-FOR-BETA", description="DESC-BETA-HIDDEN")
    ep3 = make_episode(title=f"{TAG} Gamma-not-invited")
    ep4 = make_episode(title=f"{TAG} Delta", status=PodcastStatus.CANCELLED)
    a1 = add_slot(alice, ep1, "accepted", role=ParticipantRole.KEYNOTE_SPEAKER, message="Glad to have you!")
    a2 = add_slot(alice, ep2, "pending")
    a3 = add_slot(alice, ep3, "pending", invited=False)
    a4 = add_slot(alice, ep4, "accepted")
    b1 = add_slot(bob, ep1, "accepted")
    c1 = add_slot(carol, ep1, "pending")
    d1 = add_slot(dave, ep1, "declined")
    b2 = add_slot(bob, ep2, "pending")
    c = app.test_client()

    r = c.get(f"/p/{alice.portal_token}")
    body = r.get_data(as_text=True)
    check("dashboard loads", r.status_code == 200, str(r.status_code))
    check("dashboard lists invited episodes", all(t in body for t in ("Alpha", "Beta", "Delta")))
    check("dashboard hides never-invited slot", "Gamma-not-invited" not in body)
    check("unknown token is 404", c.get("/p/not-a-real-token").status_code == 404)
    check("never-invited slot URL is 404", c.get(f"/p/{alice.portal_token}/episodes/{a3.id}").status_code == 404)
    check("guest with no episodes gets 200 empty state",
          "No invitations yet" in c.get(f"/p/{erin.portal_token}").get_data(as_text=True))
    check("portal has no app shell (anonymous)", '<nav class="app-nav"' not in body)
    check("portal has no app shell (logged-in producer)",
          '<nav class="app-nav"' not in admin_client().get(f"/p/{alice.portal_token}").get_data(as_text=True))

    acc = c.get(f"/p/{alice.portal_token}/episodes/{a1.id}").get_data(as_text=True)
    check("accepted detail: prep info", "Bring a headset." in acc)
    check("accepted detail: host message", "Glad to have you!" in acc)
    check("accepted detail: recording date/time", "Thu, Oct 1, 2026" in acc and "2:30 PM" in acc)
    check("accepted detail: release date/time", "Tue, Oct 20, 2026" in acc and "6:00 AM" in acc)
    check("accepted detail: show name", show.title in acc)
    check("accepted detail: confirmed co-guest listed", "Bob Verify" in acc)
    check("accepted detail: pending/declined co-guests hidden", "Carol Verify" not in acc and "Dave Verify" not in acc)
    check("accepted detail: never shows production notes", "SECRET-PRODUCTION-NOTES" not in acc)
    check("accepted detail: never shows co-guest email", "@verify.invalid" not in acc)

    pend = c.get(f"/p/{alice.portal_token}/episodes/{a2.id}").get_data(as_text=True)
    check("pending detail offers accept and decline", 'value="accept"' in pend and 'value="decline"' in pend)
    check("pending detail hides accepted-only info",
          "PREP-FOR-BETA" not in pend and "DESC-BETA-HIDDEN" not in pend and "Bob Verify" not in pend)

    canc = c.get(f"/p/{alice.portal_token}/episodes/{a4.id}").get_data(as_text=True)
    check("cancelled detail shows badge and no actions", "Cancelled" in canc and 'name="action"' not in canc)

    check("guest A token + guest B slot -> 404", c.get(f"/p/{alice.portal_token}/episodes/{b1.id}").status_code == 404)
    check("guest B token + guest A slot -> 404", c.get(f"/p/{bob.portal_token}/episodes/{a1.id}").status_code == 404)
    check("respond on another guest's slot -> 404",
          c.post(f"/p/{bob.portal_token}/episodes/{a2.id}/respond", data={"action": "accept"}).status_code == 404)

    r = c.post(f"/p/{alice.portal_token}/episodes/{a2.id}/respond", data={"action": "accept"})
    db.session.expire_all()
    check("accept records ACCEPTED and redirects", r.status_code == 302 and a2.invitation_status == InvitationStatus.ACCEPTED)
    c.post(f"/p/{alice.portal_token}/episodes/{a2.id}/respond", data={"action": "decline"})
    db.session.expire_all()
    check("guest can change answer to DECLINED", a2.invitation_status == InvitationStatus.DECLINED)
    c.post(f"/p/{alice.portal_token}/episodes/{a2.id}/respond", data={"action": "bogus"})
    db.session.expire_all()
    check("invalid action changes nothing", a2.invitation_status == InvitationStatus.DECLINED)
    c.post(f"/p/{alice.portal_token}/episodes/{a4.id}/respond", data={"action": "decline"})
    db.session.expire_all()
    check("cancelled episode refuses responses", a4.invitation_status == InvitationStatus.ACCEPTED)


@register
def check_invitation_redirect():
    alice = make_guest("Alice")
    ep = make_episode()
    ep_cancelled = make_episode(status=PodcastStatus.CANCELLED)
    pp = add_slot(alice, ep, "pending")
    pc = add_slot(alice, ep_cancelled, "pending")
    c = app.test_client()

    r = c.get(f"/invitations/{pp.invitation_token}/accept")
    dest = f"/p/{alice.portal_token}/episodes/{pp.id}"
    check("email accept link redirects into the portal", r.status_code == 302 and r.headers["Location"].endswith(dest), r.headers.get("Location", ""))
    db.session.expire_all()
    check("email accept link records ACCEPTED", pp.invitation_status == InvitationStatus.ACCEPTED)

    r = c.get(f"/invitations/{pp.invitation_token}/decline")
    db.session.expire_all()
    check("second email link can't silently flip a recorded answer",
          pp.invitation_status == InvitationStatus.ACCEPTED and r.status_code == 302 and r.headers["Location"].endswith(dest))

    r = c.get(f"/invitations/{pp.invitation_token}/bogus")
    check("invalid action still redirects to main.index", r.status_code == 302 and r.headers["Location"].endswith("/"), r.headers.get("Location", ""))
    check("unknown invitation token is 404", c.get("/invitations/nope/accept").status_code == 404)

    c.get(f"/invitations/{pc.invitation_token}/accept")
    db.session.expire_all()
    check("cancelled episode: email link records nothing", pc.invitation_status == InvitationStatus.PENDING)


@register
def check_portal_link_management():
    from app.email import _build_context, send_invitation_email
    from app.models import MERGE_FIELDS
    alice = make_guest("Alice")
    ep = make_episode()
    pp = add_slot(alice, ep, "pending")

    check("portal_url is a merge field", "portal_url" in MERGE_FIELDS)
    with app.test_request_context(base_url="http://localhost"):
        check("email context carries the portal url",
              _build_context(pp)["portal_url"] == f"http://localhost/p/{alice.portal_token}")
        pp.email_template_id = None
        with mail.record_messages() as out:
            sent = send_invitation_email(pp)
        check("fallback invitation email sends", sent and len(out) == 1)
        link = f"/p/{alice.portal_token}"
        check("fallback email (html + text) links to the portal", link in out[0].html and link in out[0].body)

    c = admin_client()
    check("edit page shows the portal link", f"/p/{alice.portal_token}" in c.get(f"/participants/{alice.id}/edit").get_data(as_text=True))
    old = alice.portal_token
    r = c.post(f"/participants/{alice.id}/regenerate-portal-link")
    db.session.expire_all()
    check("regenerate redirects and changes the token", r.status_code == 302 and alice.portal_token != old)
    anon = app.test_client()
    check("old portal URL now 404s", anon.get(f"/p/{old}").status_code == 404)
    check("new portal URL works", anon.get(f"/p/{alice.portal_token}").status_code == 200)


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
