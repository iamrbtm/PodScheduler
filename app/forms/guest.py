from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, SelectField, SubmitField
from wtforms.validators import DataRequired, Email, Optional, Length, ValidationError
from ..models import Guest


class GuestForm(FlaskForm):
    name = StringField("Full Name", validators=[DataRequired(), Length(max=120)])
    email = StringField("Email", validators=[DataRequired(), Email(), Length(max=120)])
    phone = StringField("Phone", validators=[Optional(), Length(max=30)])
    company = StringField("Company / Organization", validators=[Optional(), Length(max=120)])
    bio = TextAreaField("Bio", validators=[Optional()])
    submit = SubmitField("Save Guest")

    def __init__(self, guest=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._guest = guest

    def validate_email(self, field):
        query = Guest.query.filter_by(email=field.data.lower())
        if self._guest:
            query = query.filter(Guest.id != self._guest.id)
        if query.first():
            raise ValidationError("A guest with this email already exists.")


class InviteGuestForm(FlaskForm):
    guest_id = SelectField("Guest", coerce=int, validators=[DataRequired()])
    message = TextAreaField("Personal Message (optional)", validators=[Optional()])
    submit = SubmitField("Send Invitation")
