from ..extensions import db


class Role(db.Model):
    __tablename__ = "roles"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), unique=True, nullable=False)
    description = db.Column(db.String(255))
    permissions = db.Column(db.Text, default="")

    users = db.relationship("User", backref="role", lazy="dynamic")

    def has_permission(self, perm):
        if not self.permissions:
            return False
        return perm in self.permissions.split(",")

    def add_permission(self, perm):
        perms = set(self.permissions.split(",")) if self.permissions else set()
        perms.discard("")
        perms.add(perm)
        self.permissions = ",".join(sorted(perms))

    def remove_permission(self, perm):
        perms = set(self.permissions.split(",")) if self.permissions else set()
        perms.discard(perm)
        self.permissions = ",".join(sorted(perms))

    def __repr__(self):
        return f"<Role {self.name}>"


PERMISSIONS = {
    "manage_users": "Create, edit, and delete users",
    "manage_roles": "Create, edit, and delete roles",
    "create_podcast": "Create new episodes",
    "edit_podcast": "Edit any episode",
    "delete_podcast": "Delete any episode",
    "manage_participants": "Add, edit, and remove participants",
    "send_invitations": "Send participant invitations",
    "manage_email_templates": "Create and edit email templates",
    "manage_shows": "Create and edit shows, and distribute episodes to directories",
    "view_all": "View all episodes and participants",
}
