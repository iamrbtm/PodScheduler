from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from ..extensions import db
from ..models import Podcast, PodcastStatus, User, Participant, PodcastParticipant, Show
from ..models.podcast_participant import InvitationStatus, ParticipantRole
from ..forms import PodcastForm
from ..decorators import permission_required
from ..email import send_invitation_email
from ..storage import upload_audio, delete_object
from ..audio import get_duration_seconds

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
    form.show_id.choices = [(0, "— No show —")] + [(s.id, s.title) for s in Show.query.order_by(Show.title).all()]

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
            show_id=form.show_id.data or None,
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

    already_ids = {pp.participant_id for pp in podcast.participant_slots}
    available_participants = Participant.query.filter(
        Participant.id.notin_(already_ids)
    ).order_by(Participant.name).all()

    users = User.query.filter_by(is_active=True).order_by(User.username).all()

    return render_template(
        "podcasts/detail.html",
        podcast=podcast,
        available_participants=available_participants,
        users=users,
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
    form.show_id.choices = [(0, "— No show —")] + [(s.id, s.title) for s in Show.query.order_by(Show.title).all()]
    if podcast.status:
        form.status.data = podcast.status.value if isinstance(podcast.status, PodcastStatus) else podcast.status
    if request.method == "GET":
        form.show_id.data = podcast.show_id or 0

    if form.validate_on_submit():
        podcast.title = form.title.data
        podcast.topic = form.topic.data
        podcast.description = form.description.data
        podcast.notes = form.notes.data
        podcast.scheduled_date = form.scheduled_date.data
        podcast.duration_minutes = form.duration_minutes.data
        podcast.status = PodcastStatus(form.status.data)
        podcast.host_id = form.host_id.data
        podcast.show_id = form.show_id.data or None
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


@podcasts_bp.route("/<int:podcast_id>/add-participants", methods=["POST"])
@login_required
@permission_required("manage_participants")
def add_participants(podcast_id):
    from flask import abort
    podcast = Podcast.query.get_or_404(podcast_id)
    _check_edit_access(podcast)

    role_str = request.form.get("role", "")
    participant_ids = request.form.getlist("participant_ids")
    guest_of = request.form.get("guest_of", "").strip() or None

    try:
        role = ParticipantRole(role_str)
    except ValueError:
        flash("Invalid role.", "danger")
        return redirect(url_for("podcasts.detail", podcast_id=podcast_id))

    try:
        participant_ids = [int(pid) for pid in participant_ids]
    except (ValueError, TypeError):
        flash("Invalid participant selection.", "danger")
        return redirect(url_for("podcasts.detail", podcast_id=podcast_id))

    if not participant_ids:
        flash("Please select at least one participant.", "warning")
        return redirect(url_for("podcasts.detail", podcast_id=podcast_id))

    already_ids = {pp.participant_id for pp in podcast.participant_slots}
    added = 0
    for pid in participant_ids:
        if pid in already_ids:
            continue
        pp = PodcastParticipant(
            podcast_id=podcast.id,
            participant_id=pid,
            participant_role=role,
            guest_of=guest_of if role == ParticipantRole.KEYNOTE_SPEAKER else None,
        )
        db.session.add(pp)
        added += 1

    db.session.commit()
    if added:
        flash(f"Added {added} participant{'s' if added != 1 else ''}.", "success")
    else:
        flash("Those participants were already on this episode.", "info")
    return redirect(url_for("podcasts.detail", podcast_id=podcast_id))


@podcasts_bp.route("/<int:podcast_id>/distribute", methods=["POST"])
@login_required
@permission_required("distribute_podcast")
def distribute(podcast_id):
    from datetime import datetime, timezone

    podcast = Podcast.query.get_or_404(podcast_id)

    if podcast.status != PodcastStatus.READY_TO_DISTRIBUTE:
        flash("Episode must be marked 'Ready to Distribute' first.", "warning")
        return redirect(url_for("podcasts.detail", podcast_id=podcast_id))
    if not podcast.has_audio:
        flash("Upload episode audio before distributing.", "warning")
        return redirect(url_for("podcasts.detail", podcast_id=podcast_id))
    if not podcast.show or not podcast.show.is_feed_ready:
        flash("Assign this episode to a fully configured show first (title, author, owner email, cover art).", "warning")
        return redirect(url_for("podcasts.detail", podcast_id=podcast_id))

    podcast.status = PodcastStatus.PUBLISHED
    podcast.published_at = datetime.now(timezone.utc)
    db.session.commit()
    flash("Published! The episode is now live in your RSS feed — every directory subscribed to it will pick it up automatically.", "success")
    return redirect(url_for("podcasts.detail", podcast_id=podcast_id))


@podcasts_bp.route("/<int:podcast_id>/upload-audio", methods=["POST"])
@login_required
def upload_audio_file(podcast_id):
    podcast = Podcast.query.get_or_404(podcast_id)
    _check_edit_access(podcast)

    audio_file = request.files.get("audio_file")
    if not audio_file or not audio_file.filename:
        flash("Please choose an audio file.", "warning")
        return redirect(url_for("podcasts.detail", podcast_id=podcast_id))

    allowed_ext = {"mp3", "m4a", "wav", "aac", "ogg"}
    ext = audio_file.filename.rsplit(".", 1)[-1].lower() if "." in audio_file.filename else ""
    if ext not in allowed_ext:
        flash("Unsupported audio format. Use MP3, M4A, WAV, AAC, or OGG.", "danger")
        return redirect(url_for("podcasts.detail", podcast_id=podcast_id))

    duration = get_duration_seconds(audio_file)
    old_key = podcast.audio_object_key
    object_key, url, file_size = upload_audio(audio_file, podcast.id)

    podcast.audio_object_key = object_key
    podcast.audio_url = url
    podcast.audio_file_size = file_size
    podcast.audio_duration_seconds = duration
    db.session.commit()

    if old_key and old_key != object_key:
        delete_object(old_key)

    flash("Episode audio uploaded.", "success")
    return redirect(url_for("podcasts.detail", podcast_id=podcast_id))


@podcasts_bp.route("/<int:podcast_id>/set-crew", methods=["POST"])
@login_required
def set_crew(podcast_id):
    podcast = Podcast.query.get_or_404(podcast_id)
    _check_edit_access(podcast)

    host_id = request.form.get("host_id", type=int)
    producer_id = request.form.get("producer_id", type=int) or None

    if host_id:
        podcast.host_id = host_id
    podcast.producer_id = producer_id
    db.session.commit()
    flash("Crew updated.", "success")
    return redirect(url_for("podcasts.detail", podcast_id=podcast_id))


@podcasts_bp.route("/<int:podcast_id>/participants/<int:pp_id>/update", methods=["POST"])
@login_required
def update_slot(podcast_id, pp_id):
    from flask import abort
    podcast = Podcast.query.get_or_404(podcast_id)
    _check_edit_access(podcast)
    pp = PodcastParticipant.query.get_or_404(pp_id)
    if pp.podcast_id != podcast_id:
        abort(404)

    pp.guest_of = request.form.get("guest_of", "").strip() or None
    db.session.commit()
    flash("Updated.", "success")
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


@podcasts_bp.route("/<int:podcast_id>/participants/<int:participant_id>/send-invite", methods=["POST"])
@login_required
@permission_required("send_invitations")
def send_invite(podcast_id, participant_id):
    pp = PodcastParticipant.query.filter_by(podcast_id=podcast_id, participant_id=participant_id).first_or_404()
    pp.mark_invited()
    db.session.flush()
    sent = send_invitation_email(pp)
    db.session.commit()
    verb = "sent" if sent else "failed"
    if sent:
        flash(f"Invitation sent to {pp.participant.name}.", "success")
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
