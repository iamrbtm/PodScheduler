from flask import Blueprint, render_template, redirect, url_for, flash
from ..extensions import db
from ..models.podcast_guest import PodcastGuest, InvitationStatus

invitations_bp = Blueprint("invitations", __name__)


@invitations_bp.route("/<token>/<action>")
def respond(token, action):
    pg = PodcastGuest.query.filter_by(invitation_token=token).first_or_404()

    if pg.invitation_status != InvitationStatus.PENDING:
        already = pg.invitation_status.value
        return render_template(
            "invitations/already_responded.html",
            pg=pg,
            already=already,
        )

    if action == "accept":
        pg.accept()
        db.session.commit()
        return render_template("invitations/accepted.html", pg=pg)
    elif action == "decline":
        pg.decline()
        db.session.commit()
        return render_template("invitations/declined.html", pg=pg)
    else:
        flash("Invalid action.", "danger")
        return redirect(url_for("main.index"))
