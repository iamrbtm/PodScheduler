from datetime import datetime, timezone
from ..extensions import db


class MailSettings(db.Model):
    __tablename__ = "mail_settings"

    id = db.Column(db.Integer, primary_key=True)
    mail_server = db.Column(db.String(200), nullable=False, default="localhost")
    mail_port = db.Column(db.Integer, nullable=False, default=25)
    mail_use_tls = db.Column(db.Boolean, default=False)
    mail_use_ssl = db.Column(db.Boolean, default=False)
    mail_username = db.Column(db.String(200))
    mail_password = db.Column(db.String(500))
    mail_default_sender = db.Column(db.String(200))
    mail_suppress_send = db.Column(db.Boolean, default=False)
    updated_at = db.Column(db.DateTime)
    updated_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)

    updated_by = db.relationship("User", foreign_keys=[updated_by_id])
