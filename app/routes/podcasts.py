from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from ..extensions import db
from ..models import Podcast, PodcastStatus, User, Participant, PodcastParticipant, EmailTemplate
from ..models.podcast_participant import InvitationStatus, ParticipantRole
from ..forms import PodcastForm, InviteParticipantForm
from ..decorators import permission_required
from ..email import send_invitation_email

podcasts_bp = Blueprint("podcasts", __name__)


@podcasts_bp.route("/")
@login_required
def index():
    status_filter = request.args.get("status")
    query = Podcast.query

    if status_filter and status_filter in [s.value for s in PodcastStatus]:
        query = query.filter_by(status=PodcastStatus(status_filter))

    if not current_user.is_admin() and not current_user.has_permission("view_all"):
        query = query.filter(
            (Podcast.host_id == current_user.id) |
            (Podcast.created_by_id == current_user.id)
        )

    podcasts = query.order_by(Podcast.scheduled_date.desc().nullslast(), Podcast.created_at.desc()).all()
    return render_template(
        "podcasts/index.html",
        podcasts=podcasts,
        statuses=PodcastStatus,
        current_status=status_filter,
    )


@podcasts_bp.route("/new", methods=["GET", "POST"])
@login_required
@permission_required("create_podcast")
def create():
    form = PodcastForm()
    form.host_id.choices = [(u.id, u.username) for u in User.query.filter_by(is_active=True).order_by(User.username).all()]

    if form.validate_on_submit():
        podcast = Podcast(
            title=form.title.data,
            topic=form.topic.data,
            description=form.description.data,
            notes=form.notes.data,
            scheduled_date=form.scheduled_date.data,
            duration_minutes=form.duration_minutes.data,
            status=PodcastStatus(form.status.data),
            host_id=form.host_id.data,
            created_by_id=current_user.id,
        )
        db.session.add(podcast)
        db.session.commit()
        flash(f"Episode '{podcast.title}' created.", "success")
        return redirect(url_for("podcasts.detail", podcast_id=podcast.id))

    return render_template("podcasts/form.html", form=form, podcast=None)


@podcasts_bp.route("/<int:podcast_id>")
@login_required
def detail(podcast_id):
    podcast = Podcast.query.get_or_404(podcast_id)
    _check_access(podcast)

    invite_form = InviteParticipantForm()
    already_invited_ids = [pp.participant_id for pp in podcast.participant_slots]
    available = Participant.query.filter(Participant.id.notin_(already_invited_ids)).order_by(Participant.name).all()
    invite_form.participant_id.choices = [(p.id, f"{p.name} <{p.email}>") for p in available]

    templates = EmailTemplate.query.order_by(EmailTemplate.name).all()
    invite_form.email_template_id.choices = [(0, "— Default template —")] + [(t.id, t.name) for t in templates]

    return render_template(
        "podcasts/detail.html",
        podcast=podcast,
        invite_form=invite_form,
        InvitationStatus=InvitationStatus,
        ParticipantRole=ParticipantRole,
    )


@podcasts_bp.route("/<int:podcast_id>/edit", methods=["GET", "POST"])
@login_required
def edit(podcast_id):
    podcast = Podcast.query.get_or_404(podcast_id)
    _check_edit_access(podcast)

    form = PodcastForm(obj=podcast)
    form.host_id.choices = [(u.id, u.username) for u in User.query.filter_by(is_active=True).order_by(User.username).all()]
    if podcast.status:
        form.status.data = podcast.status.value if isinstance(podcast.status, PodcastStatus) else podcast.status

    if form.validate_on_submit():
        podcast.title = form.title.data
        podcast.topic = form.topic.data
        podcast.description = form.description.data
        podcast.notes = form.notes.data
        podcast.scheduled_date = form.scheduled_date.data
        podcast.duration_minutes = form.duration_minutes.data
        podcast.status = PodcastStatus(form.status.data)
        podcast.host_id = form.host_id.data
        db.session.commit()
        flash("Episode updated.", "success")
        return redirect(url_for("podcasts.detail", podcast_id=podcast.id))

    return render_template("podcasts/form.html", form=form, podcast=podcast)


@podcasts_bp.route("/<int:podcast_id>/delete", methods=["POST"])
@login_required
@permission_required("delete_podcast")
def delete(podcast_id):
    podcast = Podcast.query.get_or_404(podcast_id)
    title = podcast.title
    db.session.delete(podcast)
    db.session.commit()
    flash(f"Episode '{title}' deleted.", "success")
    return redirect(url_for("podcasts.index"))


@podcasts_bp.route("/<int:podcast_id>/invite", methods=["POST"])
@login_required
@permission_required("send_invitations")
def invite_participant(podcast_id):
    podcast = Podcast.query.get_or_404(podcast_id)
    _check_edit_access(podcast)

    invite_form = InviteParticipantForm()
    already_invited_ids = [pp.participant_id for pp in podcast.participant_slots]
    available = Participant.query.filter(Participant.id.notin_(already_invited_ids)).order_by(Participant.name).all()
    invite_form.participant_id.choices = [(p.id, f"{p.name} <{p.email}>") for p in available]
    templates = EmailTemplate.query.order_by(EmailTemplate.name).all()
    invite_form.email_template_id.choices = [(0, "— Default template —")] + [(t.id, t.name) for t in templates]

    if invite_form.validate_on_submit():
        template_id = invite_form.email_template_id.data or None
        pp = PodcastParticipant(
            podcast_id=podcast.id,
            participant_id=invite_form.participant_id.data,
            participant_role=ParticipantRole(invite_form.participant_role.data),
            email_template_id=template_id if template_id else None,
            message=invite_form.message.data,
        )
        pp.mark_invited()
        db.session.add(pp)
        db.session.flush()

        sent = send_invitation_email(pp)
        db.session.commit()

        if sent:
            flash(f"Invitation sent to {pp.participant.name}.", "success")
        else:
            flash("Participant added but email delivery failed. Check mail settings.", "warning")

    return redirect(url_for("podcasts.detail", podcast_id=podcast_id))


@podcasts_bp.route("/<int:podcast_id>/participants/<int:participant_id>/remove", methods=["POST"])
@login_required
def remove_participant(podcast_id, participant_id):
    podcast = Podcast.query.get_or_404(podcast_id)
    _check_edit_access(podcast)
    pp = PodcastParticipant.query.filter_by(podcast_id=podcast_id, participant_id=participant_id).first_or_404()
    db.session.delete(pp)
    db.session.commit()
    flash("Participant removed from episode.", "success")
    return redirect(url_for("podcasts.detail", podcast_id=podcast_id))


@podcasts_bp.route("/<int:podcast_id>/participants/<int:participant_id>/resend", methods=["POST"])
@login_required
@permission_required("send_invitations")
def resend_invitation(podcast_id, participant_id):
    pp = PodcastParticipant.query.filter_by(podcast_id=podcast_id, participant_id=participant_id).first_or_404()
    pp.mark_invited()
    db.session.flush()
    sent = send_invitation_email(pp)
    db.session.commit()
    if sent:
        flash(f"Invitation resent to {pp.participant.name}.", "success")
    else:
        flash("Email delivery failed. Check mail settings.", "warning")
    return redirect(url_for("podcasts.detail", podcast_id=podcast_id))


def _check_access(podcast):
    from flask import abort
    if current_user.is_admin() or current_user.has_permission("view_all"):
        return
    if podcast.host_id == current_user.id or podcast.created_by_id == current_user.id:
        return
    abort(403)


def _check_edit_access(podcast):
    from flask import abort
    if current_user.is_admin() or current_user.has_permission("edit_podcast"):
        return
    if podcast.host_id == current_user.id or podcast.created_by_id == current_user.id:
        return
    abort(403)
