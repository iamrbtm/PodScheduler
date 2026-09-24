from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required
from ..extensions import db
from ..models import User, Role
from ..models.role import PERMISSIONS
from ..forms import EditUserForm, RoleForm
from ..decorators import admin_required

admin_bp = Blueprint("admin", __name__)


@admin_bp.route("/")
@login_required
@admin_required
def dashboard():
    users = User.query.order_by(User.created_at.desc()).all()
    roles = Role.query.all()
    return render_template("admin/dashboard.html", users=users, roles=roles)


@admin_bp.route("/users")
@login_required
@admin_required
def users():
    users = User.query.order_by(User.username).all()
    return render_template("admin/users.html", users=users)


@admin_bp.route("/users/<int:user_id>/edit", methods=["GET", "POST"])
@login_required
@admin_required
def edit_user(user_id):
    user = User.query.get_or_404(user_id)
    form = EditUserForm(user=user, obj=user)
    form.role_id.choices = [(r.id, r.name.title()) for r in Role.query.order_by(Role.name).all()]

    if form.validate_on_submit():
        user.username = form.username.data
        user.email = form.email.data.lower()
        user.role_id = form.role_id.data
        user.is_active = form.is_active.data
        if form.new_password.data:
            user.set_password(form.new_password.data)
        db.session.commit()
        flash(f"User '{user.username}' updated.", "success")
        return redirect(url_for("admin.users"))

    return render_template("admin/edit_user.html", form=form, user=user)


@admin_bp.route("/users/<int:user_id>/toggle", methods=["POST"])
@login_required
@admin_required
def toggle_user(user_id):
    user = User.query.get_or_404(user_id)
    if user.is_admin():
        flash("Cannot deactivate the admin account.", "danger")
    else:
        user.is_active = not user.is_active
        db.session.commit()
        state = "activated" if user.is_active else "deactivated"
        flash(f"User '{user.username}' {state}.", "success")
    return redirect(url_for("admin.users"))


@admin_bp.route("/users/new", methods=["GET", "POST"])
@login_required
@admin_required
def create_user():
    from ..forms.auth import RegisterForm
    form = RegisterForm()
    roles = Role.query.order_by(Role.name).all()
    role_choices = [(r.id, r.name.title()) for r in roles]

    if request.method == "POST" and form.validate_on_submit():
        role_id = request.form.get("role_id", type=int)
        role = Role.query.get(role_id)
        if not role:
            flash("Invalid role selected.", "danger")
        else:
            user = User(
                username=form.username.data,
                email=form.email.data.lower(),
                role_id=role.id,
                is_active=True,
            )
            user.set_password(form.password.data)
            db.session.add(user)
            db.session.commit()
            flash(f"User '{user.username}' created.", "success")
            return redirect(url_for("admin.users"))

    return render_template("admin/create_user.html", form=form, role_choices=role_choices)


@admin_bp.route("/roles")
@login_required
@admin_required
def roles():
    roles = Role.query.order_by(Role.name).all()
    return render_template("admin/roles.html", roles=roles, all_permissions=PERMISSIONS)


@admin_bp.route("/roles/new", methods=["GET", "POST"])
@login_required
@admin_required
def create_role():
    form = RoleForm()
    if form.validate_on_submit():
        role = Role(name=form.name.data.lower(), description=form.description.data)
        perms = request.form.getlist("permissions")
        role.permissions = ",".join(sorted(perms))
        db.session.add(role)
        db.session.commit()
        flash(f"Role '{role.name}' created.", "success")
        return redirect(url_for("admin.roles"))
    return render_template("admin/role_form.html", form=form, all_permissions=PERMISSIONS, role=None)


@admin_bp.route("/roles/<int:role_id>/edit", methods=["GET", "POST"])
@login_required
@admin_required
def edit_role(role_id):
    role = Role.query.get_or_404(role_id)
    form = RoleForm(obj=role)
    if form.validate_on_submit():
        role.name = form.name.data.lower()
        role.description = form.description.data
        perms = request.form.getlist("permissions")
        role.permissions = ",".join(sorted(perms))
        db.session.commit()
        flash(f"Role '{role.name}' updated.", "success")
        return redirect(url_for("admin.roles"))
    return render_template("admin/role_form.html", form=form, all_permissions=PERMISSIONS, role=role)


@admin_bp.route("/roles/<int:role_id>/delete", methods=["POST"])
@login_required
@admin_required
def delete_role(role_id):
    role = Role.query.get_or_404(role_id)
    if role.name == "admin":
        flash("Cannot delete the admin role.", "danger")
    elif role.users.count() > 0:
        flash("Cannot delete a role that is assigned to users.", "danger")
    else:
        db.session.delete(role)
        db.session.commit()
        flash(f"Role '{role.name}' deleted.", "success")
    return redirect(url_for("admin.roles"))
