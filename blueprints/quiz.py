"""Квизы."""
from flask import Blueprint, jsonify, request
from flask_login import current_user, login_required
from sqlalchemy import func

from blueprints.helpers import admin_required
from extensions import db
from models import Course, PhishingResult, Question, Quiz, QuizAttempt
import ai
import scoring

quiz_bp = Blueprint("quiz", __name__, url_prefix="/api/quiz")


@quiz_bp.get("")
@login_required
def list_quizzes():
    return jsonify([
        {
            "id": q.id,
            "title": q.title,
            "course_id": q.course_id,
            "ai_generated": q.ai_generated,
            "question_count": len(q.questions),
        }
        for q in Quiz.query.order_by(Quiz.id).all()
    ])


@quiz_bp.get("/history")
@login_required
def history():
    attempts = QuizAttempt.query.filter_by(user_id=current_user.id)\
        .order_by(QuizAttempt.created_at.desc()).limit(50).all()
    return jsonify([a.to_dict(with_quiz=True) for a in attempts])


@quiz_bp.get("/<int:quiz_id>")
@login_required
def get_quiz(quiz_id):
    return jsonify(Quiz.query.get_or_404(quiz_id).to_dict(with_answers=False))


@quiz_bp.post("/<int:quiz_id>/submit")
@login_required
def submit(quiz_id):
    quiz = Quiz.query.get_or_404(quiz_id)
    answers = (request.get_json(silent=True) or {}).get("answers") or []
    questions = quiz.questions
    total = len(questions)
    correct = 0
    review = []

    for i, q in enumerate(questions):
        chosen = answers[i] if i < len(answers) else None
        ok = chosen == q.correct_index
        correct += int(ok)
        review.append({
            "question_id": q.id,
            "chosen": chosen,
            "correct_index": q.correct_index,
            "is_correct": ok,
            "explanation": q.explanation,
        })

    score = round(100 * correct / total) if total else 0
    db.session.add(QuizAttempt(
        user_id=current_user.id, quiz_id=quiz.id,
        score=score, total=total, correct=correct,
    ))
    scoring.apply_delta(current_user, round(scoring.QUIZ_BONUS_MAX * correct / total) if total else 0)
    scoring.add_points(current_user, correct * scoring.POINTS_QUIZ_PER_CORRECT)
    badges = scoring.check_score_badges(current_user)
    badges.extend(scoring.check_activity_badges(current_user))
    if score == 100 and scoring.award_badge(current_user, "Отличник ИБ", "🎓"):
        badges.append("Отличник ИБ")
    db.session.commit()

    return jsonify({
        "score": score,
        "correct": correct,
        "total": total,
        "review": review,
        "security_score": current_user.security_score,
        "points": current_user.points,
        "new_badges": badges,
    })


@quiz_bp.post("/generate")
@login_required
def generate():
    data = request.get_json(silent=True) or {}
    payload, used_ai = ai.generate_quiz(
        topic=data.get("topic", "общая кибербезопасность"),
        n=int(data.get("n", 4)),
        difficulty=data.get("difficulty", "medium"),
    )
    quiz = Quiz(
        title=payload.get("title", "Квиз"),
        course_id=data.get("course_id"),
        ai_generated=True,
    )
    db.session.add(quiz)
    db.session.flush()
    for q in payload["questions"]:
        db.session.add(Question(
            quiz_id=quiz.id,
            text=q["text"],
            options=q["options"],
            correct_index=q["correct_index"],
            explanation=q.get("explanation", ""),
        ))
    db.session.commit()
    return jsonify({"quiz": quiz.to_dict(with_answers=False), "ai": used_ai}), 201


@quiz_bp.post("/personalized")
@login_required
def personalized():
    weak = []
    rows = db.session.query(Quiz.course_id, func.avg(QuizAttempt.score))\
        .join(QuizAttempt, QuizAttempt.quiz_id == Quiz.id)\
        .filter(QuizAttempt.user_id == current_user.id)\
        .group_by(Quiz.course_id).all()

    for course_id, avg in rows:
        if avg is not None and avg < 70 and course_id:
            course = Course.query.get(course_id)
            if course and course.topic:
                weak.append(course.topic)

    if PhishingResult.query.filter_by(user_id=current_user.id, correct=False).count():
        weak.append("Фишинг")
    if not weak:
        weak.append("общая кибербезопасность")

    topic = weak[0]
    data = request.get_json(silent=True) or {}
    payload, used_ai = ai.generate_quiz(topic=topic, n=int(data.get("n", 4)), difficulty="medium")
    course = Course.query.filter_by(topic=topic).first()

    quiz = Quiz(
        title=payload.get("title", f"Персональный квиз: {topic}"),
        course_id=course.id if course else None,
        ai_generated=True,
    )
    db.session.add(quiz)
    db.session.flush()
    for q in payload["questions"]:
        db.session.add(Question(
            quiz_id=quiz.id,
            text=q["text"],
            options=q["options"],
            correct_index=q["correct_index"],
            explanation=q.get("explanation", ""),
        ))
    db.session.commit()

    return jsonify({
        "quiz": quiz.to_dict(with_answers=False),
        "ai": used_ai,
        "weak_topics": list(dict.fromkeys(weak)),
        "selected_topic": topic,
    }), 201


@quiz_bp.post("")
@admin_required
def create_quiz():
    data = request.get_json(silent=True) or {}
    if not data.get("title"):
        return jsonify(error="Нужен title"), 400
    questions = data.get("questions") or []
    if not questions:
        return jsonify(error="Нужен хотя бы один вопрос"), 400

    quiz = Quiz(title=data["title"], course_id=data.get("course_id"), ai_generated=False)
    db.session.add(quiz)
    db.session.flush()
    for q in questions:
        if "text" not in q or "options" not in q or "correct_index" not in q:
            return jsonify(error="Вопрос: text, options, correct_index"), 400
        db.session.add(Question(
            quiz_id=quiz.id,
            text=q["text"],
            options=q["options"],
            correct_index=q["correct_index"],
            explanation=q.get("explanation", ""),
        ))
    db.session.commit()
    return jsonify(quiz.to_dict(with_answers=True)), 201


@quiz_bp.put("/<int:quiz_id>")
@admin_required
def update_quiz(quiz_id):
    quiz = Quiz.query.get_or_404(quiz_id)
    data = request.get_json(silent=True) or {}
    if "title" in data:
        quiz.title = data["title"]
    if "course_id" in data:
        quiz.course_id = data["course_id"]
    if "questions" in data:
        for old in list(quiz.questions):
            db.session.delete(old)
        for q in data["questions"]:
            db.session.add(Question(
                quiz_id=quiz.id,
                text=q["text"],
                options=q["options"],
                correct_index=q["correct_index"],
                explanation=q.get("explanation", ""),
            ))
    db.session.commit()
    return jsonify(quiz.to_dict(with_answers=True))


@quiz_bp.delete("/<int:quiz_id>")
@admin_required
def delete_quiz(quiz_id):
    db.session.delete(Quiz.query.get_or_404(quiz_id))
    db.session.commit()
    return jsonify(ok=True)
