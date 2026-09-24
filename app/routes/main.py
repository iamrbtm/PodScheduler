from flask import Blueprint, render_template, redirect, url_for
from flask_login import login_required, current_user
from ..models import Podcast, PodcastStatus
from ..extensions import db

main_bp = Blueprint("main", __name__)


@main_bp.route("/")
def index():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))
    return redirect(url_for("auth.login"))


@main_bp.route("/dashboard")
@login_required
def dashboard():
    upcoming = (
        Podcast.query
        .filter(Podcast.status.in_([PodcastStatus.SCHEDULED, PodcastStatus.DRAFT]))
        .order_by(Podcast.scheduled_date.asc())
        .limit(5)
        .all()
    )
    recent = (
        Podcast.query
        .order_by(Podcast.created_at.desc())
        .limit(5)
        .all()
    )
    total_podcasts = Podcast.query.count()
    scheduled_count = Podcast.query.filter_by(status=PodcastStatus.SCHEDULED).count()
    published_count = Podcast.query.filter_by(status=PodcastStatus.PUBLISHED).count()

    return render_template(
        "main/dashboard.html",
        upcoming=upcoming,
        recent=recent,
        total_podcasts=total_podcasts,
        scheduled_count=scheduled_count,
        published_count=published_count,
    )
