import enum
from datetime import datetime, timezone
from ..extensions import db


class PodcastStatus(str, enum.Enum):
    DRAFT = "draft"
    SCHEDULED = "scheduled"
    RECORDED = "recorded"
    PUBLISHED = "published"
    CANCELLED = "cancelled"


class Podcast(db.Model):
    __tablename__ = "podcasts"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    topic = db.Column(db.String(200))
    notes = db.Column(db.Text)
    scheduled_date = db.Column(db.DateTime)
    duration_minutes = db.Column(db.Integer, default=60)
    status = db.Column(
        db.Enum(PodcastStatus, values_callable=lambda x: [e.value for e in x]),
        default=PodcastStatus.DRAFT,
        nullable=False,
    )

    host_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    created_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    guest_slots = db.relationship(
        "PodcastGuest", backref="podcast", lazy="dynamic", cascade="all, delete-orphan"
    )

    @property
    def accepted_guests(self):
        from .podcast_guest import InvitationStatus
        return [
            pg.guest for pg in self.guest_slots
            if pg.invitation_status == InvitationStatus.ACCEPTED
        ]

    @property
    def pending_guests(self):
        from .podcast_guest import InvitationStatus
        return [
            pg.guest for pg in self.guest_slots
            if pg.invitation_status == InvitationStatus.PENDING
        ]

    @property
    def guest_count(self):
        return self.guest_slots.count()

    def __repr__(self):
        return f"<Podcast {self.title}>"
