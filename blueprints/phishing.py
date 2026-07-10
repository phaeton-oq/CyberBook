"""Симулятор фишинга."""
from flask import Blueprint, jsonify, request
from flask_login import current_user, login_required

from blueprints.helpers import admin_required
from extensions import db
from models import PhishingEmail, PhishingResult
import ai
import scoring

phishing_bp = Blueprint("phishing", __name__, url_prefix="/api/phishing")


@phishing_bp.get("/inbox")
@login_required
def inbox():
    emails = PhishingEmail.query.order_by(PhishingEmail.created_at.desc()).all()
    answered = {
        r.email_id: r
        for r in PhishingResult.query.filter_by(user_id=current_user.id).all()
    }
    out = []
    for email in emails:
        item = email.to_dict(reveal=False)
        result = answered.get(email.id)
        item["answered"] = result is not None
        item["was_correct"] = result.correct if result else None
        out.append(item)
    return jsonify(out)


@phishing_bp.get("/email/<int:email_id>")
@login_required
def get_email(email_id):
    email = PhishingEmail.query.get_or_404(email_id)
    answered = PhishingResult.query.filter_by(
        user_id=current_user.id, email_id=email_id,
    ).first()
    return jsonify(email.to_dict(reveal=answered is not None))


@phishing_bp.post("/answer")
@login_required
def answer():
    data = request.get_json(silent=True) or {}
    action = data.get("action")
    if action not in ("reported", "clicked", "trusted"):
        return jsonify(error="action: reported | clicked | trusted"), 400

    email = PhishingEmail.query.get_or_404(data.get("email_id"))
    correct = (action == "reported") if email.is_phishing else (action == "trusted")

    existing = PhishingResult.query.filter_by(
        user_id=current_user.id, email_id=email.id,
    ).first()
    badges = []
    if existing is None:
        db.session.add(PhishingResult(
            user_id=current_user.id, email_id=email.id,
            action=action, correct=correct,
        ))
        scoring.apply_delta(current_user, scoring.PHISH_CORRECT if correct else scoring.PHISH_WRONG)
        if correct:
            scoring.add_points(current_user, scoring.POINTS_PHISH_CORRECT)
        badges = scoring.check_score_badges(current_user)
        badges.extend(scoring.check_activity_badges(current_user))
        if correct and email.is_phishing and scoring.award_badge(current_user, "Охотник на фишинг", "🎣"):
            badges.append("Охотник на фишинг")
        db.session.commit()

    explanation = None
    if not correct:
        ctx = (
            f"действие '{action}' на письмо «{email.subject}» "
            f"({'фишинг' if email.is_phishing else 'легитимное'})"
        )
        explanation, _ = ai.explain_mistake(ctx)

    return jsonify({
        "correct": correct,
        "is_phishing": email.is_phishing,
        "red_flags": email.red_flags,
        "explanation": explanation,
        "security_score": current_user.security_score,
        "points": current_user.points or 0,
        "new_badges": badges,
    })


@phishing_bp.post("/generate")
@admin_required
def generate():
    data = request.get_json(silent=True) or {}
    payload, used_ai = ai.generate_phishing(
        difficulty=data.get("difficulty", "medium"),
        theme=data.get("theme", "корпоративная почта МТС"),
    )
    email = PhishingEmail(
        sender=payload.get("sender", "unknown@example.com"),
        sender_name=payload.get("sender_name", ""),
        subject=payload["subject"],
        body=payload["body"],
        is_phishing=payload.get("is_phishing", True),
        red_flags=payload.get("red_flags", []),
        difficulty=payload.get("difficulty", data.get("difficulty", "medium")),
        ai_generated=True,
    )
    db.session.add(email)
    db.session.commit()
    return jsonify({"email": email.to_dict(reveal=True), "ai": used_ai}), 201
