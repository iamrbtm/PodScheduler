from flask import current_app, render_template, url_for
from flask_mail import Message
from .extensions import mail


def _build_context(podcast_participant):
    pp = podcast_participant
    participant = pp.participant
    podcast = pp.podcast
    host = podcast.host
    scheduled = podcast.scheduled_date

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

    first_name = participant.name.split()[0] if participant.name else participant.name

    return {
        "participant_name": participant.name,
        "participant_first_name": first_name,
        "participant_email": participant.email,
        "participant_role": pp.role_display,
        "episode_title": podcast.title,
        "episode_topic": podcast.topic or "",
        "episode_date": scheduled.strftime("%B %d, %Y") if scheduled else "TBD",
        "episode_time": scheduled.strftime("%I:%M %p") if scheduled else "TBD",
        "episode_duration": str(podcast.duration_minutes or 60),
        "host_name": host.username,
        "personal_message": pp.message or "",
        "accept_url": accept_url,
        "decline_url": decline_url,
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
                                guest=pp.participant, host=pp.podcast.host,
                                accept_url=context["accept_url"], decline_url=context["decline_url"],
                                personal_message=pp.message)
    text_body = render_template("email/invitation.txt", **context, pg=pp, podcast=pp.podcast,
                                guest=pp.participant, host=pp.podcast.host,
                                accept_url=context["accept_url"], decline_url=context["decline_url"],
                                personal_message=pp.message)
    return _send(pp.participant.email, subject, html_body, text_body)


def _send(to_email, subject, html_body, text_body):
    msg = Message(subject=subject, recipients=[to_email], html=html_body, body=text_body)
    try:
        mail.send(msg)
        return True
    except Exception as e:
        current_app.logger.error(f"Failed to send email to {to_email}: {e}")
        return False
