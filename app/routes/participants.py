from flask import Blueprint, render_template, redirect, url_for, flash
from flask_login import login_required, current_user
from ..extensions import db
from ..models import Participant
from ..forms import ParticipantForm
from ..decorators import permission_required

participants_bp = Blueprint("participants", __name__)


@participants_bp.route("/")
@login_required
def index():
    participants = Participant.query.order_by(Participant.name).all()
    return render_template("participants/index.html", participants=participants)


@participants_bp.route("/new", methods=["GET", "POST"])
@login_required
@permission_required("manage_participants")
def create():
    form = ParticipantForm()
    if form.validate_on_submit():
        participant = Participant(
            name=form.name.data,
            email=form.email.data.lower(),
            phone=form.phone.data,
            company=form.company.data,
            bio=form.bio.data,
            created_by_id=current_user.id,
        )
        db.session.add(participant)
        db.session.commit()
        flash(f"Participant '{participant.name}' added.", "success")
        return redirect(url_for("participants.index"))
    return render_template("participants/form.html", form=form, participant=None)


@participants_bp.route("/<int:participant_id>/edit", methods=["GET", "POST"])
@login_required
@permission_required("manage_participants")
def edit(participant_id):
    participant = Participant.query.get_or_404(participant_id)
    form = ParticipantForm(participant=participant, obj=participant)
    if form.validate_on_submit():
        participant.name = form.name.data
        participant.email = form.email.data.lower()
        participant.phone = form.phone.data
        participant.company = form.company.data
        participant.bio = form.bio.data
        db.session.commit()
        flash(f"Participant '{participant.name}' updated.", "success")
        return redirect(url_for("participants.index"))
    return render_template("participants/form.html", form=form, participant=participant)


@participants_bp.route("/<int:participant_id>/delete", methods=["POST"])
@login_required
@permission_required("manage_participants")
def delete(participant_id):
    participant = Participant.query.get_or_404(participant_id)
    name = participant.name
    db.session.delete(participant)
    db.session.commit()
    flash(f"Participant '{name}' deleted.", "success")
    return redirect(url_for("participants.index"))
