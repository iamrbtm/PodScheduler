import secrets
from datetime import datetime, timezone
from ..extensions import db


class Participant(db.Model):
    __tablename__ = "participants"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), nullable=False, unique=True, index=True)
    bio = db.Column(db.Text)
    phone = db.Column(db.String(30))
    company = db.Column(db.String(120))
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    created_by_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    portal_token = db.Column(
        db.String(64), unique=True, index=True, default=lambda: secrets.token_urlsafe(32)
    )

    episode_slots = db.relationship(
        "PodcastParticipant", backref="participant", lazy="dynamic", cascade="all, delete-orphan"
    )

    def ensure_portal_token(self):
        if not self.portal_token:
            self.portal_token = secrets.token_urlsafe(32)
        return self.portal_token

    def regenerate_portal_token(self):
        self.portal_token = secrets.token_urlsafe(32)

    def __repr__(self):
        return f"<Participant {self.name}>"
