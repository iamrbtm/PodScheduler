# Participant Portal Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the static accept/decline confirmation pages with a per-guest dashboard (episode list + episode detail, accept/decline/change answer, print, emailed PDF, questions to the host).

**Architecture:** A new public `portal` blueprint at `/p/<token>` keyed by a per-person `Participant.portal_token`. Pages are server-rendered Jinja extending the existing `base.html` in its unauthenticated mode (with a `standalone` flag so a logged-in producer also sees the bare guest layout). The invitation-email links keep recording the response on open, then redirect into the portal. PDF is generated with `reportlab`; questions are saved in a new `guest_questions` table and emailed to the host.

**Tech Stack:** Flask 3.0, Flask-SQLAlchemy, Flask-Migrate/Alembic (Postgres 16), Flask-Mail, Jinja2, Bootstrap 5 (CDN), `reportlab` (new).

**Spec:** `docs/superpowers/specs/2026-09-29-participant-portal-design.md`

## Global Constraints

- Everything is server-rendered. **No new JSON endpoints, no WebSockets** (CLAUDE.md).
- Mobile-first, 375px viewport is the primary target: 48px minimum tap targets, `font-size: 16px` on inputs, no `<table>`s, `.row-card` for lists.
- Every POST is CSRF-protected (Flask-WTF `CSRFProtect` is already on; forms include `<input type="hidden" name="csrf_token" value="{{ csrf_token() }}">`).
- `portal_token` is `secrets.token_urlsafe(32)`, unique, indexed. Possession of the link is the only authorization; unknown token → 404.
- Every portal query is scoped to the `Participant` owning the token; a `pp_id` belonging to someone else → 404.
- `Podcast.notes` (internal production notes) is **never** rendered to guests, emailed to guests, or put in the PDF.
- The emailed PDF is sent **only to the participant's own email address**, never a caller-supplied address.
- Old invitation URLs (`/invitations/<token>/accept|decline`) keep working. An invalid `action` behaves as today: flash "Invalid action." and redirect to `main.index`.
- Recording/release datetimes are naive wall-clock values, displayed verbatim with no timezone conversion (existing behavior).
- Guest-visible episode times: show recording date+time and release date+time; "TBD" when unset.
- Migrations: write by hand; Alembic autogenerate on this DB emits unrelated drift (see CLAUDE.md "Known sharp edges"). Current head revision is `e6f7a8b9c0d1`.
- Commit messages: short imperative summary, then `-m "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"`. Never stage `.env` or the pre-existing untracked files under `docs/` other than files this plan creates.
- Project has **no test suite** and CLAUDE.md lists tests under "don't add without asking". Verification is the single script `scripts/verify_portal.py` (Task 1), built up check-by-check. "Failing test first" in this plan means: add the check, run it, see it fail.

## Review Focus

1. **Added-but-never-invited slot** — a producer adds a guest to an episode (row exists, `invited_at` is NULL) but hasn't sent the invite: it must not appear in that guest's dashboard, and its direct URL must 404. (Task 3)
2. **Cross-guest access** — guest A's token combined with guest B's `pp_id` (either direction) must 404 for view, respond, question and PDF. (Tasks 3, 6, 7)
3. **Pending/declined guests don't see accepted-only info** — description, guest prep info, host message, release date and *other guests' names* appear only for accepted guests; and other guests listed are only *accepted* ones (never pending/declined). (Task 3)
4. **Cancelled episodes** — listed with a Cancelled badge, but accept/decline/question/PDF all refuse and change nothing. (Tasks 3, 4, 6, 7)
5. **Hostile/odd input** — a guest with zero invited episodes gets a 200 empty state, not a 500; empty and 2,001-char questions are rejected; a question/prep text full of `<`, `&`, `</b>` doesn't crash PDF generation or get rendered unescaped. (Tasks 3, 6, 7)

---

## File Structure

| File | Responsibility |
|------|----------------|
| `scripts/verify_portal.py` (create) | Fixture builders + `@register`ed checks; the project's verification harness for this feature |
| `app/models/participant.py` (modify) | `portal_token` column, `ensure_portal_token()`, `regenerate_portal_token()` |
| `app/models/podcast.py` (modify) | `guest_prep_info` column |
| `app/models/guest_question.py` (create) | `GuestQuestion` model |
| `app/models/podcast_participant.py` (modify) | `other_confirmed_guests()` |
| `app/models/__init__.py` (modify) | export `GuestQuestion` |
| `migrations/versions/f7a8b9c0d1e2_add_participant_portal.py` (create) | columns, backfill, table |
| `app/forms/podcast.py`, `app/routes/podcasts.py`, `app/templates/podcasts/form.html`, `app/templates/podcasts/detail.html` (modify) | producer-facing "Guest preparation info" field |
| `app/routes/portal.py` (create) | dashboard, episode, respond, question, email-pdf routes |
| `app/templates/portal/base.html`, `page.html`, `_detail.html`, `_macros.html` (create) | guest UI |
| `app/templates/base.html` (modify) | honor a `standalone` flag so the guest layout never gets the app shell |
| `app/__init__.py` (modify) | register `portal_bp` at `/p` |
| `app/routes/invitations.py` (modify), 3 templates under `app/templates/invitations/` (delete) | redirect into portal |
| `app/email.py` (modify) | `portal_url` context, `reply_to`/attachments in `_send`, `send_guest_question_email`, `send_episode_pdf_email` |
| `app/models/email_template.py`, `app/routes/email_templates.py`, `app/templates/email/invitation.{html,txt}` (modify) | `portal_url` merge field + fallback link |
| `app/routes/participants.py`, `app/templates/participants/form.html` (modify) | show/copy/regenerate portal link |
| `app/pdf.py` (create) | `build_episode_pdf(pp) -> bytes` |
| `pyproject.toml`, `uv.lock` (modify) | `reportlab` |
| `CLAUDE.md` (modify) | document the portal |

**Run commands** (all from `/mnt/storage/docker/PodScheduler`, stack already up):
- Verify: `docker compose exec -T web uv run python scripts/verify_portal.py`
- Migrate: `docker compose exec -T web uv run flask db upgrade`

---

### Task 1: Data model, migration, verification harness

**Files:**
- Create: `scripts/verify_portal.py`, `app/models/guest_question.py`, `migrations/versions/f7a8b9c0d1e2_add_participant_portal.py`
- Modify: `app/models/participant.py`, `app/models/podcast.py`, `app/models/__init__.py`

**Interfaces:**
- Produces: `Participant.portal_token: str`, `Participant.ensure_portal_token() -> str`, `Participant.regenerate_portal_token() -> None`; `Podcast.guest_prep_info: Text|None`; `GuestQuestion(id, podcast_participant_id, question, created_at, email_sent)` with backref `PodcastParticipant.questions` (dynamic). Script helpers used by every later task: `make_show()`, `make_episode(**kw)`, `make_guest(name)`, `add_slot(guest, episode, status="pending", invited=True, role=..., message=None)`, `admin_client()`, `check(name, cond, detail)`, `@register`.

- [ ] **Step 1: Create the verification harness with the first check (will fail: model doesn't exist yet)**

Create `scripts/verify_portal.py`:

```python
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
```

- [ ] **Step 2: Run it to verify it fails**

Run: `docker compose exec -T web uv run python scripts/verify_portal.py`
Expected: traceback `ImportError: cannot import name 'GuestQuestion'` (raised inside `check_models`), then `FAIL check_models raised`, exit code 1.

- [ ] **Step 3: Add the model changes**

`app/models/participant.py` — add `import secrets` at the top and, inside the class, after `created_by_id`:

```python
    portal_token = db.Column(
        db.String(64), unique=True, index=True, default=lambda: secrets.token_urlsafe(32)
    )
```
and after the `episode_slots` relationship:

```python
    def ensure_portal_token(self):
        if not self.portal_token:
            self.portal_token = secrets.token_urlsafe(32)
        return self.portal_token

    def regenerate_portal_token(self):
        self.portal_token = secrets.token_urlsafe(32)
```

`app/models/podcast.py` — after the `notes` column:

```python
    guest_prep_info = db.Column(db.Text)  # guest-visible; unlike `notes`, which is internal
```

Create `app/models/guest_question.py`:

```python
from datetime import datetime, timezone
from ..extensions import db


class GuestQuestion(db.Model):
    __tablename__ = "guest_questions"

    id = db.Column(db.Integer, primary_key=True)
    podcast_participant_id = db.Column(
        db.Integer, db.ForeignKey("podcast_participants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    question = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    email_sent = db.Column(db.Boolean, nullable=False, default=False)

    podcast_participant = db.relationship(
        "PodcastParticipant",
        backref=db.backref("questions", lazy="dynamic", cascade="all, delete-orphan", passive_deletes=True),
    )
```

`app/models/__init__.py` — add `from .guest_question import GuestQuestion` after the `calendar_settings` import and `"GuestQuestion",` to `__all__`.

- [ ] **Step 4: Write the migration**

Create `migrations/versions/f7a8b9c0d1e2_add_participant_portal.py`:

```python
"""add participant portal: participants.portal_token, podcasts.guest_prep_info, guest_questions

Revision ID: f7a8b9c0d1e2
Revises: e6f7a8b9c0d1
Create Date: 2026-09-29

"""
import secrets

from alembic import op
import sqlalchemy as sa

revision = 'f7a8b9c0d1e2'
down_revision = 'e6f7a8b9c0d1'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('participants', sa.Column('portal_token', sa.String(64), nullable=True))
    conn = op.get_bind()
    for (pid,) in conn.execute(sa.text("SELECT id FROM participants")).fetchall():
        conn.execute(
            sa.text("UPDATE participants SET portal_token = :t WHERE id = :i"),
            {"t": secrets.token_urlsafe(32), "i": pid},
        )
    op.create_index('ix_participants_portal_token', 'participants', ['portal_token'], unique=True)

    op.add_column('podcasts', sa.Column('guest_prep_info', sa.Text(), nullable=True))

    op.create_table(
        'guest_questions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('podcast_participant_id', sa.Integer(), nullable=False),
        sa.Column('question', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('email_sent', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.ForeignKeyConstraint(['podcast_participant_id'], ['podcast_participants.id'],
                                name='fk_guest_questions_podcast_participant_id', ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_guest_questions_podcast_participant_id', 'guest_questions',
                    ['podcast_participant_id'])


def downgrade():
    op.drop_index('ix_guest_questions_podcast_participant_id', table_name='guest_questions')
    op.drop_table('guest_questions')
    op.drop_column('podcasts', 'guest_prep_info')
    op.drop_index('ix_participants_portal_token', table_name='participants')
    op.drop_column('participants', 'portal_token')
```

- [ ] **Step 5: Apply, round-trip the downgrade, re-apply, and run the check**

Run:
```bash
docker compose exec -T web uv run flask db upgrade
docker compose exec -T web uv run flask db downgrade
docker compose exec -T web uv run flask db upgrade
docker compose exec -T web uv run python scripts/verify_portal.py
```
Expected: three alembic "Running upgrade/downgrade" lines with no errors; the script prints six `PASS` lines and `6/6 passed`, exit code 0. (No live data exists yet, so regenerating tokens through the downgrade/upgrade cycle is harmless.)

- [ ] **Step 6: Commit**

```bash
git add scripts/verify_portal.py app/models migrations/versions/f7a8b9c0d1e2_add_participant_portal.py
git commit -m "Add portal_token, guest_prep_info and guest_questions" -m "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 2: Guest preparation info field on the episode form

**Files:**
- Modify: `app/forms/podcast.py`, `app/routes/podcasts.py`, `app/templates/podcasts/form.html`, `app/templates/podcasts/detail.html`, `scripts/verify_portal.py`

**Interfaces:**
- Consumes: `Podcast.guest_prep_info` (Task 1); `make_show`, `make_episode`, `admin_client`, `check` (script).
- Produces: `PodcastForm.guest_prep_info`; producers can edit the field at `/podcasts/<id>/edit` and `/podcasts/new`.

- [ ] **Step 1: Add the failing check** (above `# ── runner ──` in `scripts/verify_portal.py`)

```python
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
```

- [ ] **Step 2: Run to verify it fails**

Run: `docker compose exec -T web uv run python scripts/verify_portal.py`
Expected: `FAIL episode form has the guest prep field` and the later three checks fail too.

- [ ] **Step 3: Implement**

`app/forms/podcast.py` — after the `notes` field:

```python
    guest_prep_info = TextAreaField(
        "Guest Preparation Info", validators=[Optional(), Length(max=5000)]
    )
```

`app/routes/podcasts.py` — in `create()` add `guest_prep_info=form.guest_prep_info.data,` after the `notes=form.notes.data,` line; in `edit()` add `podcast.guest_prep_info = form.guest_prep_info.data` after `podcast.notes = form.notes.data`.

`app/templates/podcasts/form.html` — replace the Production Notes card (the `<div class="section-title">Production Notes</div>` block and its card) with:

```html
    <div class="section-title" style="padding-left:0;">Production Notes</div>
    <div class="card mb-4">
      <div class="card-body">
        {{ form.notes(class="form-control", rows=4, placeholder="Internal notes and talking points. Guests never see this.") }}
      </div>
    </div>

    <div class="section-title" style="padding-left:0;">Guest Preparation Info</div>
    <div class="card mb-4">
      <div class="card-body">
        {{ form.guest_prep_info(class="form-control" + (" is-invalid" if form.guest_prep_info.errors else ""), rows=4, placeholder="What guests should know or bring — shown on their dashboard.") }}
        {% for e in form.guest_prep_info.errors %}<div class="invalid-feedback">{{ e }}</div>{% endfor %}
        <div class="form-text">Visible to invited guests who accept. Production Notes above stay internal.</div>
      </div>
    </div>
```

`app/templates/podcasts/detail.html` — directly after the `{% if podcast.notes %} … {% endif %}` block that starts at the "notes" line (~55–58), add:

```html
      {% if podcast.guest_prep_info %}
      <div class="section-title" style="padding-left:0;margin-top:12px;">Guest prep info (shown to guests)</div>
      <p style="font-size:.8rem;color:rgba(var(--ps-ink-rgb),.4);white-space:pre-wrap;margin:0;">{{ podcast.guest_prep_info }}</p>
      {% endif %}
```
(Read lines ~50–60 first and place it inside the same card, after the notes `{% endif %}`, matching that block's markup.)

- [ ] **Step 4: Run to verify it passes**

Run: `docker compose exec -T web uv run python scripts/verify_portal.py`
Expected: all checks `PASS`, `10/10 passed`.

- [ ] **Step 5: Commit**

```bash
git add scripts/verify_portal.py app/forms/podcast.py app/routes/podcasts.py app/templates/podcasts
git commit -m "Add guest preparation info to episodes" -m "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 3: Portal blueprint — dashboard, episode detail, accept/decline

**Files:**
- Create: `app/routes/portal.py`, `app/templates/portal/base.html`, `app/templates/portal/page.html`, `app/templates/portal/_detail.html`, `app/templates/portal/_macros.html`
- Modify: `app/templates/base.html:543`, `app/__init__.py`, `app/models/podcast_participant.py`, `scripts/verify_portal.py`

**Interfaces:**
- Consumes: `Participant.portal_token`, `PodcastParticipant.invited_at`, `guest_prep_info` (Task 1); script helpers.
- Produces: endpoints `portal.dashboard` (`/p/<token>`), `portal.episode` (`/p/<token>/episodes/<int:pp_id>`), `portal.respond` (POST `.../respond`, form field `action` = `accept`|`decline`); helpers in `portal.py`: `_participant_or_404(token) -> Participant`, `_slot_or_404(participant, pp_id) -> PodcastParticipant`; model method `PodcastParticipant.other_confirmed_guests() -> list[PodcastParticipant]`; template context names `token, participant, slots, selected, view ("list"|"detail"), others`; the `standalone` base-template flag. Later tasks add `portal.question` and `portal.email_pdf` endpoints referenced from `_detail.html` — **this task's `_detail.html` must not reference them yet** (Tasks 6/7 add those forms).

- [ ] **Step 1: Add the failing checks**

```python
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
```
(`b2` is created only so a second pending slot exists for Bob; it is deliberately unused otherwise.)

- [ ] **Step 2: Run to verify it fails**

Run: `docker compose exec -T web uv run python scripts/verify_portal.py`
Expected: `check_portal_pages` fails on the first request (404 because the blueprint doesn't exist) — several `FAIL` lines.

- [ ] **Step 3: Add the model helper**

`app/models/podcast_participant.py` — add inside `PodcastParticipant`, after `role_display`:

```python
    def other_confirmed_guests(self):
        """Other guests on this episode who have accepted (never pending/declined), keynotes first."""
        others = self.podcast.participant_slots.filter(
            PodcastParticipant.id != self.id,
            PodcastParticipant.invitation_status == InvitationStatus.ACCEPTED,
        ).all()
        return sorted(
            others,
            key=lambda s: (s.participant_role != ParticipantRole.KEYNOTE_SPEAKER, s.participant.name.lower()),
        )
```

- [ ] **Step 4: Let a template opt out of the app shell**

`app/templates/base.html` line 543: change
`{% if current_user.is_authenticated %}` → `{% if current_user.is_authenticated and not standalone %}`
(`standalone` is an undefined-is-falsy Jinja variable everywhere except templates that `{% set standalone = true %}`.)

- [ ] **Step 5: Write the blueprint**

Create `app/routes/portal.py`:

```python
from datetime import datetime

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for

from ..extensions import db
from ..models import InvitationStatus, Participant, PodcastParticipant, PodcastStatus

portal_bp = Blueprint("portal", __name__)

_STATUS_ORDER = {
    InvitationStatus.PENDING: 0,
    InvitationStatus.ACCEPTED: 1,
    InvitationStatus.DECLINED: 2,
}


def _participant_or_404(token):
    return Participant.query.filter_by(portal_token=token).first_or_404()


def _slot_or_404(participant, pp_id):
    """A slot the guest was actually invited to. Anything else — someone else's
    slot, or one a producer added but never sent — is a 404."""
    pp = PodcastParticipant.query.filter_by(id=pp_id, participant_id=participant.id).first_or_404()
    if pp.invited_at is None:
        abort(404)
    return pp


def _visible_slots(participant):
    slots = participant.episode_slots.filter(PodcastParticipant.invited_at.isnot(None)).all()
    return sorted(
        slots,
        key=lambda s: (
            _STATUS_ORDER[s.invitation_status],
            s.podcast.recording_date is None,
            s.podcast.recording_date or datetime.max,
            s.podcast.title.lower(),
        ),
    )


def _render(participant, token, view, selected):
    others = []
    if selected is not None and selected.invitation_status == InvitationStatus.ACCEPTED:
        others = selected.other_confirmed_guests()
    return render_template(
        "portal/page.html",
        participant=participant,
        token=token,
        slots=_visible_slots(participant),
        selected=selected,
        view=view,
        others=others,
    )


@portal_bp.route("/<token>")
def dashboard(token):
    participant = _participant_or_404(token)
    slots = _visible_slots(participant)
    return _render(participant, token, "list", slots[0] if slots else None)


@portal_bp.route("/<token>/episodes/<int:pp_id>")
def episode(token, pp_id):
    participant = _participant_or_404(token)
    return _render(participant, token, "detail", _slot_or_404(participant, pp_id))


@portal_bp.route("/<token>/episodes/<int:pp_id>/respond", methods=["POST"])
def respond(token, pp_id):
    participant = _participant_or_404(token)
    pp = _slot_or_404(participant, pp_id)
    action = request.form.get("action")

    if pp.podcast.status == PodcastStatus.CANCELLED:
        flash("This episode was cancelled, so it can't be changed.", "warning")
    elif action == "accept":
        pp.accept()
        db.session.commit()
        flash("You're confirmed — thank you!", "success")
    elif action == "decline":
        pp.decline()
        db.session.commit()
        flash("You've declined this invitation. You can change your mind here any time.", "info")
    else:
        flash("Invalid action.", "danger")
    return redirect(url_for("portal.episode", token=token, pp_id=pp.id))
```

`app/__init__.py` — where the other blueprints are imported, add `from .routes.portal import portal_bp` (match the file's import style), and after `app.register_blueprint(calendar_bp)` add:

```python
    app.register_blueprint(portal_bp, url_prefix="/p")
```

- [ ] **Step 6: Write the templates**

Create `app/templates/portal/_macros.html`:

```html
{% macro when(d) -%}
{%- if d -%}{{ d.strftime('%a, %b') }} {{ d.day }}, {{ d.year }} · {{ d.strftime('%I:%M %p').lstrip('0') }}{%- else -%}TBD{%- endif -%}
{%- endmacro %}

{% macro pill(s) -%}
{%- if s.podcast.status.value == 'cancelled' -%}<span class="pill pill-cancelled">Cancelled</span>
{%- elif s.invitation_status.value == 'pending' -%}<span class="pill pill-pending">Needs response</span>
{%- elif s.invitation_status.value == 'accepted' -%}<span class="pill pill-accepted">Confirmed</span>
{%- else -%}<span class="pill pill-declined">Declined</span>{%- endif -%}
{%- endmacro %}
```

Create `app/templates/portal/base.html`:

```html
{% extends "base.html" %}
{% set standalone = true %}
{% block extra_head %}
<meta name="robots" content="noindex,nofollow">
<meta name="referrer" content="no-referrer">
<style>
  .portal { max-width: 520px; margin: 0 auto; padding: 20px 14px 40px; }
  .portal-hello h1 { font-size: 1.25rem; font-weight: 800; margin: 0 0 4px; }
  .portal-hello p { color: var(--ps-text-muted); font-size: .9rem; margin-bottom: 16px; }
  .portal[data-view="list"] .portal-detail { display: none; }
  .portal[data-view="detail"] .portal-list,
  .portal[data-view="detail"] .portal-hello { display: none; }
  .portal .btn { min-height: 48px; display: inline-flex; align-items: center; justify-content: center; gap: 6px; }
  .portal .btn-full { width: 100%; }
  .portal textarea, .portal input { font-size: 16px; }
  .portal-back { display: inline-flex; align-items: center; gap: 4px; min-height: 48px; color: var(--ps-accent); text-decoration: none; font-weight: 600; }
  .portal .row-card.selected { border-color: var(--ps-accent); background: var(--ps-accent-dim); }
  .pill { font-size: .7rem; font-weight: 700; padding: 3px 9px; border-radius: 20px; white-space: nowrap; }
  .pill-pending  { background: rgba(var(--ps-yellow-rgb), .18); color: var(--ps-yellow); }
  .pill-accepted { background: rgba(var(--ps-green-rgb), .16);  color: var(--ps-green); }
  .pill-declined { background: rgba(var(--ps-red-rgb), .16);    color: var(--ps-red); }
  .pill-cancelled { background: var(--ps-badge-cancelled-bg);   color: var(--ps-badge-cancelled-fg); }
  .detail-row { display: flex; gap: 10px; padding: 10px 0; border-bottom: 1px solid var(--ps-border); font-size: .9rem; }
  .detail-row:last-child { border-bottom: 0; }
  .detail-row .k { width: 96px; flex-shrink: 0; color: var(--ps-text-muted); }
  .detail-row .v { flex: 1; min-width: 0; overflow-wrap: anywhere; }
  .portal-cover { width: 100%; max-height: 220px; object-fit: cover; border-radius: 14px; margin-bottom: 14px; }
  .prewrap { white-space: pre-wrap; overflow-wrap: anywhere; }

  @media (min-width: 992px) {
    .portal { max-width: 1100px; display: grid; grid-template-columns: 340px minmax(0, 1fr); gap: 24px; align-items: start; }
    .portal[data-view] .portal-list, .portal[data-view] .portal-detail { display: block; }
    .portal[data-view] .portal-hello { display: block; grid-column: 1 / -1; }
    .portal-back { display: none; }
  }

  @media print {
    html:root[data-bs-theme] {
      --ps-bg: #fff; --ps-surface: #fff; --ps-surface2: #fff; --ps-text: #000;
      --ps-text-muted: #444; --ps-border: #ccc; --ps-ink-rgb: 0,0,0;
    }
    body { background: #fff !important; color: #000 !important; }
    .portal-list, .portal-hello, .portal-back, .no-print { display: none !important; }
    .portal { display: block; max-width: none; padding: 0; }
    .portal .portal-detail { display: block !important; }
    .portal .card { break-inside: avoid; box-shadow: none; }
  }
</style>
{% endblock %}
```

Create `app/templates/portal/page.html`:

```html
{% extends "portal/base.html" %}
{% from "portal/_macros.html" import when, pill %}
{% block title %}Your episodes — PodScheduler{% endblock %}
{% block content %}
<div class="portal" data-view="{{ view }}">
  <div class="portal-hello">
    <h1>Hi {{ participant.name.split()[0] if participant.name else 'there' }} 👋</h1>
    <p>Your episodes with us. Bookmark this page to come back any time.</p>
  </div>

  <aside class="portal-list">
    <div class="section-title" style="padding-left:0;">Your episodes</div>
    {% for s in slots %}
    <a class="row-card{% if selected and s.id == selected.id %} selected{% endif %}"
       href="{{ url_for('portal.episode', token=token, pp_id=s.id) }}">
      <div class="rc-icon"><i class="bi bi-mic"></i></div>
      <div class="rc-body">
        <div class="rc-title">{{ s.podcast.title }}</div>
        <div class="rc-sub">Recording: {{ when(s.podcast.recording_date) }}</div>
      </div>
      <div class="rc-end">{{ pill(s) }}</div>
    </a>
    {% else %}
    <div style="text-align:center;padding:32px 8px;color:var(--ps-text-muted);">
      <div style="font-size:2rem;">🎙️</div>
      <div style="font-weight:700;margin-top:6px;">No invitations yet</div>
      <div style="font-size:.85rem;">When you're invited to an episode it will show up here.</div>
    </div>
    {% endfor %}
  </aside>

  <section class="portal-detail">
    {% if selected %}
      {% include "portal/_detail.html" %}
    {% else %}
      <div style="text-align:center;padding:32px 8px;color:var(--ps-text-muted);">Select an episode to see its details.</div>
    {% endif %}
  </section>
</div>
{% endblock %}
```

Create `app/templates/portal/_detail.html`:

```html
{% from "portal/_macros.html" import when, pill %}
{% set pp = selected %}
{% set ep = pp.podcast %}
{% set cancelled = ep.status.value == 'cancelled' %}
{% set accepted = pp.invitation_status.value == 'accepted' and not cancelled %}

<a class="portal-back no-print" href="{{ url_for('portal.dashboard', token=token) }}"><i class="bi bi-chevron-left"></i> All episodes</a>

{% if ep.show and ep.show.cover_image_url %}
<img class="portal-cover" src="{{ ep.show.cover_image_url }}" alt="">
{% endif %}

<div class="d-flex align-items-start gap-2 mb-1">
  <h2 style="font-size:1.3rem;font-weight:800;flex:1;margin:0;overflow-wrap:anywhere;">{{ ep.title }}</h2>
  {{ pill(pp) }}
</div>
{% if ep.show %}<div style="color:var(--ps-text-muted);font-size:.85rem;margin-bottom:12px;">{{ ep.show.title }}</div>{% endif %}

{% if cancelled %}
<div class="card mb-3"><div class="card-body">This episode was cancelled.</div></div>
{% else %}
<div class="card mb-3"><div class="card-body">
  <div class="detail-row"><div class="k">Recording</div><div class="v">{{ when(ep.recording_date) }}</div></div>
  {% if accepted %}
  <div class="detail-row"><div class="k">Release</div><div class="v">{{ when(ep.scheduled_date) }}</div></div>
  {% endif %}
  <div class="detail-row"><div class="k">Host</div><div class="v">{{ ep.host.username }}</div></div>
  <div class="detail-row"><div class="k">Your role</div><div class="v">{{ pp.role_display }}</div></div>
  {% if ep.topic %}<div class="detail-row"><div class="k">Topic</div><div class="v">{{ ep.topic }}</div></div>{% endif %}
  {% if ep.duration_minutes %}<div class="detail-row"><div class="k">Length</div><div class="v">About {{ ep.duration_minutes }} minutes</div></div>{% endif %}
</div></div>

{% if pp.invitation_status.value == 'pending' %}
<form method="post" action="{{ url_for('portal.respond', token=token, pp_id=pp.id) }}" class="d-flex flex-column gap-2 mb-3 no-print">
  <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
  <button type="submit" name="action" value="accept" class="btn btn-accent btn-full">✓ Accept invitation</button>
  <button type="submit" name="action" value="decline" class="btn btn-outline-secondary btn-full">Decline</button>
</form>
{% endif %}

{% if accepted %}
  {% if ep.description %}
  <div class="section-title" style="padding-left:0;">About this episode</div>
  <div class="card mb-3"><div class="card-body prewrap">{{ ep.description }}</div></div>
  {% endif %}
  {% if pp.message %}
  <div class="section-title" style="padding-left:0;">A note from the host</div>
  <div class="card mb-3"><div class="card-body prewrap">{{ pp.message }}</div></div>
  {% endif %}
  {% if ep.guest_prep_info %}
  <div class="section-title" style="padding-left:0;">How to prepare</div>
  <div class="card mb-3"><div class="card-body prewrap">{{ ep.guest_prep_info }}</div></div>
  {% endif %}
  {% if others %}
  <div class="section-title" style="padding-left:0;">Also on this episode</div>
  <div class="card mb-3"><div class="card-body">
    {% for o in others %}
    <div class="detail-row"><div class="v">{{ o.participant.name }}</div><div class="k" style="width:auto;">{{ o.role_display }}</div></div>
    {% endfor %}
  </div></div>
  {% endif %}

  <div class="d-flex flex-column gap-2 mb-3 no-print">
    <button type="button" class="btn btn-outline-secondary btn-full" onclick="window.print()"><i class="bi bi-printer"></i> Print</button>
  </div>

  <form method="post" action="{{ url_for('portal.respond', token=token, pp_id=pp.id) }}" class="mb-3 no-print">
    <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
    <button type="submit" name="action" value="decline" class="btn btn-outline-danger btn-full">I can't make it — decline</button>
  </form>
{% elif pp.invitation_status.value == 'declined' %}
  <form method="post" action="{{ url_for('portal.respond', token=token, pp_id=pp.id) }}" class="mb-3 no-print">
    <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
    <p style="color:var(--ps-text-muted);font-size:.9rem;">You declined this invitation. Changed your mind?</p>
    <button type="submit" name="action" value="accept" class="btn btn-accent btn-full">✓ Accept invitation</button>
  </form>
{% endif %}
{% endif %}
```

- [ ] **Step 7: Run to verify it passes**

Run: `docker compose exec -T web uv run python scripts/verify_portal.py`
Expected: every check `PASS` (about 39 total), exit 0. If the two "no app shell" checks fail, the `{% set standalone %}` did not reach `base.html` — confirm `portal/base.html` has the `set` at top level (outside any block) and that the `base.html` condition was edited.

- [ ] **Step 8: Commit**

```bash
git add scripts/verify_portal.py app/routes/portal.py app/templates/portal app/templates/base.html app/__init__.py app/models/podcast_participant.py
git commit -m "Add participant portal dashboard and episode pages" -m "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 4: Invitation email links redirect into the portal

**Files:**
- Modify: `app/routes/invitations.py`, `scripts/verify_portal.py`
- Delete: `app/templates/invitations/accepted.html`, `declined.html`, `already_responded.html`

**Interfaces:**
- Consumes: `portal.episode` endpoint, `Participant.ensure_portal_token()`.
- Produces: `/invitations/<token>/<action>` now always ends in a redirect (302) to `/p/<portal_token>/episodes/<pp.id>`, except invalid action → `main.index` (unchanged) and unknown token → 404 (unchanged).

- [ ] **Step 1: Add the failing check**

```python
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
```

- [ ] **Step 2: Run to verify it fails**

Run: `docker compose exec -T web uv run python scripts/verify_portal.py`
Expected: `FAIL email accept link redirects into the portal` (currently returns 200 with the static page), plus the cancelled check failing.

- [ ] **Step 3: Rewrite the route**

Replace the whole of `app/routes/invitations.py` with:

```python
from flask import Blueprint, redirect, url_for, flash
from ..extensions import db
from ..models.podcast import PodcastStatus
from ..models.podcast_participant import PodcastParticipant, InvitationStatus

invitations_bp = Blueprint("invitations", __name__)


@invitations_bp.route("/<token>/<action>")
def respond(token, action):
    pp = PodcastParticipant.query.filter_by(invitation_token=token).first_or_404()

    if action not in ("accept", "decline"):
        flash("Invalid action.", "danger")
        return redirect(url_for("main.index"))

    if pp.podcast.status == PodcastStatus.CANCELLED:
        flash("This episode was cancelled.", "warning")
    elif pp.invitation_status != InvitationStatus.PENDING:
        flash(f"You already {pp.invitation_status.value} this invitation. You can change your answer below.", "info")
    elif action == "accept":
        pp.accept()
        flash("You're confirmed — thank you!", "success")
    else:
        pp.decline()
        flash("You've declined this invitation. You can change your mind here any time.", "info")

    portal_token = pp.participant.ensure_portal_token()
    db.session.commit()
    return redirect(url_for("portal.episode", token=portal_token, pp_id=pp.id))
```

- [ ] **Step 4: Remove the now-unused templates**

Run: `git rm app/templates/invitations/accepted.html app/templates/invitations/declined.html app/templates/invitations/already_responded.html && grep -rn "invitations/accepted\|invitations/declined\|already_responded" app || echo "no references left"`
Expected: `no references left`.

- [ ] **Step 5: Run to verify it passes**

Run: `docker compose exec -T web uv run python scripts/verify_portal.py`
Expected: all checks `PASS`.

- [ ] **Step 6: Commit**

```bash
git add scripts/verify_portal.py app/routes/invitations.py
git commit -m "Redirect invitation links into the participant portal" -m "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 5: `portal_url` merge field, fallback-email link, producer-side link management

**Files:**
- Modify: `app/email.py`, `app/models/email_template.py`, `app/routes/email_templates.py`, `app/templates/email/invitation.html`, `app/templates/email/invitation.txt`, `app/routes/participants.py`, `app/templates/participants/form.html`, `scripts/verify_portal.py`

**Interfaces:**
- Consumes: `portal.dashboard`, `Participant.ensure_portal_token()`, `Participant.regenerate_portal_token()`.
- Produces: merge field `portal_url` (in `MERGE_FIELDS` and `_build_context`); endpoint `participants.regenerate_portal_link` (POST `/participants/<int:participant_id>/regenerate-portal-link`, permission `manage_participants`).

- [ ] **Step 1: Add the failing check**

```python
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
```

- [ ] **Step 2: Run to verify it fails**

Run: `docker compose exec -T web uv run python scripts/verify_portal.py`
Expected: `FAIL portal_url is a merge field` then a `KeyError`/failures further down.

- [ ] **Step 3: Implement**

`app/models/email_template.py` — in `MERGE_FIELDS`, after `"decline_url"`:

```python
    "portal_url": "Guest's private dashboard link (all their episodes)",
```

`app/email.py` — in `_build_context`, after the `decline_url = url_for(...)` block:

```python
    portal_url = url_for(
        "portal.dashboard",
        token=participant.ensure_portal_token(),
        _external=True,
    )
```
and in the returned dict, after `"decline_url": decline_url,`:
```python
        "portal_url": portal_url,
```

`app/routes/email_templates.py` — in the sample context dict (after `"decline_url": "#decline",`) add `"portal_url": "#portal",`.

`app/templates/email/invitation.html` — replace the paragraph
```html
    <p style="font-size:.85rem; color:#6c757d;">
      These links are unique to you. No account required to respond.
    </p>
```
with
```html
    <p style="font-size:.85rem; color:#6c757d;">
      These links are unique to you. No account required to respond.
    </p>
    <p style="font-size:.85rem; color:#6c757d;">
      <a href="{{ portal_url }}">View all your episodes</a> — bookmark it to come back any time.
    </p>
```

`app/templates/email/invitation.txt` — after the `{{ decline_url }}` line add:

```
To see all your episodes (bookmark this to come back any time):
{{ portal_url }}
```
(keep a blank line before it and the existing `---` footer after it).

`app/routes/participants.py` — in `edit()`, change the final `return` to pass the link:

```python
    if participant.portal_token is None:
        participant.ensure_portal_token()
        db.session.commit()
    portal_url = url_for("portal.dashboard", token=participant.portal_token, _external=True)
    return render_template("participants/form.html", form=form, participant=participant, portal_url=portal_url)
```
Add a new route at the end of the file:

```python
@participants_bp.route("/<int:participant_id>/regenerate-portal-link", methods=["POST"])
@login_required
@permission_required("manage_participants")
def regenerate_portal_link(participant_id):
    participant = Participant.query.get_or_404(participant_id)
    participant.regenerate_portal_token()
    db.session.commit()
    flash("Portal link regenerated. The old link no longer works — send the new one to the guest.", "success")
    return redirect(url_for("participants.edit", participant_id=participant.id))
```
`create()`'s `render_template("participants/form.html", form=form, participant=None)` needs no change (the new block is guarded by `{% if participant %}`).

`app/templates/participants/form.html` — insert between `  </form>` and the closing `</div>` that precedes `{% endblock %}`:

```html
  {% if participant %}
  <div class="section-title" style="padding-left:0;margin-top:20px;">Guest dashboard link</div>
  <div class="card mb-4">
    <div class="card-body" style="display:flex;flex-direction:column;gap:10px;">
      <div style="font-size:.85rem;color:var(--ps-text-muted);">Private link to this guest's episode dashboard. Anyone with it can see their episodes.</div>
      <input type="text" id="portalLink" class="form-control" value="{{ portal_url }}" readonly>
      <button type="button" class="btn btn-outline-secondary btn-full" style="min-height:48px;"
              onclick="navigator.clipboard.writeText(document.getElementById('portalLink').value);this.textContent='Copied ✓';">Copy link</button>
      <form method="post" action="{{ url_for('participants.regenerate_portal_link', participant_id=participant.id) }}"
            onsubmit="return confirm('Regenerate the link? The current link will stop working immediately.');">
        <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
        <button type="submit" class="btn btn-outline-danger btn-full" style="min-height:48px;">Regenerate link</button>
      </form>
    </div>
  </div>
  {% endif %}
```

- [ ] **Step 4: Run to verify it passes**

Run: `docker compose exec -T web uv run python scripts/verify_portal.py`
Expected: all checks `PASS`.

- [ ] **Step 5: Commit**

```bash
git add scripts/verify_portal.py app/email.py app/models/email_template.py app/routes/email_templates.py app/routes/participants.py app/templates/email app/templates/participants/form.html
git commit -m "Add portal_url merge field and link management" -m "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 6: Email a question to the host

**Files:**
- Modify: `app/email.py`, `app/routes/portal.py`, `app/templates/portal/_detail.html`, `scripts/verify_portal.py`

**Interfaces:**
- Consumes: `GuestQuestion`, `PodcastParticipant.questions`, `_slot_or_404`, `_participant_or_404`, `_send`.
- Produces: `_send(to_email, subject, html_body, text_body, reply_to=None, attachments=None) -> bool` (Task 7 reuses `attachments`); `send_guest_question_email(question: GuestQuestion) -> bool`; endpoint `portal.question` (POST `/p/<token>/episodes/<pp_id>/question`, form field `question`).

- [ ] **Step 1: Add the failing check**

```python
@register
def check_questions():
    from app.models import GuestQuestion
    alice, bob = make_guest("Alice"), make_guest("Bob")
    ep, ep_cancelled = make_episode(), make_episode(status=PodcastStatus.CANCELLED)
    ok = add_slot(alice, ep, "accepted")
    pending = add_slot(bob, ep, "pending")
    cancelled = add_slot(alice, ep_cancelled, "accepted")
    c = app.test_client()
    url = lambda g, s: f"/p/{g.portal_token}/episodes/{s.id}/question"

    with mail.record_messages() as out:
        r = c.post(url(alice, ok), data={"question": "What mic should I use? <b>&</b>"})
    db.session.expire_all()
    q = GuestQuestion.query.filter_by(podcast_participant_id=ok.id).first()
    check("question saved and redirects", r.status_code == 302 and q is not None)
    check("question marked emailed", q is not None and q.email_sent is True)
    check("host emailed with guest as reply-to",
          len(out) == 1 and out[0].recipients == [admin().email] and out[0].reply_to == alice.email
          and "What mic should I use?" in out[0].body, str([(m.recipients, m.reply_to) for m in out]))

    n0 = GuestQuestion.query.count()
    c.post(url(alice, ok), data={"question": "   "})
    c.post(url(alice, ok), data={"question": "x" * 2001})
    c.post(url(bob, pending), data={"question": "not accepted yet"})
    c.post(url(alice, cancelled), data={"question": "cancelled episode"})
    check("empty / 2001-char / pending / cancelled questions are rejected", GuestQuestion.query.count() == n0)
    check("question on another guest's slot -> 404", c.post(url(bob, ok), data={"question": "hi"}).status_code == 404)

    real_send = mail.send
    def boom(msg):
        raise RuntimeError("smtp down")
    mail.send = boom
    try:
        r = c.post(url(alice, ok), data={"question": "second question"}, follow_redirects=True)
    finally:
        mail.send = real_send
    db.session.expire_all()
    q2 = GuestQuestion.query.filter_by(podcast_participant_id=ok.id, question="second question").first()
    check("mail failure: question still saved, email_sent False", q2 is not None and q2.email_sent is False)
    # (no apostrophes in the needle: flashed text is HTML-escaped, so "couldn't" renders as "couldn&#39;t")
    check("mail failure: guest told plainly", "email it to the host right now" in r.get_data(as_text=True))
```

- [ ] **Step 2: Run to verify it fails**

Run: `docker compose exec -T web uv run python scripts/verify_portal.py`
Expected: `FAIL question saved and redirects` (404, route missing) and the rest.

- [ ] **Step 3: Extend the mail helpers**

`app/email.py` — add `from flask_mail import Message` is already imported; replace `_send` with:

```python
def _send(to_email, subject, html_body, text_body, reply_to=None, attachments=None):
    msg = Message(subject=subject, recipients=[to_email], html=html_body, body=text_body, reply_to=reply_to)
    for filename, content_type, data in attachments or []:
        msg.attach(filename, content_type, data)
    try:
        mail.send(msg)
        return True
    except Exception as e:
        current_app.logger.error(f"Failed to send email to {to_email}: {e}")
        return False


def send_guest_question_email(question):
    pp = question.podcast_participant
    guest = pp.participant
    episode = pp.podcast
    subject = f"Question from {guest.name} about {episode.title}"
    text = (
        f'{guest.name} <{guest.email}> asked about "{episode.title}":\n\n'
        f"{question.question}\n\n"
        "— Reply to this email to answer them directly."
    )
    return _send(episode.host.email, subject, None, text, reply_to=guest.email)
```

- [ ] **Step 4: Add the route and form**

`app/routes/portal.py` — add `from ..email import send_guest_question_email` and `from ..models import GuestQuestion` (extend the existing `..models` import), then append:

```python
MAX_QUESTION_LENGTH = 2000


@portal_bp.route("/<token>/episodes/<int:pp_id>/question", methods=["POST"])
def question(token, pp_id):
    participant = _participant_or_404(token)
    pp = _slot_or_404(participant, pp_id)
    text = (request.form.get("question") or "").strip()

    if pp.podcast.status == PodcastStatus.CANCELLED or pp.invitation_status != InvitationStatus.ACCEPTED:
        flash("You can ask the host a question once you've accepted an active episode.", "warning")
    elif not text:
        flash("Please type your question first.", "warning")
    elif len(text) > MAX_QUESTION_LENGTH:
        flash(f"Please keep your question under {MAX_QUESTION_LENGTH:,} characters.", "warning")
    else:
        q = GuestQuestion(podcast_participant_id=pp.id, question=text)
        db.session.add(q)
        db.session.commit()
        if send_guest_question_email(q):
            q.email_sent = True
            db.session.commit()
            flash("Your question was sent to the host. They'll reply by email.", "success")
        else:
            flash("We saved your question but couldn't email it to the host right now. "
                  "Please try again later or contact them directly.", "warning")
    return redirect(url_for("portal.episode", token=token, pp_id=pp.id))
```

`app/templates/portal/_detail.html` — inside the `{% if accepted %}` block, immediately before the `<form ... action="{{ url_for('portal.respond' ... 'decline' ...` "I can't make it" form, insert:

```html
  <div class="card mb-3 no-print"><div class="card-body">
    <form method="post" action="{{ url_for('portal.question', token=token, pp_id=pp.id) }}">
      <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
      <label class="form-label" for="guestQuestion">Ask the host a question</label>
      <textarea id="guestQuestion" name="question" class="form-control mb-2" rows="3" maxlength="2000" required
                placeholder="Anything you'd like to know before the recording…"></textarea>
      <button type="submit" class="btn btn-accent btn-full"><i class="bi bi-send"></i> Send question</button>
    </form>
  </div></div>
```

- [ ] **Step 5: Run to verify it passes**

Run: `docker compose exec -T web uv run python scripts/verify_portal.py`
Expected: all checks `PASS`.

- [ ] **Step 6: Commit**

```bash
git add scripts/verify_portal.py app/email.py app/routes/portal.py app/templates/portal/_detail.html
git commit -m "Let guests email a question to the host" -m "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 7: Emailed PDF of the episode details

**Files:**
- Create: `app/pdf.py`
- Modify: `pyproject.toml`, `uv.lock`, `app/email.py`, `app/routes/portal.py`, `app/templates/portal/_detail.html`, `scripts/verify_portal.py`

**Interfaces:**
- Consumes: `_send(..., attachments=[(filename, content_type, bytes)])` (Task 6), `PodcastParticipant.other_confirmed_guests()` (Task 3).
- Produces: `build_episode_pdf(pp) -> bytes`; `send_episode_pdf_email(pp) -> bool` (recipient is always `pp.participant.email`); endpoint `portal.email_pdf` (POST `/p/<token>/episodes/<pp_id>/email-pdf`).

- [ ] **Step 1: Install the dependency**

Run:
```bash
docker compose exec -T web uv add "reportlab>=4.2"
docker compose exec -T web uv run python -c "import reportlab; print(reportlab.Version)"
git diff --stat pyproject.toml uv.lock
```
Expected: a version like `4.x` printed; both `pyproject.toml` and `uv.lock` show changes (the project directory is bind-mounted, so the container edits the host files). `reportlab` is pure Python for our use (needs Pillow, already a dependency), so the Docker image needs no system packages; a later `docker compose up --build` picks it up from the lockfile.

- [ ] **Step 2: Add the failing check**

```python
@register
def check_pdf():
    from reportlab import rl_config
    rl_config.pageCompression = 0  # keep PDF text greppable for this check
    from app.pdf import build_episode_pdf
    alice, bob, carol = make_guest("Alice"), make_guest("Bob"), make_guest("Carol")
    show = make_show()
    ep = make_episode(show_id=show.id, notes="SECRET-PRODUCTION-NOTES",
                      guest_prep_info="Bring a headset & <b>arrive</b> early </b> R&D <3",
                      description="Desc <i>unbalanced")
    pp = add_slot(alice, ep, "accepted", role=ParticipantRole.KEYNOTE_SPEAKER, message="Hi & welcome")
    add_slot(bob, ep, "accepted")
    add_slot(carol, ep, "pending")

    data = build_episode_pdf(pp)
    check("PDF bytes are a PDF", data[:5] == b"%PDF-")
    check("PDF includes prep info and confirmed co-guest", b"headset" in data and b"Bob Verify" in data)
    check("PDF excludes production notes and pending co-guests",
          b"SECRET-PRODUCTION-NOTES" not in data and b"Carol Verify" not in data)

    ep_cancelled = make_episode(status=PodcastStatus.CANCELLED)
    cancelled = add_slot(alice, ep_cancelled, "accepted")
    pending = add_slot(bob, ep_cancelled, "pending")
    c = app.test_client()
    url = lambda g, s: f"/p/{g.portal_token}/episodes/{s.id}/email-pdf"

    with mail.record_messages() as out:
        r = c.post(url(alice, pp))
    check("email-pdf redirects", r.status_code == 302, str(r.status_code))
    check("PDF emailed only to the guest's own address", len(out) == 1 and out[0].recipients == [alice.email], str([m.recipients for m in out]))
    att = out[0].attachments[0] if out and out[0].attachments else None
    check("PDF attached as a .pdf", att is not None and att.filename.endswith(".pdf") and att.data[:5] == b"%PDF-")

    with mail.record_messages() as out:
        c.post(url(alice, cancelled))
        c.post(url(bob, pending))
    check("no PDF for cancelled or unaccepted episodes", len(out) == 0)
    check("PDF on another guest's slot -> 404", c.post(url(bob, pp)).status_code == 404)
```

- [ ] **Step 3: Run to verify it fails**

Run: `docker compose exec -T web uv run python scripts/verify_portal.py`
Expected: `check_pdf raised` with `ModuleNotFoundError: No module named 'app.pdf'`.

- [ ] **Step 4: Write the PDF builder**

Create `app/pdf.py`:

```python
from io import BytesIO
from xml.sax.saxutils import escape

from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer


def _fmt(dt):
    if not dt:
        return "TBD"
    return f"{dt.strftime('%A, %B')} {dt.day}, {dt.year} at {dt.strftime('%I').lstrip('0')}:{dt.strftime('%M %p')}"


def _para(text, style):
    # Paragraph parses XML-ish markup, so user text must be escaped (and newlines made explicit).
    return Paragraph(escape(text).replace("\n", "<br/>"), style)


def build_episode_pdf(pp):
    """PDF of what an *accepted* guest sees on their episode page. Never includes
    Podcast.notes (internal) or unconfirmed guests."""
    episode = pp.podcast
    styles = getSampleStyleSheet()
    title = ParagraphStyle("PSTitle", parent=styles["Title"], alignment=0, fontSize=20, leading=24)
    heading = ParagraphStyle("PSHeading", parent=styles["Heading3"], spaceBefore=12, spaceAfter=2)
    body = styles["BodyText"]

    story = [_para(episode.title, title)]
    if episode.show:
        story.append(_para(episode.show.title, body))
    story.append(Spacer(1, 6))

    rows = [
        ("Your role", pp.role_display),
        ("Recording", _fmt(episode.recording_date)),
        ("Release", _fmt(episode.scheduled_date)),
        ("Host", episode.host.username),
        ("Topic", episode.topic),
        ("Length", f"About {episode.duration_minutes} minutes" if episode.duration_minutes else None),
    ]
    for label, value in rows:
        if value:
            story.append(Paragraph(f"<b>{escape(label)}:</b> {escape(str(value))}", body))

    sections = [
        ("About this episode", episode.description),
        ("A note from the host", pp.message),
        ("How to prepare", episode.guest_prep_info),
    ]
    for label, value in sections:
        if value:
            story.append(Paragraph(escape(label), heading))
            story.append(_para(value, body))

    others = pp.other_confirmed_guests()
    if others:
        story.append(Paragraph("Also on this episode", heading))
        for o in others:
            story.append(_para(f"{o.participant.name} ({o.role_display})", body))

    buf = BytesIO()
    SimpleDocTemplate(
        buf, pagesize=letter, title=episode.title,
        leftMargin=inch, rightMargin=inch, topMargin=inch, bottomMargin=inch,
    ).build(story)
    return buf.getvalue()
```

- [ ] **Step 5: Email helper, route, button**

`app/email.py` — add at the top `from werkzeug.utils import secure_filename` and `from .pdf import build_episode_pdf`, then append:

```python
def send_episode_pdf_email(pp):
    """Email the episode details PDF to the participant's own address only."""
    episode = pp.podcast
    filename = f"{secure_filename(episode.title) or 'episode'}.pdf"
    subject = f"Details for {episode.title}"
    text = (
        f"Hi {pp.participant.name},\n\n"
        f'Attached are your details for "{episode.title}".\n\n'
        "Sent via PodScheduler"
    )
    return _send(
        pp.participant.email, subject, None, text,
        attachments=[(filename, "application/pdf", build_episode_pdf(pp))],
    )
```

`app/routes/portal.py` — extend the email import to `from ..email import send_episode_pdf_email, send_guest_question_email` and append:

```python
@portal_bp.route("/<token>/episodes/<int:pp_id>/email-pdf", methods=["POST"])
def email_pdf(token, pp_id):
    participant = _participant_or_404(token)
    pp = _slot_or_404(participant, pp_id)

    if pp.podcast.status == PodcastStatus.CANCELLED or pp.invitation_status != InvitationStatus.ACCEPTED:
        flash("The PDF is available once you've accepted an active episode.", "warning")
    elif send_episode_pdf_email(pp):
        flash(f"We emailed the details to {participant.email}.", "success")
    else:
        flash("We couldn't send the email right now. You can still use Print on this page.", "warning")
    return redirect(url_for("portal.episode", token=token, pp_id=pp.id))
```

`app/templates/portal/_detail.html` — replace the Print button block

```html
  <div class="d-flex flex-column gap-2 mb-3 no-print">
    <button type="button" class="btn btn-outline-secondary btn-full" onclick="window.print()"><i class="bi bi-printer"></i> Print</button>
  </div>
```
with

```html
  <div class="d-flex flex-column gap-2 mb-3 no-print">
    <button type="button" class="btn btn-outline-secondary btn-full" onclick="window.print()"><i class="bi bi-printer"></i> Print</button>
    <form method="post" action="{{ url_for('portal.email_pdf', token=token, pp_id=pp.id) }}">
      <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
      <button type="submit" class="btn btn-outline-secondary btn-full"><i class="bi bi-envelope"></i> Email me a PDF</button>
    </form>
  </div>
```

- [ ] **Step 6: Run to verify it passes**

Run: `docker compose exec -T web uv run python scripts/verify_portal.py`
Expected: all checks `PASS`. If `b"Bob Verify" in data` fails but the rest pass, reportlab split the text into separate operators — search for a shorter token (`b"Verify"`) and note it in the commit; don't loosen the *exclusion* checks.

- [ ] **Step 7: Commit**

```bash
git add scripts/verify_portal.py app/pdf.py app/email.py app/routes/portal.py app/templates/portal/_detail.html pyproject.toml uv.lock
git commit -m "Let guests email themselves a PDF of episode details" -m "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 8: Documentation, full verification, visual check

**Files:**
- Modify: `CLAUDE.md`

**Interfaces:**
- Consumes: everything above.
- Produces: nothing new; leaves docs accurate and the branch verified.

- [ ] **Step 1: Update CLAUDE.md** (make each edit with the Edit tool against the current text)

- **Project layout** tree: add under `routes/`: `portal.py          # /p/<token>/* — public guest dashboard (episodes, accept/decline, questions, PDF)`; under `app/`: `pdf.py              # build_episode_pdf(pp) via reportlab`; under `models/`: `guest_question.py   # GuestQuestion — questions guests send to the host`; under `templates/`: `portal/            # base.html, page.html, _detail.html, _macros.html — standalone guest UI`; top level: `scripts/verify_portal.py  # verification harness for the portal (no test suite)`.
- **Tech stack** table: add row `| PDF | reportlab — emailed episode-details PDF for guests |`.
- **Database models**: Participant gains `portal_token` (unique, `token_urlsafe(32)`; `ensure_portal_token()`, `regenerate_portal_token()`); Podcast gains `guest_prep_info` (guest-visible; contrast `notes`, internal); new `### GuestQuestion` section (`id`, `podcast_participant_id` FK cascade, `question`, `created_at`, `email_sent`).
- **Merge fields** list: add `portal_url`.
- **Email invitation flow**: replace steps 4–5 with: guest clicks the link → `/invitations/<token>/accept|decline` records the response (one click, on open) and **redirects** to `/p/<portal_token>/episodes/<pp_id>`.
- **New section "Participant portal"** documenting: per-person `portal_token` link is the whole authorization model (like the ICS feed; regenerate on the participant edit page to revoke, old URL 404s immediately); every query scoped to the token owner, foreign or never-invited (`invited_at IS NULL`) slots 404; visibility rules (pending/declined guests see title/topic/host/recording date/role only; description, release date, host message, prep info and other *accepted* guests' names only after accepting; `notes` never); cancelled episodes refuse all actions; questions are saved then emailed with `Reply-To` = guest, `email_sent=False` if mail fails; PDF is emailed only to the participant's own address; `standalone` flag in `base.html` (a template that does `{% set standalone = true %}` renders without the app shell even for logged-in users); wide-screen split view vs. phone two-screen flow; times are naive wall-clock with no timezone shown (known limitation); email link scanners can respond on a guest's behalf because Accept/Decline are one-click GETs (accepted trade-off; guests can change their answer in the portal).
- **Known sharp edges**: add "`scripts/verify_portal.py` must stop the first request from calling `_load_mail_settings` (it re-inits Flask-Mail from the DB's real SMTP settings) and must set `app.extensions['mail'].suppress = True` — setting `app.config['MAIL_SUPPRESS_SEND']` after `create_app()` does nothing because Flask-Mail reads it at `init_app` time. Ad-hoc scripts that send mail have tried real SMTP because of this."
- **"What this project does NOT have"**: change "No tests (yet)" to "No test suite (only `scripts/verify_portal.py` for the portal)"; add to the file-upload bullet nothing (no uploads added); add under API/JSON endpoints: "the guest portal adds public POST endpoints under `/p/<token>/…` (respond, question, email-pdf) — they are HTML form posts, not JSON"; add "No in-app question threads or producer question inbox, and no polls, in the portal (deliberate v1 scope — see the portal spec)".

- [ ] **Step 2: Restart the web container and run the whole verification**

Run:
```bash
docker compose restart web
docker compose exec -T web uv run python scripts/verify_portal.py
docker compose exec -T web uv run flask db current
```
Expected: `N/N passed` with exit 0 (N ≈ 60); `flask db current` shows `f7a8b9c0d1e2 (head)`.

- [ ] **Step 3: Visual check at phone and wide widths**

Run `docker compose exec -T web uv run python scripts/verify_portal.py --keep`, then print the token of the keynote guest on the "verify-portal Alpha" episode (she has accepted Alpha, is pending on Beta, and has a cancelled Delta):

```bash
docker compose exec -T web uv run python -c "
from app import create_app
from app.models import Podcast, ParticipantRole
app = create_app()
with app.app_context():
    ep = Podcast.query.filter_by(title='verify-portal Alpha').first()
    print(ep.participant_slots.filter_by(participant_role=ParticipantRole.KEYNOTE_SPEAKER).first().participant.portal_token)
"
```

and open `http://localhost:27800/p/<token>` in a browser (use the `claude-in-chrome` skill if available; otherwise ask the user to do this in DevTools). Check, at **375×812**: the list is one column; tapping a row opens the detail as its own screen with a working "All episodes" back link; all buttons ≥ 48px tall; no horizontal scroll; the textarea doesn't zoom on focus. At **1280×800**: list left / detail right, first episode pre-selected, no back link. Try both light and dark mode, and browser Print preview on an accepted episode (list, buttons and back link hidden; text black on white). Then clean up: `docker compose exec -T web uv run python scripts/verify_portal.py` (no `--keep`) — it deletes leftovers first.

Expected: layouts as described. Fix any deviation in `portal/base.html` CSS and re-run Step 2 before continuing.

- [ ] **Step 4: Final tree check and commit**

Run: `git status --short`
Expected: only `CLAUDE.md` modified beyond the already-committed work, plus the pre-existing `M .env` and untracked `docs/` files (do **not** stage those; the two docs files created by this feature — the spec and this plan — are already committed or are committed here).

```bash
git add CLAUDE.md docs/superpowers/plans/2026-09-29-participant-portal.md
git commit -m "Document the participant portal" -m "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```
