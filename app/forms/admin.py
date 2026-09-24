from flask_wtf import FlaskForm
from wtforms import StringField, SelectField, BooleanField, PasswordField, TextAreaField, SubmitField
from wtforms.validators import DataRequired, Email, Optional, Length, ValidationError
from ..models import User


class EditUserForm(FlaskForm):
    username = StringField("Username", validators=[DataRequired(), Length(3, 64)])
    email = StringField("Email", validators=[DataRequired(), Email(), Length(max=120)])
    role_id = SelectField("Role", coerce=int, validators=[DataRequired()])
    is_active = BooleanField("Active")
    new_password = PasswordField("New Password (leave blank to keep current)", validators=[Optional(), Length(min=8)])
    submit = SubmitField("Update User")

    def __init__(self, user=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._user = user

    def validate_username(self, field):
        query = User.query.filter_by(username=field.data)
        if self._user:
            query = query.filter(User.id != self._user.id)
        if query.first():
            raise ValidationError("Username already taken.")

    def validate_email(self, field):
        query = User.query.filter_by(email=field.data.lower())
        if self._user:
            query = query.filter(User.id != self._user.id)
        if query.first():
            raise ValidationError("Email already registered.")


class RoleForm(FlaskForm):
    name = StringField("Role Name", validators=[DataRequired(), Length(2, 64)])
    description = StringField("Description", validators=[Optional(), Length(max=255)])
    submit = SubmitField("Save Role")
