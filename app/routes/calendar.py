from datetime import datetime, timedelta, timezone

from flask import Blueprint, Response, current_app, url_for, jsonify, render_template
from flask_login import login_required, current_user
from icalendar import Calendar, Event

from ..models import Podcast, PodcastStatus
from ..models.calendar_settings import CalendarSettings

calendar_bp = Blueprint("calendar", __name__)

# Copied verbatim from base.html's .badge-status-* rules — keep in sync by hand.
STATUS_COLORS = {
    PodcastStatus.DRAFT: "#8a8a99",
    PodcastStatus.SCHEDULED: "#60a5fa",
    PodcastStatus.RECORDED: "#fb923c",
    PodcastStatus.READY_TO_DISTRIBUTE: "#93c5fd",
    PodcastStatus.PUBLISHED: "#4ade80",
    PodcastStatus.CANCELLED: "#f87171",
}


def _event_start(podcast):
    # scheduled_date comes from a DateTimeLocalField and is stored — and
    # displayed everywhere else in this app (podcasts/detail.html,
    # main/dashboard.html) — as the naive wall-clock time the producer
    # typed, with no timezone math applied anywhere. Keep it naive/floating
    # here too, so FullCalendar and ICS clients render the same numbers
    # instead of reinterpreting them as UTC and shifting by the viewer's
    # offset. published_at is genuinely UTC (set via
    # datetime.now(timezone.utc) in podcasts.py) and gets tagged as such.
    if podcast.scheduled_date:
        return podcast.scheduled_date
    if podcast.published_at:
        dt = podcast.published_at
        return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)
    return None


def _event_duration_minutes(podcast):
    if podcast.scheduled_date:
        return 30  # release is a marker, not a block of time
    if podcast.audio_duration_seconds:
        return max(1, podcast.audio_duration_seconds // 60)
    return 30


def _calendar_events(podcast):
    """Yield (uid_suffix, title, start, end) for each event this episode produces.

    Recording is its own event (naive wall-clock, like scheduled_date), prefixed
    "RECORDING - "; the release event keeps the original scheduled_date/published_at
    behavior.
    """
    if podcast.recording_date:
        start = podcast.recording_date
        end = start + timedelta(minutes=podcast.duration_minutes or 60)
        yield "recording", f"RECORDING - {podcast.title}", start, end
    start = _event_start(podcast)
    if start is not None:
        end = start + timedelta(minutes=_event_duration_minutes(podcast))
        yield "release", podcast.title, start, end


@calendar_bp.route("/calendar/feed/<token>.ics")
def ics_feed(token):
    settings = CalendarSettings.query.filter_by(feed_token=token).first_or_404()

    # Deliberately NOT visibility-scoped — always the full pipeline.
    # See docs/superpowers/specs/2026-09-28-calendar-page-design.md
    # ("Decisions confirmed with stakeholder"). Do not add per-user
    # filtering here.
    podcasts = Podcast.query.all()

    cal = Calendar()
    cal.add("prodid", "-//PodScheduler//Calendar Feed//EN")
    cal.add("version", "2.0")
    cal.add("calscale", "GREGORIAN")
    cal.add("method", "PUBLISH")
    cal.add("x-wr-calname", "PodScheduler Pipeline")
    # Best-effort refresh hints — clients are not required to honor these,
    # and there is no way to force a faster refresh from this side.
    cal.add("x-published-ttl", "PT1H")

    base_url = current_app.config["PUBLIC_BASE_URL"]

    for podcast, suffix, title, start, end in (
        (p, *e) for p in podcasts for e in _calendar_events(p)
    ):
        event = Event()
        # The release event keeps the original UID so existing subscriptions
        # don't see it as a new event.
        uid_kind = "" if suffix == "release" else f"-{suffix}"
        event.add("uid", f"podscheduler-episode-{podcast.id}{uid_kind}@podscheduler.local")
        event.add("summary", title)
        event.add("dtstart", start)
        event.add("dtend", end)
        event.add("dtstamp", datetime.now(timezone.utc))
        event.add("sequence", 0)
        event.add("color", STATUS_COLORS[podcast.status])
        event.add("url", f"{base_url}{url_for('podcasts.detail', podcast_id=podcast.id)}")

        description_lines = [
            f"Status: {podcast.status.value.replace('_', ' ').title()}",
        ]
        if podcast.host:
            description_lines.append(f"Host: {podcast.host.username}")
        if podcast.show:
            description_lines.append(f"Show: {podcast.show.title}")
        description_lines.append(f"Participants: {podcast.participant_count}")
        event.add("description", "\n".join(description_lines))

        cal.add_component(event)

    return Response(
        cal.to_ical(),
        mimetype="text/calendar",
        headers={"Content-Disposition": "inline; filename=podscheduler-pipeline.ics"},
    )


def _visible_podcasts():
    query = Podcast.query
    if not current_user.is_admin() and not current_user.has_permission("view_all"):
        query = query.filter(
            (Podcast.host_id == current_user.id) |
            (Podcast.created_by_id == current_user.id)
        )
    return query


def _event_payload(podcast, suffix, title, start, end):
    return {
        "id": f"{podcast.id}-{suffix}",
        "title": title,
        "start": start.isoformat(),
        "end": end.isoformat(),
        "color": STATUS_COLORS[podcast.status],
        "url": url_for("podcasts.detail", podcast_id=podcast.id),
        "extendedProps": {
            "status": podcast.status.value.replace("_", " ").title(),
            "host": podcast.host.username if podcast.host else None,
            "show": podcast.show.title if podcast.show else None,
            "participantCount": podcast.participant_count,
        },
    }


@calendar_bp.route("/calendar/events.json")
@login_required
def events_json():
    podcasts = _visible_podcasts().all()
    events = [_event_payload(p, *e) for p in podcasts for e in _calendar_events(p)]
    return jsonify(events)


@calendar_bp.route("/calendar")
@login_required
def index():
    return render_template("calendar/index.html")
