import secrets
from datetime import datetime, timezone
from ..extensions import db


class CalendarSettings(db.Model):
    __tablename__ = "calendar_settings"

    id = db.Column(db.Integer, primary_key=True)
    feed_token = db.Column(db.String(64), unique=True, nullable=False)
    updated_at = db.Column(db.DateTime)
    updated_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)

    updated_by = db.relationship("User", foreign_keys=[updated_by_id])

    @classmethod
    def get_or_create(cls):
        settings = cls.query.first()
        if settings is None:
            settings = cls(feed_token=secrets.token_urlsafe(32))
            db.session.add(settings)
            db.session.commit()
        return settings

    def regenerate_token(self, user):
        self.feed_token = secrets.token_urlsafe(32)
        self.updated_at = datetime.now(timezone.utc)
        self.updated_by_id = user.id
        db.session.commit()

    def __repr__(self):
        return f"<CalendarSettings id={self.id}>"
