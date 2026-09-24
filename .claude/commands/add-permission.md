Add a new permission to the system.

## Steps

1. **Define the permission** in `app/models/role.py`, in the `PERMISSIONS` dict:
   ```python
   "your_permission_key": "Human-readable description of what it allows",
   ```

2. **Assign it to roles** in `app/seed.py`. Find the role(s) that should have it and add the key to their permissions list. The `admin` role automatically gets all permissions (it uses `",".join(sorted(PERMISSIONS.keys()))`).

3. **Use it in routes** with the decorator:
   ```python
   from ..decorators import permission_required

   @bp.route("/something")
   @login_required
   @permission_required("your_permission_key")
   def your_view():
       ...
   ```

4. **Use it in templates**:
   ```html
   {% if current_user.is_admin() or current_user.has_permission('your_permission_key') %}
   <!-- show the button / link -->
   {% endif %}
   ```

5. **Re-seed** to update existing roles in the database:
   ```bash
   docker compose exec web uv run flask seed
   ```
   The seed is idempotent — it updates permissions on existing roles without touching user data.

## Permissions already in the system

| Key | Description |
|-----|-------------|
| manage_users | Create, edit, delete users |
| manage_roles | Create, edit, delete roles |
| create_podcast | Create new episodes |
| edit_podcast | Edit any episode |
| delete_podcast | Delete any episode |
| manage_participants | Add, edit, remove participants |
| send_invitations | Send participant invitations |
| manage_email_templates | Create and edit email templates |
| view_all | View all episodes and participants |
