from flask import Blueprint, render_template, redirect, url_for, flash
from flask_login import login_required, current_user
from ..extensions import db
from ..models import Show
from ..forms import ShowForm
from ..decorators import permission_required
from ..storage import upload_cover_image, delete_object

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
