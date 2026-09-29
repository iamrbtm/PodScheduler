from datetime import datetime, timezone
from ..extensions import db


class GuestQuestion(db.Model):
    __tablename__ = "guest_questions"

    id = db.Column(db.Integer, primary_key=True)
    podcast_participant_id = db.Column(
        db.Integer, db.ForeignKey("podcast_participants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    question = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    email_sent = db.Column(db.Boolean, nullable=False, default=False)

    podcast_participant = db.relationship(
        "PodcastParticipant",
        backref=db.backref("questions", lazy="dynamic", cascade="all, delete-orphan", passive_deletes=True),
    )
