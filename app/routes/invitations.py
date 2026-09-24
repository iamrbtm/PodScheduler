from flask import Blueprint, render_template, redirect, url_for, flash
from ..extensions import db
from ..models.podcast_participant import PodcastParticipant, InvitationStatus

invitations_bp = Blueprint("invitations", __name__)


@invitations_bp.route("/<token>/<action>")
def respond(token, action):
    pp = PodcastParticipant.query.filter_by(invitation_token=token).first_or_404()

    if pp.invitation_status != InvitationStatus.PENDING:
        return render_template(
            "invitations/already_responded.html",
            pg=pp,
            already=pp.invitation_status.value,
        )

    if action == "accept":
        pp.accept()
        db.session.commit()
        return render_template("invitations/accepted.html", pg=pp)
    elif action == "decline":
        pp.decline()
        db.session.commit()
        return render_template("invitations/declined.html", pg=pp)
    else:
        flash("Invalid action.", "danger")
        return redirect(url_for("main.index"))
