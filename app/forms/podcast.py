from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, SelectField, IntegerField, SubmitField
from wtforms.fields import DateTimeLocalField
from wtforms.validators import DataRequired, Optional, Length, NumberRange


class PodcastForm(FlaskForm):
    title = StringField("Title", validators=[DataRequired(), Length(max=200)])
    topic = StringField("Topic", validators=[Optional(), Length(max=200)])
    description = TextAreaField("Description", validators=[Optional()])
    notes = TextAreaField("Production Notes", validators=[Optional()])
    guest_prep_info = TextAreaField(
        "Guest Preparation Info", validators=[Optional(), Length(max=5000)]
    )
    recording_date = DateTimeLocalField(
        "Recording Date & Time", format="%Y-%m-%dT%H:%M", validators=[Optional()]
    )
    scheduled_date = DateTimeLocalField(
        "Release Date & Time (goes live)", format="%Y-%m-%dT%H:%M", validators=[Optional()]
    )
    duration_minutes = IntegerField(
        "Duration (minutes)", default=60, validators=[Optional(), NumberRange(min=1, max=600)]
    )
    host_id = SelectField("Host", coerce=int, validators=[DataRequired()])
    show_id = SelectField("Show", coerce=int, validators=[Optional()])
    status = SelectField(
        "Status",
        choices=[
            ("draft", "Draft"),
            ("scheduled", "Scheduled"),
            ("recorded", "Recorded"),
            ("ready_to_distribute", "Ready to Distribute"),
            ("published", "Published"),
            ("cancelled", "Cancelled"),
        ],
        default="draft",
    )
    submit = SubmitField("Save Podcast")
