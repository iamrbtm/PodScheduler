import enum
from datetime import datetime, timezone
from ..extensions import db


class SubmissionStatus(str, enum.Enum):
    NOT_SUBMITTED = "not_submitted"
    SUBMITTED = "submitted"
    LIVE = "live"


class DirectorySubmission(db.Model):
    __tablename__ = "directory_submissions"

    id = db.Column(db.Integer, primary_key=True)
    show_id = db.Column(db.Integer, db.ForeignKey("shows.id"), nullable=False)
    directory_key = db.Column(db.String(50), nullable=False)
    status = db.Column(
        db.Enum(SubmissionStatus, values_callable=lambda x: [e.value for e in x]),
        default=SubmissionStatus.NOT_SUBMITTED,
        nullable=False,
    )
    submitted_at = db.Column(db.DateTime)
    updated_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)

    show = db.relationship("Show", backref=db.backref("directory_submissions", cascade="all, delete-orphan"))

    __table_args__ = (db.UniqueConstraint("show_id", "directory_key", name="uq_directory_submission_show_key"),)

    def mark(self, status):
        self.status = status
        self.submitted_at = datetime.now(timezone.utc) if status != SubmissionStatus.NOT_SUBMITTED else None
