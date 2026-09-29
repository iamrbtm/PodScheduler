from datetime import datetime

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for

from ..extensions import db
from ..models import InvitationStatus, Participant, PodcastParticipant, PodcastStatus

portal_bp = Blueprint("portal", __name__)

_STATUS_ORDER = {
    InvitationStatus.PENDING: 0,
    InvitationStatus.ACCEPTED: 1,
    InvitationStatus.DECLINED: 2,
}


def _participant_or_404(token):
    return Participant.query.filter_by(portal_token=token).first_or_404()


def _slot_or_404(participant, pp_id):
    """A slot the guest was actually invited to. Anything else — someone else's
    slot, or one a producer added but never sent — is a 404."""
    pp = PodcastParticipant.query.filter_by(id=pp_id, participant_id=participant.id).first_or_404()
    if pp.invited_at is None:
        abort(404)
    return pp


def _visible_slots(participant):
    slots = participant.episode_slots.filter(PodcastParticipant.invited_at.isnot(None)).all()
    return sorted(
        slots,
        key=lambda s: (
            _STATUS_ORDER[s.invitation_status],
            s.podcast.recording_date is None,
            s.podcast.recording_date or datetime.max,
            s.podcast.title.lower(),
        ),
    )


def _render(participant, token, view, selected):
    others = []
    if selected is not None and selected.invitation_status == InvitationStatus.ACCEPTED:
        others = selected.other_confirmed_guests()
    return render_template(
        "portal/page.html",
        participant=participant,
        token=token,
        slots=_visible_slots(participant),
        selected=selected,
        view=view,
        others=others,
    )


@portal_bp.route("/<token>")
def dashboard(token):
    participant = _participant_or_404(token)
    slots = _visible_slots(participant)
    return _render(participant, token, "list", slots[0] if slots else None)


@portal_bp.route("/<token>/episodes/<int:pp_id>")
def episode(token, pp_id):
    participant = _participant_or_404(token)
    return _render(participant, token, "detail", _slot_or_404(participant, pp_id))


@portal_bp.route("/<token>/episodes/<int:pp_id>/respond", methods=["POST"])
def respond(token, pp_id):
    participant = _participant_or_404(token)
    pp = _slot_or_404(participant, pp_id)
    action = request.form.get("action")

    if pp.podcast.status == PodcastStatus.CANCELLED:
        flash("This episode was cancelled, so it can't be changed.", "warning")
    elif action == "accept":
        pp.accept()
        db.session.commit()
        flash("You're confirmed — thank you!", "success")
    elif action == "decline":
        pp.decline()
        db.session.commit()
        flash("You've declined this invitation. You can change your mind here any time.", "info")
    else:
        flash("Invalid action.", "danger")
    return redirect(url_for("portal.episode", token=token, pp_id=pp.id))
