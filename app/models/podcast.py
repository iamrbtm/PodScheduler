import enum
from datetime import datetime, timezone
from ..extensions import db


class PodcastStatus(str, enum.Enum):
    DRAFT = "draft"
    SCHEDULED = "scheduled"
    RECORDED = "recorded"
    READY_TO_DISTRIBUTE = "ready_to_distribute"
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
    producer_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    created_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    show_id = db.Column(db.Integer, db.ForeignKey("shows.id"), nullable=True)

    audio_object_key = db.Column(db.String(500))
    audio_url = db.Column(db.String(500))
    audio_duration_seconds = db.Column(db.Integer)
    audio_file_size = db.Column(db.Integer)
    episode_number = db.Column(db.Integer)
    season_number = db.Column(db.Integer)
    published_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    participant_slots = db.relationship(
        "PodcastParticipant", backref="podcast", lazy="dynamic", cascade="all, delete-orphan"
    )

    @property
    def keynote_slots(self):
        from .podcast_participant import ParticipantRole
        return [p for p in self.participant_slots if p.participant_role == ParticipantRole.KEYNOTE_SPEAKER]

    @property
    def roundtable_slots(self):
        from .podcast_participant import ParticipantRole
        return [p for p in self.participant_slots if p.participant_role == ParticipantRole.ROUNDTABLE]

    @property
    def accepted_participants(self):
        from .podcast_participant import InvitationStatus
        return [pp.participant for pp in self.participant_slots if pp.invitation_status == InvitationStatus.ACCEPTED]

    @property
    def participant_count(self):
        return self.participant_slots.count()

    @property
    def has_audio(self):
        return bool(self.audio_url)

    @property
    def audio_duration_display(self):
        if not self.audio_duration_seconds:
            return None
        minutes, seconds = divmod(self.audio_duration_seconds, 60)
        return f"{minutes}:{seconds:02d}"

    def __repr__(self):
        return f"<Podcast {self.title}>"
