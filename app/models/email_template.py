import json
import re
from datetime import datetime, timezone
from ..extensions import db


MERGE_FIELDS = {
    "participant_name": "Participant's full name",
    "participant_first_name": "Participant's first name",
    "participant_email": "Participant's email address",
    "participant_role": "Role on this episode (e.g. Keynote Speaker)",
    "episode_title": "Episode/podcast title",
    "episode_topic": "Episode topic",
    "episode_date": "Scheduled date",
    "episode_time": "Scheduled time",
    "episode_duration": "Duration in minutes",
    "host_name": "Host's name",
    "personal_message": "Optional personal message",
    "accept_url": "Invitation accept link",
    "decline_url": "Invitation decline link",
}


def render_blocks_to_html(blocks: list) -> str:
    parts = [
        '<div style="font-family:-apple-system,BlinkMacSystemFont,\'Segoe UI\',sans-serif;'
        'max-width:600px;margin:0 auto;background:#fff;border-radius:12px;overflow:hidden;'
        'box-shadow:0 2px 8px rgba(0,0,0,.1);">'
    ]
    for block in blocks:
        t = block.get("type")
        content = block.get("content", "")

        if t == "header":
            bg = block.get("bg_color", "#1a1a2e")
            color = block.get("text_color", "#ffffff")
            parts.append(
                f'<div style="background:{bg};color:{color};padding:32px;text-align:center;">'
                f'<div style="font-size:2rem;">🎙️</div>'
                f'<h1 style="margin:8px 0 0;font-size:1.5rem;">{content}</h1></div>'
            )
        elif t == "text":
            parts.append(
                f'<div style="padding:24px 32px;">'
                f'<p style="margin:0;line-height:1.6;color:#333;white-space:pre-wrap;">{content}</p></div>'
            )
        elif t == "button_row":
            accept_text = block.get("accept_text", "Accept Invitation")
            decline_text = block.get("decline_text", "Decline")
            parts.append(
                f'<div style="padding:16px 32px;text-align:center;">'
                f'<a href="{{{{accept_url}}}}" style="display:inline-block;background:#198754;color:#fff;'
                f'text-decoration:none;padding:14px 32px;border-radius:8px;font-weight:600;margin-right:12px;">'
                f'{accept_text}</a>'
                f'<a href="{{{{decline_url}}}}" style="display:inline-block;background:#dc3545;color:#fff;'
                f'text-decoration:none;padding:14px 32px;border-radius:8px;font-weight:600;">'
                f'{decline_text}</a></div>'
            )
        elif t == "divider":
            parts.append('<hr style="border:none;border-top:1px solid #e9ecef;margin:0 32px;">')
        elif t == "spacer":
            height = block.get("height", 20)
            parts.append(f'<div style="height:{height}px;"></div>')
        elif t == "detail_box":
            parts.append(
                f'<div style="background:#f8f9fa;border-radius:8px;padding:20px;margin:0 32px 16px;">'
                f'<p style="margin:0;line-height:1.8;color:#333;white-space:pre-wrap;">{content}</p></div>'
            )
        elif t == "footer":
            parts.append(
                f'<div style="background:#f8f9fa;padding:20px 32px;text-align:center;'
                f'font-size:.8rem;color:#6c757d;">{content}</div>'
            )

    parts.append('</div>')
    return "\n".join(parts)


def render_blocks_to_text(blocks: list) -> str:
    lines = []
    for block in blocks:
        t = block.get("type")
        content = block.get("content", "")
        if t in ("header", "text", "detail_box", "footer"):
            lines.append(content)
            lines.append("")
        elif t == "button_row":
            lines.append(f'To ACCEPT: {{{{accept_url}}}}')
            lines.append(f'To DECLINE: {{{{decline_url}}}}')
            lines.append("")
        elif t == "divider":
            lines.append("---")
            lines.append("")
    return "\n".join(lines)


def merge(template_str: str, context: dict) -> str:
    def replacer(m):
        key = m.group(1).strip()
        return str(context.get(key, m.group(0)))
    return re.sub(r"\{\{(\w+)\}\}", replacer, template_str)


class EmailTemplate(db.Model):
    __tablename__ = "email_templates"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    subject = db.Column(db.String(500), nullable=False, default="")
    blocks_json = db.Column(db.Text, default="[]")
    html_body = db.Column(db.Text, default="")
    text_body = db.Column(db.Text, default="")
    created_by_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    creator = db.relationship("User", foreign_keys=[created_by_id])

    def get_blocks(self):
        try:
            return json.loads(self.blocks_json or "[]")
        except Exception:
            return []

    def set_blocks(self, blocks: list):
        self.blocks_json = json.dumps(blocks)
        self.html_body = render_blocks_to_html(blocks)
        self.text_body = render_blocks_to_text(blocks)

    def render(self, context: dict) -> tuple[str, str, str]:
        """Return (subject, html, text) with merge fields resolved."""
        return (
            merge(self.subject, context),
            merge(self.html_body, context),
            merge(self.text_body or "", context),
        )

    def __repr__(self):
        return f"<EmailTemplate {self.name}>"
