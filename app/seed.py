import os
from .extensions import db
from .models import Role, User
from .models.role import PERMISSIONS


def run_seed():
    _seed_roles()
    _seed_admin()


def _seed_roles():
    default_roles = [
        {
            "name": "admin",
            "description": "Full system access",
            "permissions": ",".join(sorted(PERMISSIONS.keys())),
        },
        {
            "name": "producer",
            "description": "Creates and manages episodes and participants",
            "permissions": ",".join(sorted([
                "create_podcast", "edit_podcast", "delete_podcast",
                "manage_participants", "send_invitations",
                "manage_email_templates", "manage_shows", "distribute_podcast", "view_all",
            ])),
        },
        {
            "name": "host",
            "description": "Views and manages their own episodes",
            "permissions": ",".join(sorted([
                "create_podcast", "send_invitations",
            ])),
        },
        {
            "name": "viewer",
            "description": "Read-only access",
            "permissions": "view_all",
        },
    ]

    for rd in default_roles:
        role = Role.query.filter_by(name=rd["name"]).first()
        if not role:
            role = Role(name=rd["name"], description=rd["description"], permissions=rd["permissions"])
            db.session.add(role)
            print(f"  Created role: {rd['name']}")
        else:
            role.permissions = rd["permissions"]
            role.description = rd["description"]

    db.session.commit()


def _seed_admin():
    admin_role = Role.query.filter_by(name="admin").first()
    if not admin_role:
        return

    email = os.getenv("ADMIN_EMAIL", "admin@example.com")
    username = os.getenv("ADMIN_USERNAME", "admin")
    password = os.getenv("ADMIN_PASSWORD", "changeme123")

    if not User.query.filter_by(email=email).first():
        admin = User(username=username, email=email, role_id=admin_role.id, is_active=True)
        admin.set_password(password)
        db.session.add(admin)
        db.session.commit()
        print(f"  Created admin user: {email}")
    else:
        print(f"  Admin user already exists: {email}")
