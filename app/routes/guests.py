from flask import Blueprint, render_template, redirect, url_for, flash
from flask_login import login_required, current_user
from ..extensions import db
from ..models import Guest
from ..forms import GuestForm
from ..decorators import permission_required

guests_bp = Blueprint("guests", __name__)


@guests_bp.route("/")
@login_required
def index():
    guests = Guest.query.order_by(Guest.name).all()
    return render_template("guests/index.html", guests=guests)


@guests_bp.route("/new", methods=["GET", "POST"])
@login_required
@permission_required("manage_guests")
def create():
    form = GuestForm()
    if form.validate_on_submit():
        guest = Guest(
            name=form.name.data,
            email=form.email.data.lower(),
            phone=form.phone.data,
            company=form.company.data,
            bio=form.bio.data,
            created_by_id=current_user.id,
        )
        db.session.add(guest)
        db.session.commit()
        flash(f"Guest '{guest.name}' added.", "success")
        return redirect(url_for("guests.index"))
    return render_template("guests/form.html", form=form, guest=None)


@guests_bp.route("/<int:guest_id>/edit", methods=["GET", "POST"])
@login_required
@permission_required("manage_guests")
def edit(guest_id):
    guest = Guest.query.get_or_404(guest_id)
    form = GuestForm(guest=guest, obj=guest)
    if form.validate_on_submit():
        guest.name = form.name.data
        guest.email = form.email.data.lower()
        guest.phone = form.phone.data
        guest.company = form.company.data
        guest.bio = form.bio.data
        db.session.commit()
        flash(f"Guest '{guest.name}' updated.", "success")
        return redirect(url_for("guests.index"))
    return render_template("guests/form.html", form=form, guest=guest)


@guests_bp.route("/<int:guest_id>/delete", methods=["POST"])
@login_required
@permission_required("manage_guests")
def delete(guest_id):
    guest = Guest.query.get_or_404(guest_id)
    name = guest.name
    db.session.delete(guest)
    db.session.commit()
    flash(f"Guest '{name}' deleted.", "success")
    return redirect(url_for("guests.index"))
