from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, SelectField, IntegerField, SubmitField
from wtforms.fields import DateTimeLocalField
from wtforms.validators import DataRequired, Optional, Length, NumberRange


class PodcastForm(FlaskForm):
    title = StringField("Title", validators=[DataRequired(), Length(max=200)])
    topic = StringField("Topic", validators=[Optional(), Length(max=200)])
    description = TextAreaField("Description", validators=[Optional()])
    notes = TextAreaField("Production Notes", validators=[Optional()])
    scheduled_date = DateTimeLocalField(
        "Scheduled Date & Time", format="%Y-%m-%dT%H:%M", validators=[Optional()]
    )
    duration_minutes = IntegerField(
        "Duration (minutes)", default=60, validators=[Optional(), NumberRange(min=1, max=600)]
    )
    host_id = SelectField("Host", coerce=int, validators=[DataRequired()])
    status = SelectField(
        "Status",
        choices=[
            ("draft", "Draft"),
            ("scheduled", "Scheduled"),
            ("recorded", "Recorded"),
            ("published", "Published"),
            ("cancelled", "Cancelled"),
        ],
        default="draft",
    )
    submit = SubmitField("Save Podcast")
