"""
Фишинг-движок (моя часть).

Флоу:
  GET  /api/phishing/inbox         -> список писем (без раскрытия is_phishing)
  GET  /api/phishing/email/<id>    -> одно письмо (без раскрытия)
  POST /api/phishing/answer        -> {email_id, action: reported|clicked|trusted}
                                       возвращает correct + разбор + red_flags + новый score
  POST /api/phishing/generate      -> (admin) сгенерировать новое письмо через AI
"""
from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user

from extensions import db
from models import PhishingEmail, PhishingResult
import scoring
import ai

phishing_bp = Blueprint("phishing", __name__, url_prefix="/api/phishing")


def admin_only():
    return current_user.is_authenticated and current_user.role == "admin"


@phishing_bp.get("/inbox")
@login_required
def inbox():
    """Инбокс сотрудника: письма + отметка, отвечал ли он уже."""
    emails = PhishingEmail.query.order_by(PhishingEmail.created_at.desc()).all()
    answered = {
        r.email_id: r
        for r in PhishingResult.query.filter_by(user_id=current_user.id).all()
    }
    result = []
    for e in emails:
        item = e.to_dict(reveal=False)
        r = answered.get(e.id)
        item["answered"] = r is not None
        item["was_correct"] = r.correct if r else None
        result.append(item)
    return jsonify(result)


@phishing_bp.get("/email/<int:email_id>")
@login_required
def get_email(email_id):
    e = PhishingEmail.query.get_or_404(email_id)
    r = PhishingResult.query.filter_by(
        user_id=current_user.id, email_id=email_id
    ).first()
    # если уже отвечал — раскрываем разбор
    return jsonify(e.to_dict(reveal=r is not None))


@phishing_bp.post("/answer")
@login_required
def answer():
    data = request.get_json(silent=True) or {}
    email_id = data.get("email_id")
    action = data.get("action")  # reported | clicked | trusted

    if action not in ("reported", "clicked", "trusted"):
        return jsonify(error="action: reported | clicked | trusted"), 400

    email = PhishingEmail.query.get_or_404(email_id)

    # правильный ответ: фишинг -> reported; легитимное -> trusted
    if email.is_phishing:
        correct = action == "reported"
    else:
        correct = action == "trusted"

    # не даём отвечать дважды
    existing = PhishingResult.query.filter_by(
        user_id=current_user.id, email_id=email_id
    ).first()
    if existing is None:
        db.session.add(PhishingResult(
            user_id=current_user.id, email_id=email_id,
            action=action, correct=correct,
        ))
        scoring.apply_delta(
            current_user,
            scoring.PHISH_CORRECT if correct else scoring.PHISH_WRONG,
        )
        new_badges = scoring.check_score_badges(current_user)
        # бейдж за первый пойманный фишинг
        if correct and email.is_phishing:
            if scoring.award_badge(current_user, "Охотник на фишинг", "🎣"):
                new_badges.append("Охотник на фишинг")
        db.session.commit()
    else:
        new_badges = []

    # обучающий момент от AI, если ошибся
    explanation = None
    if not correct:
        ctx = f"сотрудник выбрал действие '{action}' на письмо «{email.subject}» " \
              f"(это {'фишинг' if email.is_phishing else 'легитимное письмо'})"
        explanation, _ = ai.explain_mistake(ctx)

    return jsonify({
        "correct": correct,
        "is_phishing": email.is_phishing,
        "red_flags": email.red_flags,
        "explanation": explanation,
        "security_score": current_user.security_score,
        "new_badges": new_badges,
    })


@phishing_bp.post("/generate")
@login_required
def generate():
    """Админ генерирует новое фишинговое письмо через Cerebras и сохраняет в базу."""
    if not admin_only():
        return jsonify(error="Только для админа"), 403
    data = request.get_json(silent=True) or {}
    difficulty = data.get("difficulty", "medium")
    theme = data.get("theme", "корпоративная почта МТС")

    payload, used_ai = ai.generate_phishing(difficulty=difficulty, theme=theme)
    email = PhishingEmail(
        sender=payload.get("sender", "unknown@example.com"),
        sender_name=payload.get("sender_name", ""),
        subject=payload["subject"],
        body=payload["body"],
        is_phishing=payload.get("is_phishing", True),
        red_flags=payload.get("red_flags", []),
        difficulty=payload.get("difficulty", difficulty),
        ai_generated=True,
    )
    db.session.add(email)
    db.session.commit()
    return jsonify({"email": email.to_dict(reveal=True), "ai": used_ai}), 201
