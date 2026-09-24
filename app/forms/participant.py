from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, SelectField, SubmitField
from wtforms.validators import DataRequired, Email, Optional, Length, ValidationError
from ..models import Participant


class ParticipantForm(FlaskForm):
    name = StringField("Full Name", validators=[DataRequired(), Length(max=120)])
    email = StringField("Email", validators=[DataRequired(), Email(), Length(max=120)])
    phone = StringField("Phone", validators=[Optional(), Length(max=30)])
    company = StringField("Company / Organization", validators=[Optional(), Length(max=120)])
    bio = TextAreaField("Bio", validators=[Optional()])
    submit = SubmitField("Save Participant")

    def __init__(self, participant=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._participant = participant

    def validate_email(self, field):
        query = Participant.query.filter_by(email=field.data.lower())
        if self._participant:
            query = query.filter(Participant.id != self._participant.id)
        if query.first():
            raise ValidationError("A participant with this email already exists.")


class InviteParticipantForm(FlaskForm):
    participant_id = SelectField("Participant", coerce=int, validators=[DataRequired()])
    participant_role = SelectField(
        "Role on this Episode",
        choices=[
            ("keynote_speaker", "Keynote Speaker"),
            ("roundtable", "Round Table Participant"),
        ],
        validators=[DataRequired()],
    )
    email_template_id = SelectField("Email Template", coerce=int, validators=[Optional()])
    message = TextAreaField("Personal Message (optional)", validators=[Optional()])
    submit = SubmitField("Send Invitation")
