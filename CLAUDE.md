# PodScheduler — Agent Context

## What this project is

A **mobile-first podcast scheduling platform** built for a small team. Producers schedule episodes, assign participants (guests), and send tokenized email invitations. Participants accept or decline via a link — no login required. All UI is designed for phones; tablet/desktop is acceptable but never the primary target.

---

## Tech stack

| Layer | Tool |
|-------|------|
| Framework | Flask 3.0 (app factory pattern, blueprints) |
| ORM | SQLAlchemy 3.1 via Flask-SQLAlchemy |
| Auth | Flask-Login (session cookies) |
| Forms | Flask-WTF / WTForms (CSRF on all POST) |
| Email | Flask-Mail (HTML + plain text) |
| Migrations | Flask-Migrate (Alembic) |
| DB | PostgreSQL 16 |
| Object storage | MinIO (S3-compatible, self-hosted) via `boto3` — episode audio + show cover art |
| Reverse proxy | Caddy — automatic HTTPS on `PUBLIC_DOMAIN`, routes `/media/*` to MinIO |
| Audio metadata | `mutagen` — reads episode duration on upload |
| Image validation | `Pillow` — validates cover art dimensions/format on upload |
| Package manager | **uv** — `pyproject.toml` + `uv.lock`, `[tool.uv] package = false` |
| Container | Docker Compose (`web` + `db` + `minio` + `minio-init` + `caddy`) |
| WSGI | gunicorn, 2 workers |

---

## Running the project

```bash
# Start everything
docker compose up --build

# App is at http://localhost:5000
# Default admin: admin@example.com / changeme123  (see .env)
```

The `entrypoint.sh` runs on start:
```
uv run flask db upgrade   →  runs all Alembic migrations
uv run flask seed         →  creates default roles + admin user if missing
uv run gunicorn ...       →  starts the app
```

**Important:** `docker-compose.yml` has `volumes: - .:/app` which mounts the host directory. This is fine for development but means the container sees local file changes immediately.

### Environment variables (`.env` file)

```
SECRET_KEY=<strong-random-key>
FLASK_ENV=development          # or production
DATABASE_URL=postgresql://podscheduler:podscheduler@db:5432/podscheduler
ADMIN_EMAIL=admin@example.com
ADMIN_USERNAME=admin
ADMIN_PASSWORD=changeme123

# Mail (optional — MAIL_SUPPRESS_SEND=True in development)
MAIL_SERVER=smtp.example.com
MAIL_PORT=587
MAIL_USE_TLS=true
MAIL_USERNAME=...
MAIL_PASSWORD=...
MAIL_DEFAULT_SENDER=noreply@podscheduler.local

# Object storage (MinIO) for episode audio + show cover art
MINIO_ROOT_USER=podscheduler
MINIO_ROOT_PASSWORD=<strong-random-string>
MINIO_BUCKET=podscheduler-media
MINIO_ENDPOINT=http://minio:9000   # internal Docker address, not public

# Public domain the RSS feed + media files are served from. Podcast
# directories fetch these from the open internet, so this must be a
# real domain with DNS pointed at the server — not localhost — before
# distributing anything for real.
PUBLIC_DOMAIN=localhost
PUBLIC_BASE_URL=http://localhost
```

---

## Project layout

```
PodScheduler/
├── app/
│   ├── __init__.py          # create_app() factory + CLI registration
│   ├── config.py            # DevelopmentConfig / ProductionConfig / TestingConfig
│   ├── extensions.py        # db, login_manager, mail, migrate singletons
│   ├── decorators.py        # @permission_required(perm)
│   ├── email.py             # send_invitation_email(podcast_participant)
│   ├── seed.py              # run_seed() — roles + admin user
│   ├── storage.py           # upload_file/upload_audio/upload_cover_image/delete_object (MinIO via boto3)
│   ├── audio.py             # get_duration_seconds() via mutagen
│   ├── directories.py       # DIRECTORIES — static list of podcast directories + submission links
│   ├── models/
│   │   ├── __init__.py
│   │   ├── role.py          # Role, PERMISSIONS dict
│   │   ├── user.py          # User (Flask-Login mixin)
│   │   ├── show.py          # Show — owns the RSS feed (one show, many episodes)
│   │   ├── podcast.py       # Podcast (= one episode), PodcastStatus enum
│   │   ├── participant.py   # Participant (the person, not tied to an episode)
│   │   ├── podcast_participant.py  # PodcastParticipant join table + enums
│   │   ├── directory_submission.py # DirectorySubmission, SubmissionStatus enum
│   │   └── email_template.py       # EmailTemplate, MERGE_FIELDS, render_blocks_*
│   ├── forms/
│   │   ├── __init__.py
│   │   ├── auth.py
│   │   ├── podcast.py
│   │   ├── participant.py
│   │   ├── show.py          # ShowForm — validates cover art dimensions via Pillow
│   │   └── role.py
│   ├── routes/
│   │   ├── main.py          # / and /dashboard
│   │   ├── auth.py          # /auth/*
│   │   ├── admin.py         # /admin/*
│   │   ├── podcasts.py      # /podcasts/* (incl. upload-audio, distribute)
│   │   ├── participants.py  # /participants/*
│   │   ├── invitations.py   # /invitations/<token>/accept|decline (no login)
│   │   ├── email_templates.py  # /admin/email-templates/*
│   │   ├── shows.py         # /admin/shows/* (CRUD + directory checklist)
│   │   └── feed.py          # /feed/<slug>.xml — public RSS feed, no login
│   └── templates/
│       ├── base.html        # App shell: fixed header + bottom nav
│       ├── main/
│       ├── auth/
│       ├── podcasts/
│       ├── participants/
│       ├── admin/
│       │   ├── email_templates/  # builder.html, index.html, preview.html
│       │   ├── shows/            # index.html, form.html, directories.html
│       │   └── ...
│       └── invitations/     # Standalone pages (no app shell, no login)
├── migrations/              # Alembic migration files
├── Dockerfile
├── docker-compose.yml       # web, db, minio, minio-init, caddy
├── Caddyfile                # reverse proxy: /media/* → minio, everything else → web
├── entrypoint.sh            # Must be chmod +x in git (git update-index --chmod=+x)
├── pyproject.toml
└── uv.lock
```

---

## Database models

### Role
- `id`, `name` (unique), `description`, `permissions` (comma-separated string)
- `has_permission(perm)`, `add_permission(perm)`, `remove_permission(perm)`

### User
- `id`, `username`, `email`, `password_hash`, `role_id` (FK), `is_active`, `last_login`, `created_at`
- `is_admin()` → True if `role.name == "admin"`
- `has_permission(perm)` → delegates to `role.has_permission(perm)`

### Show
- `id`, `title`, `feed_slug` (unique — used in the public feed URL), `description`, `author_name`, `owner_email`, `itunes_category`, `explicit`, `language`, `website_url`, `cover_image_object_key`, `cover_image_url`, `created_by_id` (FK User), `created_at`
- One `Show` owns one RSS feed and can have many `Podcast` (episode) rows
- Property: `is_feed_ready` → True once title/author_name/owner_email/cover_image_url are all set — required before an episode on this show can be distributed

### Podcast  *(= one episode)*
- `id`, `title`, `topic`, `description`, `notes`, `status` (PodcastStatus enum), `scheduled_date`, `duration_minutes`, `host_id` (FK User), `created_by_id` (FK User), `show_id` (FK Show, nullable), `created_at`
- Audio fields: `audio_object_key`, `audio_url`, `audio_duration_seconds`, `audio_file_size`, `episode_number`, `season_number`, `published_at`
- `PodcastStatus`: `draft`, `scheduled`, `recorded`, `ready_to_distribute`, `published`, `cancelled`
- Properties: `keynote_slots`, `roundtable_slots`, `participant_count`, `has_audio`, `audio_duration_display`

### Participant
- `id`, `name`, `email`, `phone`, `company`, `bio`, `created_at`, `created_by_id` (FK User)
- Relationship: `episode_slots` → list of `PodcastParticipant` rows
- The **same person** can be keynote on one episode and roundtable on another

### PodcastParticipant  *(join table)*
- `id`, `podcast_id` (FK), `participant_id` (FK), `participant_role` (enum), `invitation_status` (enum)
- `invitation_token` (unique, urlsafe 32-byte secret), `email_template_id` (FK, nullable)
- `message` (personal note), `invited_at`, `responded_at`
- Unique constraint: `(podcast_id, participant_id)` — one slot per person per episode
- `ParticipantRole`: `keynote_speaker`, `roundtable`
- `InvitationStatus`: `pending`, `accepted`, `declined`
- Methods: `generate_token()`, `mark_invited()`, `accept()`, `decline()`
- Property: `role_display` → human-readable string

### EmailTemplate
- `id`, `name`, `subject`, `blocks_json` (JSON array), `html_body`, `text_body`, `created_by_id` (FK), `created_at`, `updated_at`
- `set_blocks(blocks)` — saves JSON and re-renders html_body + text_body
- `render(context) → (subject, html, text)` — replaces `{{field}}` merge fields

### DirectorySubmission
- `id`, `show_id` (FK Show), `directory_key` (matches a key in `app/directories.py::DIRECTORIES`), `status` (SubmissionStatus enum), `submitted_at`, `updated_by_id` (FK User)
- `SubmissionStatus`: `not_submitted`, `submitted`, `live`
- Unique constraint `(show_id, directory_key)` — one row per directory per show, created on first status update
- Method: `mark(status)` — sets status and `submitted_at` (or clears it back to `None` for `not_submitted`)

---

## Permissions

Defined in `app/models/role.py::PERMISSIONS`:

| Permission | Description |
|------------|-------------|
| `manage_users` | Create, edit, delete users |
| `manage_roles` | Create, edit, delete roles |
| `create_podcast` | Create new episodes |
| `edit_podcast` | Edit any episode |
| `delete_podcast` | Delete any episode |
| `manage_participants` | Add, edit, remove participants |
| `send_invitations` | Send participant invitations |
| `manage_email_templates` | Create and edit email templates |
| `manage_shows` | Create and edit shows (RSS feed metadata, cover art) |
| `distribute_podcast` | Publish an episode marked "Ready to Distribute" into its show's RSS feed |
| `view_all` | View all episodes and participants |

**Default roles seeded by `flask seed`:**
- `admin` — all permissions
- `producer` — create/edit/delete podcast, manage_participants, send_invitations, manage_email_templates, manage_shows, distribute_podcast, view_all
- `host` — create_podcast, send_invitations
- `viewer` — view_all

Use `@permission_required("perm_name")` decorator on routes. Check in templates with `current_user.has_permission('perm')` or `current_user.is_admin()`.

---

## Email invitation flow

1. Producer invites a participant from the episode detail page → bottom sheet form
2. `podcasts.invite_participant` creates a `PodcastParticipant` row and calls `send_invitation_email(pp)`
3. `email.py::send_invitation_email` builds a context dict from the `PodcastParticipant`, renders the chosen `EmailTemplate` (or falls back to Jinja2 templates), and sends via Flask-Mail
4. Participant clicks the link → `/invitations/<token>/accept` or `/invitations/<token>/decline`
5. `invitations.py` looks up the token, updates `invitation_status`, shows a standalone confirmation page (no login required)

**Merge fields** available in templates:
`participant_name`, `participant_first_name`, `participant_email`, `participant_role`,
`episode_title`, `episode_topic`, `episode_date`, `episode_time`, `episode_duration`,
`host_name`, `personal_message`, `accept_url`, `decline_url`

---

## Email template builder

- Route: `/admin/email-templates/new` and `/admin/email-templates/<id>/edit`
- Template: `app/templates/admin/email_templates/builder.html`
- Blocks (stored as JSON array in `blocks_json`):
  - `header` — big title with emoji icon
  - `text` — paragraph, supports `\n` newlines
  - `detail_box` — grey info box (date, time, host, role)
  - `button_row` — Accept + Decline buttons (uses `{{accept_url}}` / `{{decline_url}}`)
  - `divider` — horizontal rule
  - `spacer` — empty vertical space (`height` px)
  - `footer` — small grey footer text
- Saving: `POST /admin/email-templates/save` with JSON body `{id, name, subject, blocks[]}`
- `EmailTemplate.set_blocks()` renders HTML and plain text at save time, not at send time
- Merge fields are resolved at send time via `EmailTemplate.render(context)`

---

## Episode distribution (RSS feed → podcast directories)

**There is no API that pushes an episode to Apple/Spotify/Amazon/etc.** Podcast directories don't
offer one — they poll a show's public RSS feed on their own schedule after a one-time feed
submission. The "publish everywhere" feature is built around that reality, not around it:

1. A `Show` owns one RSS feed (`GET /feed/<show.feed_slug>.xml`, public, no login). It needs
   `title`, `author_name`, `owner_email`, and `cover_image_url` set before anything can be
   distributed (`Show.is_feed_ready`).
2. An episode (`Podcast`) is assigned to a `Show` via `show_id`, and gets audio uploaded via
   `podcasts.upload_audio_file` → `storage.upload_audio()` (MinIO) + `audio.get_duration_seconds()`
   (mutagen).
3. When status is set to `ready_to_distribute`, a **"Publish to All Directories"** button appears
   on the episode detail page. Confirming it (`podcasts.distribute`) checks audio + show
   completeness, then sets `status = published` and `published_at = now()`.
4. `published` episodes with audio appear in `feed.rss` automatically — this is the actual
   distribution mechanism. No further action is needed per episode.
5. Getting a show listed on each directory in the first place is a **one-time, per-show** setup
   step, not a per-episode one: `/admin/shows/<id>/directories` (`app/directories.py::DIRECTORIES`)
   lists every directory from the Buzzsprout roundup with its submission link (or a note that it
   auto-indexes from Apple's directory / your RSS feed with no action needed) and a status you tick
   off once. Do not add per-directory API integrations here — none of the majors (Apple, Spotify,
   Amazon) offer a public submission API; this checklist is the correct, honest surface for that
   step.
6. **Deploying this for real requires a public domain.** `PUBLIC_DOMAIN`/`PUBLIC_BASE_URL` in
   `.env` and Caddy in `docker-compose.yml` exist so the feed and audio files are reachable from
   the open internet — directories cannot crawl `localhost`.

---

## Mobile-first UI

**This is a phone app. Every decision must start from a 375px viewport.**

### App shell (base.html)

- Fixed top header: `56px`, back-button slot + title + action slot
- Fixed bottom nav: `64px`, 6 tabs (Home, Podcasts, People, Templates, Admin, Me)
- Content area: `padding-top: 68px; padding-bottom: 80px` (header + nav)
- Max-width: `520px`, centered — looks native on phone, fine on tablet
- Safe-area insets via `env(safe-area-inset-bottom)` for notched iPhones

### CSS design tokens (defined on `:root` in base.html)

```css
--ps-accent:   #7c5cfc   /* primary purple */
--ps-accent-dim: rgba(124,92,252,.18)
--ps-bg:       #0a0a16   /* page background */
--ps-surface:  #141428   /* card background */
--ps-surface2: #1c1c36   /* elevated surface (card header, inputs) */
--ps-border:   rgba(255,255,255,.08)
--ps-text:     #f0f0ff
--ps-text-muted: rgba(255,255,255,.45)
--ps-header-h: 56px
--ps-nav-h:    64px
```

### Key components (all in base.html)

| Class | Purpose |
|-------|---------|
| `.row-card` | Replaces table rows — icon + text + badge + chevron tap target |
| `.stat-pill` | Big number stat cards for dashboard |
| `.filter-bar` + `.filter-pill` | Horizontal-scroll pill filter row |
| `.section-title` | Small all-caps section label |
| `.empty-state` | Centered empty placeholder with icon |
| `.fab` | Floating action button (fixed, above bottom nav) |
| `.btn-accent` | Primary purple button |
| `.btn-full` | Full-width block button |
| `offcanvas.offcanvas-bottom` | Bottom sheet — used for invite form and block editor |

### Touch target rules

- Minimum tap target: **48px** — never use smaller buttons
- `font-size: 16px` on all inputs (prevents iOS auto-zoom)
- `inputmode="email"` / `inputmode="tel"` on relevant inputs
- `-webkit-tap-highlight-color: transparent` on all elements

### No tables

Replace every `<table>` with `.row-card` elements. Tables break on mobile. If you're tempted to use a table, use cards.

### Back navigation

Every sub-page must override `{% block header_back %}` with:
```html
{% block header_back %}
<a href="{{ url_for('some.index') }}" class="hdr-back"><i class="bi bi-chevron-left"></i></a>
{% endblock %}
```

### Bottom sheet pattern (offcanvas)

Use Bootstrap 5 offcanvas with class `offcanvas-bottom` for forms that appear over the current page (invite form, block editor, confirm dialogs). Always round the top corners:
```html
<div class="offcanvas offcanvas-bottom" id="mySheet" tabindex="-1">
```
CSS in base.html already sets `border-radius: 20px 20px 0 0`.

### Full-screen modal pattern (multi-select pickers)

For a picker where the user needs to scan/select from a long list (e.g. adding several
participants at once), use a Bootstrap `modal` with `modal-fullscreen` instead of a bottom sheet —
a bottom sheet's capped height leaves too little room to see many rows at once:
```html
<div class="modal" id="myPicker" tabindex="-1">
  <div class="modal-dialog modal-fullscreen">
    <div class="modal-content">
      <div class="modal-header">...<button data-bs-dismiss="modal">...</button></div>
      <div class="modal-body">
        <form id="myForm" class="d-flex flex-column h-100">
          <!-- search/filter fields here -->
          <div class="picker-list">...</div> <!-- flex:1, scrolls; see podcasts/detail.html -->
        </form>
      </div>
      <div class="modal-footer">
        <button type="submit" form="myForm" class="btn btn-accent btn-full">Add</button>
      </div>
    </div>
  </div>
</div>
```
Trigger with `data-bs-toggle="modal" data-bs-target="#myPicker"`. Put the submit button in
`modal-footer` using `form="myForm"` (HTML5 form association) so it stays pinned below the
scrolling list rather than requiring a scroll to reach it. CSS for `.modal-fullscreen` lives in
base.html; `.picker-list`/`.picker-item` are local to the template that uses them (see
`podcasts/detail.html`'s keynote/round-table pickers for a full example).

---

## Migrations

```bash
# Create a new migration (after changing models)
docker compose exec web uv run flask db migrate -m "description of change"

# Apply migrations
docker compose exec web uv run flask db upgrade

# Roll back one step
docker compose exec web uv run flask db downgrade
```

Migration files live in `migrations/versions/`. Always review the generated file before applying — Alembic sometimes misses column type changes or renames.

When renaming a column or table, write the migration **manually** rather than letting Alembic auto-detect, since it will generate a drop+add instead of a rename.

---

## Adding a new feature — checklist

1. **Model change?** → edit `app/models/`, update `app/models/__init__.py`, create a migration
2. **New route?** → create `app/routes/<name>.py` with a Blueprint, register in `app/__init__.py`
3. **New permission needed?** → add to `PERMISSIONS` dict in `app/models/role.py`, update `seed.py` to assign it to the right default roles
4. **New page?** → create template in `app/templates/`, always extend `base.html`, always override `page_title` block, use `.page-pad` div for content padding
5. **Form page?** → stacked inputs, full-width, `btn-accent btn-full` submit button, back button in header
6. **List page?** → `.row-card` elements, no tables, `.empty-state` for zero results, FAB or topbar `+` button for create
7. **Mobile test:** open in Chrome DevTools at 375×812 before calling done

---

## Git

Branch: `claude/podscheduler-program-1oag4o`
Remote: `https://github.com/iamrbtm/podscheduler`

```bash
git push -u origin claude/podscheduler-program-1oag4o
```

Commit message format:
```
Short imperative summary (50 chars max)

Longer explanation if needed.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01NtkwyGzAHoQyLgDNgCa4Tf
```

---

## Known sharp edges

- `entrypoint.sh` **must** have execute bit set in git: `git update-index --chmod=+x entrypoint.sh`. The Docker volume mount overrides the filesystem, so the chmod in the Dockerfile alone is not enough.
- `[tool.uv] package = false` in `pyproject.toml` is required — this is an app, not a library. Without it, uv tries to install it as a package and fails because there is no package directory.
- Jinja2 blocks are parsed statically, not conditionally. You cannot define `{% block content %}` inside both branches of an `{% if %}`. Use `{{ self.content() }}` in the else branch if you need the same block in both.
- The `MAIL_SUPPRESS_SEND = True` in `DevelopmentConfig` silently swallows emails. To test real email sending, use `ProductionConfig` or temporarily override in `.env` with `FLASK_ENV=production`.
- `PodcastParticipant` has a unique constraint `(podcast_id, participant_id)`. You cannot invite the same person to the same episode twice, but you can change their role.
- Postgres native enum columns (`PodcastStatus`, `SubmissionStatus`, etc.) need explicit handling in migrations: `op.drop_table()` does **not** drop the associated `CREATE TYPE` — you must call `sa.Enum(name='...').drop(op.get_bind(), checkfirst=True)` in `downgrade()` or the type collides on a later re-create. Adding a new value to an existing enum is a one-way `ALTER TYPE ... ADD VALUE` (see `9f1c2d3e4b5a`); Postgres cannot drop a single enum value, so those migrations' `downgrade()` is a no-op.
- `flask db migrate` autogeneration on this database currently re-detects unrelated drift left over from an earlier rename (`ix_guests_email`/`ix_podcast_guests_invitation_token` index names, `podcast_participants.participant_role` column type) on every run. Strip that noise out of the generated file by hand — don't let it ride along in an unrelated migration.
- MinIO/Caddy only work end-to-end when Docker actually has a Docker daemon available (a plain container with just the `docker` CLI, like some CI/sandbox environments, cannot run `docker compose up`). Validate model/route/migration logic against a real Postgres instance directly if that's the situation, and confirm the full stack once on an environment with a working daemon before treating it as deployed.
- MinIO images are pulled from `quay.io/minio/minio` and `quay.io/minio/mc`, **not** Docker Hub's `minio/minio`/`minio/mc` — MinIO locked those Docker Hub repos down in 2024, so pulling the Docker Hub names now fails with `pull access denied ... repository does not exist`. If a pinned `RELEASE.*` tag 404s on quay.io (tags aren't always mirrored 1:1), fall back to `quay.io/minio/minio:latest` / `quay.io/minio/mc:latest` rather than reaching for the Docker Hub name.

---

## What this project does NOT have (don't add without asking)

- No tests (yet)
- No API / JSON endpoints (except `email_templates.save`)
- No WebSockets or real-time updates
- No file uploads beyond episode audio (`storage.upload_audio`) and show cover art
  (`storage.upload_cover_image`) — both go to MinIO. Don't add general-purpose file upload without asking.
- No push-based directory integrations (YouTube Data API, etc.) — only the RSS feed + the manual
  submission checklist. This was an explicit scope decision (see the distribution section above),
  not an oversight — don't add one without asking, and check `app/directories.py` first if asked to.
- No calendar integration
- No multi-tenancy (single organization per deployment)
- No desktop-specific layouts — the mobile layout IS the layout
