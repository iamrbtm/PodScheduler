from flask import Blueprint, redirect, url_for, flash
from ..extensions import db
from ..models.podcast import PodcastStatus
from ..models.podcast_participant import PodcastParticipant, InvitationStatus

invitations_bp = Blueprint("invitations", __name__)


@invitations_bp.route("/<token>/<action>")
def respond(token, action):
    pp = PodcastParticipant.query.filter_by(invitation_token=token).first_or_404()

    if action not in ("accept", "decline"):
        flash("Invalid action.", "danger")
        return redirect(url_for("main.index"))

    if pp.podcast.status == PodcastStatus.CANCELLED:
        flash("This episode was cancelled.", "warning")
    elif pp.invitation_status != InvitationStatus.PENDING:
        flash(f"You already {pp.invitation_status.value} this invitation. You can change your answer below.", "info")
    elif action == "accept":
        pp.accept()
        flash("You're confirmed — thank you!", "success")
    else:
        pp.decline()
        flash("You've declined this invitation. You can change your mind here any time.", "info")

    portal_token = pp.participant.ensure_portal_token()
    db.session.commit()
    return redirect(url_for("portal.episode", token=portal_token, pp_id=pp.id))
