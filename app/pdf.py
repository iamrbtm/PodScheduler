from io import BytesIO
from xml.sax.saxutils import escape

from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer


def _fmt(dt):
    if not dt:
        return "TBD"
    return f"{dt.strftime('%A, %B')} {dt.day}, {dt.year} at {dt.strftime('%I').lstrip('0')}:{dt.strftime('%M %p')}"


def _para(text, style):
    # Paragraph parses XML-ish markup, so user text must be escaped (and newlines made explicit).
    return Paragraph(escape(text).replace("\n", "<br/>"), style)


def build_episode_pdf(pp):
    """PDF of what an *accepted* guest sees on their episode page. Never includes
    Podcast.notes (internal) or unconfirmed guests."""
    episode = pp.podcast
    styles = getSampleStyleSheet()
    title = ParagraphStyle("PSTitle", parent=styles["Title"], alignment=0, fontSize=20, leading=24)
    heading = ParagraphStyle("PSHeading", parent=styles["Heading3"], spaceBefore=12, spaceAfter=2)
    body = styles["BodyText"]

    story = [_para(episode.title, title)]
    if episode.show:
        story.append(_para(episode.show.title, body))
    story.append(Spacer(1, 6))

    rows = [
        ("Your role", pp.role_display),
        ("Recording", _fmt(episode.recording_date)),
        ("Release", _fmt(episode.scheduled_date)),
        ("Host", episode.host.username),
        ("Topic", episode.topic),
        ("Length", f"About {episode.duration_minutes} minutes" if episode.duration_minutes else None),
    ]
    for label, value in rows:
        if value:
            story.append(Paragraph(f"<b>{escape(label)}:</b> {escape(str(value))}", body))

    sections = [
        ("About this episode", episode.description),
        ("A note from the host", pp.message),
        ("How to prepare", episode.guest_prep_info),
    ]
    for label, value in sections:
        if value:
            story.append(Paragraph(escape(label), heading))
            story.append(_para(value, body))

    others = pp.other_confirmed_guests()
    if others:
        story.append(Paragraph("Also on this episode", heading))
        for o in others:
            story.append(_para(f"{o.participant.name} ({o.role_display})", body))

    buf = BytesIO()
    SimpleDocTemplate(
        buf, pagesize=letter, title=episode.title,
        leftMargin=inch, rightMargin=inch, topMargin=inch, bottomMargin=inch,
    ).build(story)
    return buf.getvalue()
