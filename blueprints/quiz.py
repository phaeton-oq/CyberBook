"""
Квизы: получение, прохождение, генерация через AI.
БАЗА готова — второй бэкенд расширяет (персонализация по слабым темам, история попыток).

  GET  /api/quiz/<id>          -> квиз БЕЗ правильных ответов
  POST /api/quiz/<id>/submit   -> {answers: [idx,...]} -> результат + разбор + score
  POST /api/quiz/generate      -> {topic, n?, difficulty?, course_id?} -> сгенерировать квиз (AI)
"""
from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user

from extensions import db
from models import Quiz, Question, QuizAttempt
import scoring
import ai

quiz_bp = Blueprint("quiz", __name__, url_prefix="/api/quiz")


@quiz_bp.get("/<int:quiz_id>")
@login_required
def get_quiz(quiz_id):
    quiz = Quiz.query.get_or_404(quiz_id)
    return jsonify(quiz.to_dict(with_answers=False))


@quiz_bp.post("/<int:quiz_id>/submit")
@login_required
def submit(quiz_id):
    quiz = Quiz.query.get_or_404(quiz_id)
    data = request.get_json(silent=True) or {}
    answers = data.get("answers") or []

    questions = quiz.questions
    total = len(questions)
    correct = 0
    review = []
    for i, q in enumerate(questions):
        chosen = answers[i] if i < len(answers) else None
        is_ok = chosen == q.correct_index
        if is_ok:
            correct += 1
        review.append({
            "question_id": q.id,
            "chosen": chosen,
            "correct_index": q.correct_index,
            "is_correct": is_ok,
            "explanation": q.explanation,
        })

    score = round(100 * correct / total) if total else 0

    db.session.add(QuizAttempt(
        user_id=current_user.id, quiz_id=quiz.id,
        score=score, total=total, correct=correct,
    ))
    # бонус к security_score за долю правильных
    scoring.apply_delta(current_user, round(scoring.QUIZ_BONUS_MAX * correct / total) if total else 0)
    new_badges = scoring.check_score_badges(current_user)
    if score == 100 and scoring.award_badge(current_user, "Отличник ИБ", "🎓"):
        new_badges.append("Отличник ИБ")
    db.session.commit()

    return jsonify({
        "score": score,
        "correct": correct,
        "total": total,
        "review": review,
        "security_score": current_user.security_score,
        "new_badges": new_badges,
    })


@quiz_bp.post("/generate")
@login_required
def generate():
    """Генерация квиза через Cerebras и сохранение в базу."""
    data = request.get_json(silent=True) or {}
    topic = data.get("topic", "общая кибербезопасность")
    n = int(data.get("n", 4))
    difficulty = data.get("difficulty", "medium")
    course_id = data.get("course_id")

    payload, used_ai = ai.generate_quiz(topic=topic, n=n, difficulty=difficulty)

    quiz = Quiz(title=payload.get("title", f"Квиз: {topic}"),
                course_id=course_id, ai_generated=True)
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
