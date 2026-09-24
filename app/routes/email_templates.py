import json
from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from ..extensions import db
from ..models import EmailTemplate, MERGE_FIELDS
from ..decorators import permission_required

email_templates_bp = Blueprint("email_templates", __name__)


@email_templates_bp.route("/")
@login_required
@permission_required("manage_email_templates")
def index():
    templates = EmailTemplate.query.order_by(EmailTemplate.updated_at.desc()).all()
    return render_template("admin/email_templates/index.html", templates=templates)


@email_templates_bp.route("/new")
@login_required
@permission_required("manage_email_templates")
def create():
    return render_template(
        "admin/email_templates/builder.html",
        template=None,
        merge_fields=MERGE_FIELDS,
    )


@email_templates_bp.route("/<int:template_id>/edit")
@login_required
@permission_required("manage_email_templates")
def edit(template_id):
    template = EmailTemplate.query.get_or_404(template_id)
    return render_template(
        "admin/email_templates/builder.html",
        template=template,
        merge_fields=MERGE_FIELDS,
    )


@email_templates_bp.route("/save", methods=["POST"])
@login_required
@permission_required("manage_email_templates")
def save():
    data = request.get_json()
    template_id = data.get("id")
    name = (data.get("name") or "").strip()
    subject = (data.get("subject") or "").strip()
    blocks = data.get("blocks", [])

    if not name or not subject:
        return jsonify({"error": "Name and subject are required."}), 400

    if template_id:
        tmpl = EmailTemplate.query.get_or_404(template_id)
    else:
        tmpl = EmailTemplate(created_by_id=current_user.id)
        db.session.add(tmpl)

    tmpl.name = name
    tmpl.subject = subject
    tmpl.set_blocks(blocks)
    db.session.commit()

    return jsonify({"id": tmpl.id, "redirect": url_for("email_templates.index")})


@email_templates_bp.route("/<int:template_id>/delete", methods=["POST"])
@login_required
@permission_required("manage_email_templates")
def delete(template_id):
    tmpl = EmailTemplate.query.get_or_404(template_id)
    name = tmpl.name
    db.session.delete(tmpl)
    db.session.commit()
    flash(f"Template '{name}' deleted.", "success")
    return redirect(url_for("email_templates.index"))


@email_templates_bp.route("/<int:template_id>/preview")
@login_required
@permission_required("manage_email_templates")
def preview(template_id):
    tmpl = EmailTemplate.query.get_or_404(template_id)
    sample = {
        "participant_name": "Jane Smith",
        "participant_first_name": "Jane",
        "participant_email": "jane@example.com",
        "participant_role": "Keynote Speaker",
        "episode_title": "The Future of AI",
        "episode_topic": "Artificial Intelligence Trends",
        "episode_date": "October 15, 2026",
        "episode_time": "2:00 PM",
        "episode_duration": "60",
        "host_name": "Alex Johnson",
        "personal_message": "We'd love to have you share your expertise!",
        "accept_url": "#accept",
        "decline_url": "#decline",
    }
    subject, html, _ = tmpl.render(sample)
    return render_template(
        "admin/email_templates/preview.html",
        tmpl=tmpl,
        subject=subject,
        html_body=html,
    )
