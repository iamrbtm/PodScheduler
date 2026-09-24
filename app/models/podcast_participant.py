import enum
import secrets
from datetime import datetime, timezone
from ..extensions import db


class InvitationStatus(str, enum.Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    DECLINED = "declined"


class ParticipantRole(str, enum.Enum):
    KEYNOTE_SPEAKER = "keynote_speaker"
    ROUNDTABLE = "roundtable"


class PodcastParticipant(db.Model):
    __tablename__ = "podcast_participants"

    id = db.Column(db.Integer, primary_key=True)
    podcast_id = db.Column(db.Integer, db.ForeignKey("podcasts.id"), nullable=False)
    participant_id = db.Column(db.Integer, db.ForeignKey("participants.id"), nullable=False)
    participant_role = db.Column(
        db.Enum(ParticipantRole, values_callable=lambda x: [e.value for e in x]),
        default=ParticipantRole.ROUNDTABLE,
        nullable=False,
    )
    invitation_status = db.Column(
        db.Enum(InvitationStatus, values_callable=lambda x: [e.value for e in x]),
        default=InvitationStatus.PENDING,
        nullable=False,
    )
    invitation_token = db.Column(db.String(64), unique=True, index=True)
    email_template_id = db.Column(db.Integer, db.ForeignKey("email_templates.id"), nullable=True)
    guest_of = db.Column(db.String(200))
    message = db.Column(db.Text)
    invited_at = db.Column(db.DateTime)
    responded_at = db.Column(db.DateTime)

    __table_args__ = (
        db.UniqueConstraint("podcast_id", "participant_id", name="uq_podcast_participant"),
    )

    def generate_token(self):
        self.invitation_token = secrets.token_urlsafe(32)

    def mark_invited(self):
        if not self.invitation_token:
            self.generate_token()
        self.invited_at = datetime.now(timezone.utc)
        self.invitation_status = InvitationStatus.PENDING

    def accept(self):
        self.invitation_status = InvitationStatus.ACCEPTED
        self.responded_at = datetime.now(timezone.utc)

    def decline(self):
        self.invitation_status = InvitationStatus.DECLINED
        self.responded_at = datetime.now(timezone.utc)

    @property
    def role_display(self):
        return "Keynote Speaker" if self.participant_role == ParticipantRole.KEYNOTE_SPEAKER else "Round Table Participant"

    def __repr__(self):
        return f"<PodcastParticipant podcast={self.podcast_id} participant={self.participant_id} role={self.participant_role}>"
