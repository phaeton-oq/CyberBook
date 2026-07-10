"""Декоратор доступа только для администратора."""
from functools import wraps

from flask import jsonify
from flask_login import login_required, current_user


def admin_required(view):
    @wraps(view)
    @login_required
    def wrapped(*args, **kwargs):
        if current_user.role != "admin":
            return jsonify(error="Только для админа"), 403
        return view(*args, **kwargs)
    return wrapped
