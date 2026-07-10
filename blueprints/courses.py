"""Курсы и уроки."""
from datetime import datetime

from flask import Blueprint, jsonify, request
from flask_login import current_user, login_required

from blueprints.helpers import admin_required
from extensions import db
from models import Course, CourseProgress, Lesson, LessonProgress
import scoring

courses_bp = Blueprint("courses", __name__, url_prefix="/api/courses")


@courses_bp.get("")
@login_required
def list_courses():
    done = {
        p.course_id for p in CourseProgress.query.filter_by(
            user_id=current_user.id, completed=True,
        ).all()
    }
    courses = Course.query.order_by(Course.order, Course.id).all()
    return jsonify([{**c.to_dict(), "completed": c.id in done} for c in courses])


@courses_bp.get("/progress/me")
@login_required
def my_progress():
    return jsonify({
        "courses": [p.to_dict() for p in CourseProgress.query.filter_by(
            user_id=current_user.id, completed=True,
        ).all()],
        "lessons": [p.to_dict() for p in LessonProgress.query.filter_by(
            user_id=current_user.id, completed=True,
        ).all()],
    })


@courses_bp.get("/<int:course_id>")
@login_required
def get_course(course_id):
    course = Course.query.get_or_404(course_id)
    return jsonify(course.to_dict(with_content=True, user_id=current_user.id))


@courses_bp.post("")
@admin_required
def create_course():
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


@courses_bp.put("/<int:course_id>")
@admin_required
def update_course(course_id):
    course = Course.query.get_or_404(course_id)
    data = request.get_json(silent=True) or {}
    for field in ("title", "description", "content", "video_url", "topic", "order"):
        if field in data:
            setattr(course, field, data[field])
    db.session.commit()
    return jsonify(course.to_dict(with_content=True))


@courses_bp.delete("/<int:course_id>")
@admin_required
def delete_course(course_id):
    db.session.delete(Course.query.get_or_404(course_id))
    db.session.commit()
    return jsonify(ok=True)


@courses_bp.post("/<int:course_id>/complete")
@login_required
def complete_course(course_id):
    Course.query.get_or_404(course_id)
    row = CourseProgress.query.filter_by(
        user_id=current_user.id, course_id=course_id,
    ).first()
    if row and row.completed:
        return jsonify(error="Курс уже пройден"), 409

    if row:
        row.completed = True
        row.completed_at = datetime.utcnow()
    else:
        db.session.add(CourseProgress(
            user_id=current_user.id, course_id=course_id, completed=True,
        ))

    scoring.apply_delta(current_user, scoring.COURSE_COMPLETE)
    scoring.add_points(current_user, scoring.POINTS_COURSE)
    badges = scoring.check_score_badges(current_user)
    badges.extend(scoring.check_activity_badges(current_user))
    db.session.commit()

    return jsonify({
        "course_id": course_id,
        "completed": True,
        "security_score": current_user.security_score,
        "points": current_user.points,
        "new_badges": badges,
    })


@courses_bp.get("/<int:course_id>/lessons")
@login_required
def list_lessons(course_id):
    Course.query.get_or_404(course_id)
    done = {
        p.lesson_id for p in LessonProgress.query.filter_by(
            user_id=current_user.id, completed=True,
        ).all()
    }
    lessons = Lesson.query.filter_by(course_id=course_id).order_by(Lesson.order, Lesson.id).all()
    return jsonify([{**l.to_dict(), "completed": l.id in done} for l in lessons])


@courses_bp.post("/<int:course_id>/lessons")
@admin_required
def create_lesson(course_id):
    Course.query.get_or_404(course_id)
    data = request.get_json(silent=True) or {}
    if not data.get("title"):
        return jsonify(error="Нужен title"), 400
    lesson = Lesson(
        course_id=course_id,
        title=data["title"],
        content=data.get("content", ""),
        video_url=data.get("video_url", ""),
        order=data.get("order", 0),
    )
    db.session.add(lesson)
    db.session.commit()
    return jsonify(lesson.to_dict()), 201


@courses_bp.get("/lessons/<int:lesson_id>")
@login_required
def get_lesson(lesson_id):
    lesson = Lesson.query.get_or_404(lesson_id)
    done = LessonProgress.query.filter_by(
        user_id=current_user.id, lesson_id=lesson_id, completed=True,
    ).first() is not None
    return jsonify({**lesson.to_dict(), "completed": done})


@courses_bp.put("/lessons/<int:lesson_id>")
@admin_required
def update_lesson(lesson_id):
    lesson = Lesson.query.get_or_404(lesson_id)
    data = request.get_json(silent=True) or {}
    for field in ("title", "content", "video_url", "order", "course_id"):
        if field in data:
            setattr(lesson, field, data[field])
    db.session.commit()
    return jsonify(lesson.to_dict())


@courses_bp.delete("/lessons/<int:lesson_id>")
@admin_required
def delete_lesson(lesson_id):
    db.session.delete(Lesson.query.get_or_404(lesson_id))
    db.session.commit()
    return jsonify(ok=True)


@courses_bp.post("/lessons/<int:lesson_id>/complete")
@login_required
def complete_lesson(lesson_id):
    lesson = Lesson.query.get_or_404(lesson_id)
    row = LessonProgress.query.filter_by(user_id=current_user.id, lesson_id=lesson_id).first()
    if row and row.completed:
        return jsonify(error="Урок уже пройден"), 409

    if row:
        row.completed = True
        row.completed_at = datetime.utcnow()
    else:
        db.session.add(LessonProgress(
            user_id=current_user.id, lesson_id=lesson_id, completed=True,
        ))

    scoring.apply_delta(current_user, scoring.LESSON_COMPLETE)
    scoring.add_points(current_user, scoring.POINTS_LESSON)
    badges = scoring.check_activity_badges(current_user)

    course = lesson.course
    lesson_ids = {l.id for l in course.lessons}
    if lesson_ids:
        done = {
            p.lesson_id for p in LessonProgress.query.filter_by(
                user_id=current_user.id, completed=True,
            ).all()
        }
        if lesson_ids <= done and not CourseProgress.query.filter_by(
            user_id=current_user.id, course_id=course.id,
        ).first():
            db.session.add(CourseProgress(
                user_id=current_user.id, course_id=course.id, completed=True,
            ))
            scoring.apply_delta(current_user, scoring.COURSE_COMPLETE)
            scoring.add_points(current_user, scoring.POINTS_COURSE)
            badges.extend(scoring.check_score_badges(current_user))

    db.session.commit()
    return jsonify({
        "lesson_id": lesson_id,
        "completed": True,
        "security_score": current_user.security_score,
        "points": current_user.points,
        "new_badges": badges,
    })
