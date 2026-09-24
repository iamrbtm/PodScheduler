from flask import current_app, render_template, url_for
from flask_mail import Message
from .extensions import mail


def send_invitation_email(podcast_guest):
    guest = podcast_guest.guest
    podcast = podcast_guest.podcast
    host = podcast.host

    accept_url = url_for(
        "invitations.respond",
        token=podcast_guest.invitation_token,
        action="accept",
        _external=True,
    )
    decline_url = url_for(
        "invitations.respond",
        token=podcast_guest.invitation_token,
        action="decline",
        _external=True,
    )

    subject = f"Podcast Invitation: {podcast.title}"
    html_body = render_template(
        "email/invitation.html",
        guest=guest,
        podcast=podcast,
        host=host,
        accept_url=accept_url,
        decline_url=decline_url,
        personal_message=podcast_guest.message,
    )
    text_body = render_template(
        "email/invitation.txt",
        guest=guest,
        podcast=podcast,
        host=host,
        accept_url=accept_url,
        decline_url=decline_url,
        personal_message=podcast_guest.message,
    )

    msg = Message(
        subject=subject,
        recipients=[guest.email],
        html=html_body,
        body=text_body,
    )
    try:
        mail.send(msg)
        return True
    except Exception as e:
        current_app.logger.error(f"Failed to send invitation email to {guest.email}: {e}")
        return False
