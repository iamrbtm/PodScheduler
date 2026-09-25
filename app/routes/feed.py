from datetime import timezone
from email.utils import format_datetime
from xml.etree.ElementTree import Element, SubElement, tostring, register_namespace
from flask import Blueprint, Response, current_app
from ..models import Show, Podcast, PodcastStatus

feed_bp = Blueprint("feed", __name__)

ITUNES_NS = "http://www.itunes.com/dtds/podcast-1.0.dtd"
ATOM_NS = "http://www.w3.org/2005/Atom"
register_namespace("itunes", ITUNES_NS)
register_namespace("atom", ATOM_NS)

AUDIO_MIME_TYPES = {
    "mp3": "audio/mpeg",
    "m4a": "audio/mp4",
    "wav": "audio/wav",
    "aac": "audio/aac",
    "ogg": "audio/ogg",
}


def _itunes(tag):
    return f"{{{ITUNES_NS}}}{tag}"


def _rfc2822(dt):
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return format_datetime(dt)


def _enclosure_type(object_key):
    ext = object_key.rsplit(".", 1)[-1].lower() if object_key and "." in object_key else "mp3"
    return AUDIO_MIME_TYPES.get(ext, "audio/mpeg")


@feed_bp.route("/feed/<slug>.xml")
def rss(slug):
    show = Show.query.filter_by(feed_slug=slug).first_or_404()

    episodes = (
        Podcast.query.filter_by(show_id=show.id, status=PodcastStatus.PUBLISHED)
        .filter(Podcast.audio_url.isnot(None))
        .order_by(Podcast.published_at.desc())
        .all()
    )

    rss_el = Element("rss", attrib={"version": "2.0"})
    channel = SubElement(rss_el, "channel")

    feed_url = f"{current_app.config['PUBLIC_BASE_URL']}/feed/{show.feed_slug}.xml"
    SubElement(channel, f"{{{ATOM_NS}}}link", attrib={
        "href": feed_url, "rel": "self", "type": "application/rss+xml",
    })

    SubElement(channel, "title").text = show.title
    SubElement(channel, "link").text = show.website_url or current_app.config["PUBLIC_BASE_URL"]
    SubElement(channel, "description").text = show.description or show.title
    SubElement(channel, "language").text = show.language
    SubElement(channel, _itunes("author")).text = show.author_name
    SubElement(channel, _itunes("explicit")).text = "true" if show.explicit else "false"

    owner = SubElement(channel, _itunes("owner"))
    SubElement(owner, _itunes("name")).text = show.author_name
    SubElement(owner, _itunes("email")).text = show.owner_email

    if show.cover_image_url:
        SubElement(channel, _itunes("image"), attrib={"href": show.cover_image_url})
        image = SubElement(channel, "image")
        SubElement(image, "url").text = show.cover_image_url
        SubElement(image, "title").text = show.title
        SubElement(image, "link").text = show.website_url or current_app.config["PUBLIC_BASE_URL"]

    SubElement(channel, _itunes("category"), attrib={"text": show.itunes_category})

    for episode in episodes:
        item = SubElement(channel, "item")
        SubElement(item, "title").text = episode.title
        SubElement(item, "description").text = episode.description or episode.title
        SubElement(item, "guid", attrib={"isPermaLink": "false"}).text = f"urn:podscheduler:episode:{episode.id}"

        pub_date = _rfc2822(episode.published_at)
        if pub_date:
            SubElement(item, "pubDate").text = pub_date

        SubElement(item, "enclosure", attrib={
            "url": episode.audio_url,
            "length": str(episode.audio_file_size or 0),
            "type": _enclosure_type(episode.audio_object_key),
        })

        if episode.audio_duration_seconds:
            SubElement(item, _itunes("duration")).text = str(episode.audio_duration_seconds)
        if episode.episode_number:
            SubElement(item, _itunes("episode")).text = str(episode.episode_number)
        if episode.season_number:
            SubElement(item, _itunes("season")).text = str(episode.season_number)
        SubElement(item, _itunes("explicit")).text = "true" if show.explicit else "false"

    xml_bytes = tostring(rss_el, encoding="utf-8", xml_declaration=True)
    return Response(xml_bytes, mimetype="application/rss+xml")
