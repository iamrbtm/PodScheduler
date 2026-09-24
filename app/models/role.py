from ..extensions import db


class Role(db.Model):
    __tablename__ = "roles"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), unique=True, nullable=False)
    description = db.Column(db.String(255))

    # Permissions stored as comma-separated strings for simplicity
    # e.g. "manage_users,manage_roles,create_podcast,edit_podcast,delete_podcast,manage_guests,view_only"
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
    "create_podcast": "Create new podcasts",
    "edit_podcast": "Edit any podcast",
    "delete_podcast": "Delete any podcast",
    "manage_guests": "Add, edit, and remove guests",
    "send_invitations": "Send guest invitations",
    "view_all": "View all podcasts and guests",
}
