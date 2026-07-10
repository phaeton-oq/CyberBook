"""
Курсы и учебные материалы.
БАЗА готова — второй бэкенд расширяет (прогресс по урокам, категории, поиск и т.п.).

  GET  /api/courses            -> список курсов (без контента)
  GET  /api/courses/<id>       -> курс с контентом, видео и списком квизов
  POST /api/courses            -> (admin) создать курс
"""
from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user

from extensions import db
from models import Course

courses_bp = Blueprint("courses", __name__, url_prefix="/api/courses")


@courses_bp.get("")
@login_required
def list_courses():
    courses = Course.query.order_by(Course.order, Course.id).all()
    return jsonify([c.to_dict() for c in courses])


@courses_bp.get("/<int:course_id>")
@login_required
def get_course(course_id):
    course = Course.query.get_or_404(course_id)
    return jsonify(course.to_dict(with_content=True))


@courses_bp.post("")
@login_required
def create_course():
    if current_user.role != "admin":
        return jsonify(error="Только для админа"), 403
    data = request.get_json(silent=True) or {}
    if not data.get("title"):
        return jsonify(error="Нужен title"), 400
    course = Course(
        title=data["title"],
        description=data.get("description", ""),
        content=data.get("content", ""),
        video_url=data.get("video_url", ""),
        topic=data.get("topic", "Общее"),
        order=data.get("order", 0),
    )
    db.session.add(course)
    db.session.commit()
    return jsonify(course.to_dict(with_content=True)), 201
