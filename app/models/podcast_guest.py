import enum
import secrets
from datetime import datetime, timezone
from ..extensions import db


class InvitationStatus(str, enum.Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    DECLINED = "declined"


class PodcastGuest(db.Model):
    __tablename__ = "podcast_guests"

    id = db.Column(db.Integer, primary_key=True)
    podcast_id = db.Column(db.Integer, db.ForeignKey("podcasts.id"), nullable=False)
    guest_id = db.Column(db.Integer, db.ForeignKey("guests.id"), nullable=False)
    invitation_status = db.Column(
        db.Enum(InvitationStatus, values_callable=lambda x: [e.value for e in x]),
        default=InvitationStatus.PENDING,
        nullable=False,
    )
    invitation_token = db.Column(db.String(64), unique=True, index=True)
    message = db.Column(db.Text)
    invited_at = db.Column(db.DateTime)
    responded_at = db.Column(db.DateTime)

    __table_args__ = (
        db.UniqueConstraint("podcast_id", "guest_id", name="uq_podcast_guest"),
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

    def __repr__(self):
        return f"<PodcastGuest podcast={self.podcast_id} guest={self.guest_id} status={self.invitation_status}>"
