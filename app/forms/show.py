from PIL import Image
from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed
from wtforms import StringField, TextAreaField, SelectField, BooleanField, SubmitField
from wtforms.validators import DataRequired, Optional, Length, Email, ValidationError, Regexp
from ..models import Show

MIN_COVER_PX = 1400
MAX_COVER_PX = 3000

ITUNES_CATEGORIES = [
    "Arts", "Business", "Comedy", "Education", "Fiction", "Government",
    "History", "Health & Fitness", "Kids & Family", "Leisure", "Music",
    "News", "Religion & Spirituality", "Science", "Society & Culture",
    "Sports", "Technology", "True Crime", "TV & Film",
]


class ShowForm(FlaskForm):
    title = StringField("Show Title", validators=[DataRequired(), Length(max=200)])
    feed_slug = StringField(
        "Feed Slug",
        validators=[
            DataRequired(),
            Length(max=100),
            Regexp(r"^[a-z0-9-]+$", message="Lowercase letters, numbers, and hyphens only."),
        ],
    )
    description = TextAreaField("Description", validators=[Optional()])
    author_name = StringField("Author / Publisher Name", validators=[DataRequired(), Length(max=200)])
    owner_email = StringField("Owner Email", validators=[DataRequired(), Email(), Length(max=200)])
    itunes_category = SelectField("Category", choices=[(c, c) for c in ITUNES_CATEGORIES])
    explicit = BooleanField("Contains Explicit Content")
    language = StringField("Language Code", default="en-us", validators=[DataRequired(), Length(max=10)])
    website_url = StringField("Website URL", validators=[Optional(), Length(max=500)])
    cover_image = FileField(
        "Cover Art (min 1400×1400px, JPG or PNG)",
        validators=[Optional(), FileAllowed(["jpg", "jpeg", "png"], "Images only.")],
    )
    submit = SubmitField("Save Show")

    def __init__(self, show=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._show = show

    def validate_feed_slug(self, field):
        query = Show.query.filter_by(feed_slug=field.data)
        if self._show:
            query = query.filter(Show.id != self._show.id)
        if query.first():
            raise ValidationError("That feed slug is already in use.")

    def validate_cover_image(self, field):
        if not field.data:
            return
        field.data.stream.seek(0)
        try:
            image = Image.open(field.data.stream)
            image.verify()
            field.data.stream.seek(0)
            image = Image.open(field.data.stream)
            width, height = image.size
            image_format = image.format
        except Exception:
            raise ValidationError("Could not read that image file.")
        finally:
            field.data.stream.seek(0)

        if image_format not in ("JPEG", "PNG"):
            raise ValidationError("Cover art must be a JPEG or PNG file.")
        if width != height:
            raise ValidationError(f"Cover art must be square (got {width}×{height}px).")
        if width < MIN_COVER_PX or width > MAX_COVER_PX:
            raise ValidationError(
                f"Cover art must be between {MIN_COVER_PX}×{MIN_COVER_PX} and "
                f"{MAX_COVER_PX}×{MAX_COVER_PX}px (got {width}×{width}px)."
            )
