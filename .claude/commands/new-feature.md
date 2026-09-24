Checklist for adding a new feature to PodScheduler. Work through each step that applies.

## 1 — Model (if adding/changing data)
- Edit `app/models/<model>.py`
- Export from `app/models/__init__.py`
- Run `/new-migration` to create + apply the migration

## 2 — Permissions (if the feature needs access control)
- Add the new permission key+description to `PERMISSIONS` dict in `app/models/role.py`
- Update `app/seed.py` to assign it to the appropriate default roles (admin always gets all)
- The next `flask seed` run will update existing roles in the database

## 3 — Forms (if the feature has a form)
- Create `app/forms/<name>.py` using Flask-WTF / WTForms
- Export from `app/forms/__init__.py`
- Always include `{{ form.hidden_tag() }}` in the template for CSRF

## 4 — Routes (blueprint)
- Create `app/routes/<name>.py`
- Register in `app/__init__.py`:
  ```python
  from .routes.<name> import <name>_bp
  app.register_blueprint(<name>_bp, url_prefix="/<name>")
  ```
- Use `@login_required` on all routes that need auth
- Use `@permission_required("perm_name")` for permission-gated routes

## 5 — Templates (mobile-first)
- Create `app/templates/<section>/<page>.html`
- Always extend `base.html`
- Always override `{% block page_title %}` and `{% block header_back %}`
- Content goes inside `<div class="page-pad">` for side padding
- **List pages**: use `.row-card` elements — no tables
- **Form pages**: stacked inputs, `btn-accent btn-full` submit, full-width cancel button
- **Empty state**: use `.empty-state` div with icon + message + optional CTA button
- **Create action**: small `+` icon button in `{% block topbar_actions %}` or a `.fab`
- Test at 375px width before calling it done

## 6 — Push
```bash
git add <specific files>
git commit -m "feat: description of what was added"
git push -u origin claude/podscheduler-program-1oag4o
```
