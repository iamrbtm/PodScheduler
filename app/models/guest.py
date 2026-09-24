from datetime import datetime, timezone
from ..extensions import db


class Guest(db.Model):
    __tablename__ = "guests"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), nullable=False, unique=True, index=True)
    bio = db.Column(db.Text)
    phone = db.Column(db.String(30))
    company = db.Column(db.String(120))
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    created_by_id = db.Column(db.Integer, db.ForeignKey("users.id"))

    invitations = db.relationship(
        "PodcastGuest", backref="guest", lazy="dynamic", cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<Guest {self.name}>"
