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
| Package manager | **uv** — `pyproject.toml` + `uv.lock`, `[tool.uv] package = false` |
| Container | Docker Compose (`web` + `db`) |
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
│   ├── models/
│   │   ├── __init__.py
│   │   ├── role.py          # Role, PERMISSIONS dict
│   │   ├── user.py          # User (Flask-Login mixin)
│   │   ├── podcast.py       # Podcast, PodcastStatus enum
│   │   ├── participant.py   # Participant (the person, not tied to an episode)
│   │   ├── podcast_participant.py  # PodcastParticipant join table + enums
│   │   └── email_template.py       # EmailTemplate, MERGE_FIELDS, render_blocks_*
│   ├── forms/
│   │   ├── __init__.py
│   │   ├── auth.py
│   │   ├── podcast.py
│   │   ├── participant.py
│   │   └── role.py
│   ├── routes/
│   │   ├── main.py          # / and /dashboard
│   │   ├── auth.py          # /auth/*
│   │   ├── admin.py         # /admin/*
│   │   ├── podcasts.py      # /podcasts/*
│   │   ├── participants.py  # /participants/*
│   │   ├── invitations.py   # /invitations/<token>/accept|decline (no login)
│   │   └── email_templates.py  # /admin/email-templates/*
│   └── templates/
│       ├── base.html        # App shell: fixed header + bottom nav
│       ├── main/
│       ├── auth/
│       ├── podcasts/
│       ├── participants/
│       ├── admin/
│       │   ├── email_templates/  # builder.html, index.html, preview.html
│       │   └── ...
│       └── invitations/     # Standalone pages (no app shell, no login)
├── migrations/              # Alembic migration files
├── Dockerfile
├── docker-compose.yml
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

### Podcast
- `id`, `title`, `topic`, `description`, `notes`, `status` (PodcastStatus enum), `scheduled_date`, `duration_minutes`, `host_id` (FK User), `created_by_id` (FK User), `created_at`
- `PodcastStatus`: `draft`, `scheduled`, `recorded`, `published`, `cancelled`
- Properties: `keynote_slots`, `roundtable_slots`, `participant_count`

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
| `view_all` | View all episodes and participants |

**Default roles seeded by `flask seed`:**
- `admin` — all permissions
- `producer` — create/edit/delete podcast, manage_participants, send_invitations, manage_email_templates, view_all
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

---

## What this project does NOT have (don't add without asking)

- No tests (yet)
- No API / JSON endpoints (except `email_templates.save`)
- No WebSockets or real-time updates
- No file uploads
- No calendar integration
- No multi-tenancy (single organization per deployment)
- No desktop-specific layouts — the mobile layout IS the layout
