# Participant portal — design spec

**Date:** 2026-09-29
**Status:** awaiting stakeholder review

## Purpose

Today a guest who clicks Accept/Decline in an invitation email lands on a
static confirmation page and has nowhere to go afterwards. Replace that with a
small dashboard the guest can return to: every episode they are invited to, the
details they need to prepare for an accepted one, and a way to print/email
those details or ask the host a question.

## Requirements (from stakeholder)

- Landing after email Accept/Decline is a dashboard, not a static page.
- Dashboard lists every episode the person is invited to. Selecting one shows
  its details (if accepted) or Accept/Decline options (if still pending).
- Print, and email a PDF of the episode details.
- Email a question to the host.
- Guest sees: recording + release date/time; title, topic, description, host;
  other guests' names and roles; show name / cover art; and "any information
  needed to prepare for the episode."
- Layout is not fixed; mobile-first per project rules.
- Polls are **not** in the first version.

## Decisions confirmed with stakeholder

1. **First version scope:** dashboard + accept/decline + details, print/PDF,
   email-a-question. Polls deferred.
2. **Email links:** Accept/Decline links in the invitation email keep their
   current one-click behavior (response is recorded on link open), then
   redirect to the dashboard on that episode. Known trade-off: an email
   scanner/link previewer that opens the link can respond on the guest's
   behalf. Mitigation: guests can change their answer from the dashboard.
3. **Access model:** one private link per *person* (`Participant.portal_token`),
   not per invitation.
4. **Visible info:** everything listed under Requirements, plus a new
   guest-facing preparation field. Internal `notes` (production notes) are
   never shown.

## Architecture

### Access

- `Participant.portal_token` — `secrets.token_urlsafe(32)`, unique, indexed,
  nullable in the schema (backfilled by the migration; generated on
  `Participant` creation going forward). Same pattern as
  `CalendarSettings.feed_token` / `PodcastParticipant.invitation_token`.
- No login. Possession of the link is the authorization; an unknown token is a
  404. Every portal query is scoped to the `Participant` that owns the token —
  a guest can only ever see or act on their own `PodcastParticipant` rows.
- Revocation: a "Regenerate portal link" action on the participant page
  (`manage_participants`) replaces the token; the old URL 404s immediately.
  The same page shows the current link with a copy button.
- The link travels in every email to that person via a new merge field
  `portal_url`, and in the built-in fallback invitation templates.

### Routes (new blueprint `app/routes/portal.py`, no login required)

| Route | Purpose |
|-------|---------|
| `GET /p/<token>` | Dashboard: list of the person's episodes |
| `GET /p/<token>/episodes/<pp_id>` | One episode (detail if accepted; accept/decline if pending; declined summary) |
| `POST /p/<token>/episodes/<pp_id>/respond` | Accept / decline / change answer (`action` form field) |
| `POST /p/<token>/episodes/<pp_id>/question` | Save + email a question to the host |
| `POST /p/<token>/episodes/<pp_id>/email-pdf` | Email the episode PDF to the guest's own address |

`<pp_id>` is the `PodcastParticipant.id`, always looked up with
`participant_id == token owner's id` (404 otherwise).

All POSTs are CSRF-protected (Flask-WTF), like the rest of the app. Everything
is server-rendered; **no new JSON endpoints** (per CLAUDE.md).

### Invitation email links

`invitations.respond` (`/invitations/<token>/<action>`) keeps recording the
response on open, then **redirects** to
`/p/<participant.portal_token>/episodes/<pp.id>` instead of rendering
`accepted.html` / `declined.html` / `already_responded.html`. Old links in
already-sent emails keep working. The three standalone templates become
unused and are deleted. Invalid `action` behaves as today.

### Layout (mobile-first)

- **Phone (default):** two screens. Dashboard = header with the guest's name
  and a list of `.row-card` rows (episode title, recording date/time, status
  badge). Tapping a row opens the episode screen with a back button
  (`header_back` → dashboard). Pending episodes sort first.
- **Wide screens (≥ 992px):** split view — list on the left, selected episode
  on the right; the dashboard URL auto-selects the first pending (else next
  upcoming) episode. Achieved with CSS only; both layouts are the same
  server-rendered pages.
- Standalone pages (no app shell, no bottom nav, no login), using the same
  `--ps-*` theme tokens as the existing invitation pages.
- Touch rules apply: 48px targets, 16px inputs.

### Episode detail contents

- **Pending:** episode title/topic/host, recording date/time, and prominent
  Accept / Decline buttons.
- **Accepted:** title, topic, description, host name; recording and release
  date/time ("TBD" if unset); show name and cover art (if any); other guests'
  names and roles (never emails/phones); the guest's own role; the host's
  personal message to them (`PodcastParticipant.message`); the new
  **guest preparation info**; Print, "Email me a PDF", "Ask the host a
  question", and "Change my answer" (decline).
- **Declined:** short confirmation and a "Change my answer" (accept) button.
- **Cancelled episodes** stay listed with a Cancelled badge; no actions.
- Times are the naive wall-clock values used everywhere else in the app, shown
  without a timezone (existing limitation; out of scope here).

### Print / PDF

- Print: `@media print` stylesheet on the detail page hides buttons/list and
  prints the episode details cleanly. No server work.
- Email PDF: generated server-side with `reportlab` (pure Python, no system
  libraries needed in the Docker image; one new dependency in
  `pyproject.toml` / `uv.lock`). Contents mirror the accepted detail view.
  Sent as an attachment via `send_invitation_email`-style `_send` helper, and
  **only to the participant's own email** — never a caller-supplied address.
  Only available for accepted episodes.

### Questions

- New table `guest_questions`: `id`, `podcast_participant_id` (FK, cascade),
  `question` (text, max 2000 chars), `created_at`, `email_sent` (bool).
- Posting a question saves the row first, then emails `podcast.host.email`
  with `Reply-To` set to the guest's email, so replies go straight to the guest
  by email. If mail fails the row is kept with `email_sent = false` and the
  guest is told it was saved but could not be emailed — no silent loss.
- No in-app thread and no producer-side question inbox in v1 (YAGNI); the
  stored rows exist so one can be added later.
- Abuse surface: the form is token-gated and length-limited; no rate limiting
  in v1 (known limitation).

### Data changes (one migration)

- `participants.portal_token` — String(64), unique, indexed; migration
  backfills existing rows with generated tokens.
- `podcasts.guest_prep_info` — Text, nullable. New "Guest preparation info"
  textarea on the episode form (label + help text: "Shown to guests on their
  dashboard"), placed after Production Notes, which remains internal.
- `guest_questions` table as above.
- `downgrade()` drops them in reverse order (no enums involved).

### Other touched code

- `app/models/email_template.py`: add `portal_url` to `MERGE_FIELDS`;
  `app/email.py::_build_context` and the sample context in
  `app/routes/email_templates.py` gain `portal_url`.
- `email/invitation.html` / `.txt` fallback: add a "View all your episodes"
  link to the portal.
- `app/__init__.py`: register `portal_bp` at `/p`.
- Participant page: show/copy/regenerate portal link.
- `CLAUDE.md`: document the portal, the new fields/table, the `/p/` public
  routes, and update "does NOT have" (guest questions table; PDF generation;
  new public POST endpoints).

## Non-goals

Polls; real-time updates; guest accounts or passwords; in-app question
threads or a producer question inbox; per-guest timezone handling; PDF
customization; changing existing production-notes/calendar exposure rules
(`notes` and `topic` remain excluded from the calendar feed).

## Verification (project has no test suite)

Exercise against the running stack with the Flask test client and real
Postgres: token 404s and cross-participant isolation (guest A cannot open guest
B's `pp_id`), accept/decline/change-answer, redirect from old invitation links,
question saved when mail is suppressed and when it fails, PDF generates and is
addressed only to the participant, regenerate-token invalidates the old URL,
detail page never renders `notes`. Then check 375×812 and a wide viewport
visually.
