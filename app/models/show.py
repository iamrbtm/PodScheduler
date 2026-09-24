from datetime import datetime, timezone
from ..extensions import db


class Show(db.Model):
    __tablename__ = "shows"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    feed_slug = db.Column(db.String(100), unique=True, nullable=False)
    description = db.Column(db.Text)
    author_name = db.Column(db.String(200), nullable=False)
    owner_email = db.Column(db.String(200), nullable=False)
    itunes_category = db.Column(db.String(100), nullable=False, default="Technology")
    explicit = db.Column(db.Boolean, default=False, nullable=False)
    language = db.Column(db.String(10), nullable=False, default="en-us")
    website_url = db.Column(db.String(500))
    cover_image_object_key = db.Column(db.String(500))
    cover_image_url = db.Column(db.String(500))
    created_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    episodes = db.relationship("Podcast", backref="show", lazy="dynamic")

    @property
    def is_feed_ready(self):
        return bool(self.title and self.author_name and self.owner_email and self.cover_image_url)

    def __repr__(self):
        return f"<Show {self.title}>"
