from flask import Blueprint, render_template, redirect, url_for, flash, request, abort
from flask_login import login_required, current_user
from ..extensions import db
from ..models import Show, DirectorySubmission, SubmissionStatus
from ..forms import ShowForm
from ..decorators import permission_required
from ..storage import upload_cover_image, delete_object
from ..directories import DIRECTORIES, DIRECTORIES_BY_KEY

shows_bp = Blueprint("shows", __name__)


@shows_bp.route("/")
@login_required
@permission_required("manage_shows")
def index():
    shows = Show.query.order_by(Show.title).all()
    return render_template("admin/shows/index.html", shows=shows)


@shows_bp.route("/new", methods=["GET", "POST"])
@login_required
@permission_required("manage_shows")
def create():
    form = ShowForm()
    if form.validate_on_submit():
        show = Show(
            title=form.title.data,
            feed_slug=form.feed_slug.data,
            description=form.description.data,
            author_name=form.author_name.data,
            owner_email=form.owner_email.data,
            itunes_category=form.itunes_category.data,
            explicit=form.explicit.data,
            language=form.language.data,
            website_url=form.website_url.data or None,
            created_by_id=current_user.id,
        )
        db.session.add(show)
        db.session.flush()

        if form.cover_image.data:
            key, url, _ = upload_cover_image(form.cover_image.data, show.id)
            show.cover_image_object_key = key
            show.cover_image_url = url

        db.session.commit()
        flash(f"Show '{show.title}' created.", "success")
        return redirect(url_for("shows.index"))

    return render_template("admin/shows/form.html", form=form, show=None)


@shows_bp.route("/<int:show_id>/edit", methods=["GET", "POST"])
@login_required
@permission_required("manage_shows")
def edit(show_id):
    show = Show.query.get_or_404(show_id)
    form = ShowForm(show=show, obj=show)

    if form.validate_on_submit():
        show.title = form.title.data
        show.feed_slug = form.feed_slug.data
        show.description = form.description.data
        show.author_name = form.author_name.data
        show.owner_email = form.owner_email.data
        show.itunes_category = form.itunes_category.data
        show.explicit = form.explicit.data
        show.language = form.language.data
        show.website_url = form.website_url.data or None

        if form.cover_image.data:
            delete_object(show.cover_image_object_key)
            key, url, _ = upload_cover_image(form.cover_image.data, show.id)
            show.cover_image_object_key = key
            show.cover_image_url = url

        db.session.commit()
        flash("Show updated.", "success")
        return redirect(url_for("shows.index"))

    return render_template("admin/shows/form.html", form=form, show=show)


@shows_bp.route("/<int:show_id>/directories")
@login_required
@permission_required("manage_shows")
def directories(show_id):
    show = Show.query.get_or_404(show_id)
    submissions = {s.directory_key: s for s in show.directory_submissions}
    rows = []
    for d in DIRECTORIES:
        submission = submissions.get(d["key"])
        rows.append({
            **d,
            "status": submission.status.value if submission else SubmissionStatus.NOT_SUBMITTED.value,
            "submitted_at": submission.submitted_at if submission else None,
        })
    return render_template("admin/shows/directories.html", show=show, rows=rows)


@shows_bp.route("/<int:show_id>/directories/<key>", methods=["POST"])
@login_required
@permission_required("manage_shows")
def update_directory_status(show_id, key):
    show = Show.query.get_or_404(show_id)
    if key not in DIRECTORIES_BY_KEY:
        abort(404)

    status_value = request.form.get("status")
    try:
        status = SubmissionStatus(status_value)
    except ValueError:
        flash("Invalid status.", "danger")
        return redirect(url_for("shows.directories", show_id=show_id))

    submission = DirectorySubmission.query.filter_by(show_id=show_id, directory_key=key).first()
    if not submission:
        submission = DirectorySubmission(show_id=show_id, directory_key=key)
        db.session.add(submission)

    submission.mark(status)
    submission.updated_by_id = current_user.id
    db.session.commit()
    flash(f"{DIRECTORIES_BY_KEY[key]['name']} marked as {status.value.replace('_', ' ')}.", "success")
    return redirect(url_for("shows.directories", show_id=show_id))


@shows_bp.route("/<int:show_id>/delete", methods=["POST"])
@login_required
@permission_required("manage_shows")
def delete(show_id):
    show = Show.query.get_or_404(show_id)
    if show.episodes.count():
        flash("Cannot delete a show with episodes attached to it.", "danger")
        return redirect(url_for("shows.index"))
    delete_object(show.cover_image_object_key)
    db.session.delete(show)
    db.session.commit()
    flash(f"Show '{show.title}' deleted.", "success")
    return redirect(url_for("shows.index"))
