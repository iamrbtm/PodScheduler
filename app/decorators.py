from functools import wraps
from flask import abort
from flask_login import current_user


def permission_required(perm):
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            if not current_user.is_authenticated:
                abort(401)
            if not current_user.has_permission(perm) and not current_user.is_admin():
                abort(403)
            return f(*args, **kwargs)
        return decorated
    return decorator


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated:
            abort(401)
        if not current_user.is_admin():
            abort(403)
        return f(*args, **kwargs)
    return decorated
