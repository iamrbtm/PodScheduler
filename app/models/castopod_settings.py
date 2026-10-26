from ..extensions import db


class CastopodSettings(db.Model):
    """Singleton row: connection to a self-hosted Castopod instance's REST API.

    Castopod's REST API is off by default; on the Castopod side it needs
    restapi.enabled=true plus restapi.basicAuth/-Username/-Password in its .env.
    """
    __tablename__ = "castopod_settings"

    id = db.Column(db.Integer, primary_key=True)
    base_url = db.Column(db.String(500))
    api_username = db.Column(db.String(200))
    api_password = db.Column(db.String(500))
    sync_enabled = db.Column(db.Boolean, default=False, nullable=False)
    updated_at = db.Column(db.DateTime)
    updated_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)

    updated_by = db.relationship("User", foreign_keys=[updated_by_id])

    @classmethod
    def get(cls):
        return cls.query.first()

    @property
    def is_configured(self):
        return bool(self.sync_enabled and self.base_url)

    def __repr__(self):
        return f"<CastopodSettings id={self.id}>"
