"""Админ: управление сотрудниками (создание, удаление). Только для роли admin."""
from flask import Blueprint, request, jsonify
from flask_login import current_user

from blueprints.helpers import admin_required
from extensions import db
from models import (
    User, QuizAttempt, PhishingResult, Badge,
    CourseProgress, LessonProgress, ThreatScan,
)

admin_bp = Blueprint("admin", __name__, url_prefix="/api/admin")


@admin_bp.post("/users")
@admin_required
def create_user():
    """Создать сотрудника."""
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""

    if not name or not email or not password:
        return jsonify(error="Нужны name, email и password"), 400
    if User.query.filter_by(email=email).first():
        return jsonify(error="Пользователь с таким email уже существует"), 409

    user = User(
        name=name,
        email=email,
        role="employee",
        department=(data.get("department") or "Общий").strip(),
    )
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    return jsonify(user.to_dict()), 201


@admin_bp.delete("/users/<int:user_id>")
@admin_required
def delete_user(user_id):
    """Удалить сотрудника вместе со связанными записями."""
    user = User.query.get_or_404(user_id)
    if user.id == current_user.id:
        return jsonify(error="Нельзя удалить самого себя"), 400
    if user.role == "admin":
        return jsonify(error="Нельзя удалить администратора"), 400

    # чистим зависимые записи, чтобы не оставлять «сирот»
    for model in (QuizAttempt, PhishingResult, Badge, CourseProgress, LessonProgress, ThreatScan):
        model.query.filter_by(user_id=user.id).delete()
    db.session.delete(user)
    db.session.commit()
    return jsonify(ok=True)
