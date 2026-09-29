from flask import current_app, render_template, url_for
from flask_mail import Message
from .extensions import mail


def _build_context(podcast_participant):
    pp = podcast_participant
    participant = pp.participant
    podcast = pp.podcast
    host = podcast.host
    recording = podcast.recording_date
    release = podcast.scheduled_date

    accept_url = url_for(
        "invitations.respond",
        token=pp.invitation_token,
        action="accept",
        _external=True,
    )
    decline_url = url_for(
        "invitations.respond",
        token=pp.invitation_token,
        action="decline",
        _external=True,
    )

    portal_url = url_for(
        "portal.dashboard",
        token=participant.ensure_portal_token(),
        _external=True,
    )

    first_name = participant.name.split()[0] if participant.name else participant.name

    return {
        "participant_name": participant.name,
        "participant_first_name": first_name,
        "participant_email": participant.email,
        "participant_role": pp.role_display,
        "episode_title": podcast.title,
        "episode_topic": podcast.topic or "",
        "episode_date": recording.strftime("%B %d, %Y") if recording else "TBD",
        "episode_time": recording.strftime("%I:%M %p") if recording else "TBD",
        "release_date": release.strftime("%B %d, %Y") if release else "TBD",
        "release_time": release.strftime("%I:%M %p") if release else "TBD",
        "episode_duration": str(podcast.duration_minutes or 60),
        "host_name": host.username,
        "personal_message": pp.message or "",
        "accept_url": accept_url,
        "decline_url": decline_url,
        "portal_url": portal_url,
    }


def send_invitation_email(podcast_participant):
    pp = podcast_participant
    context = _build_context(pp)

    # Use a saved email template if one was selected
    if pp.email_template_id:
        from .models import EmailTemplate
        tmpl = EmailTemplate.query.get(pp.email_template_id)
        if tmpl:
            subject, html_body, text_body = tmpl.render(context)
            return _send(pp.participant.email, subject, html_body, text_body)

    # Fall back to the built-in Jinja2 templates
    subject = f"Podcast Invitation: {pp.podcast.title}"
    html_body = render_template("email/invitation.html", **context, pg=pp, podcast=pp.podcast,
                                guest=pp.participant, host=pp.podcast.host)
    text_body = render_template("email/invitation.txt", **context, pg=pp, podcast=pp.podcast,
                                guest=pp.participant, host=pp.podcast.host)
    return _send(pp.participant.email, subject, html_body, text_body)


def _send(to_email, subject, html_body, text_body, reply_to=None, attachments=None):
    msg = Message(subject=subject, recipients=[to_email], html=html_body, body=text_body, reply_to=reply_to)
    for filename, content_type, data in attachments or []:
        msg.attach(filename, content_type, data)
    try:
        mail.send(msg)
        return True
    except Exception as e:
        current_app.logger.error(f"Failed to send email to {to_email}: {e}")
        return False


def send_guest_question_email(question):
    pp = question.podcast_participant
    guest = pp.participant
    episode = pp.podcast
    subject = f"Question from {guest.name} about {episode.title}"
    text = (
        f'{guest.name} <{guest.email}> asked about "{episode.title}":\n\n'
        f"{question.question}\n\n"
        "— Reply to this email to answer them directly."
    )
    return _send(episode.host.email, subject, None, text, reply_to=guest.email)
