from flask import Blueprint, jsonify, request
from flask_login import current_user, login_required

from models import PhishingEmail, PhishingResult, QuizAttempt
import ai

assistant_bp = Blueprint("assistant", __name__, url_prefix="/api/assistant")


def build_user_context(user):
    lines = [
        f"Имя: {user.name}, отдел: {user.department}.",
        f"Security Score: {user.security_score}/100.",
    ]
    attempts = QuizAttempt.query.filter_by(user_id=user.id).all()
    if attempts:
        avg = round(sum(a.score for a in attempts) / len(attempts))
        lines.append(f"Средний балл по квизам: {avg}%.")
        if avg < 70:
            lines.append("Слабые квизы, объясняй подробнее.")

    failed = PhishingResult.query.filter_by(user_id=user.id, correct=False).limit(3).all()
    if failed:
        subjects = []
        for row in failed:
            email = PhishingEmail.query.get(row.email_id)
            if email:
                subjects.append(email.subject)
        if subjects:
            lines.append("Пропустил фишинг: " + ", ".join(subjects))
    return "\n".join(lines)


@assistant_bp.post("/chat")
@login_required
def chat():
    data = request.get_json(silent=True) or {}
    message = (data.get("message") or "").strip()
    if not message:
        return jsonify(error="Пустое сообщение"), 400

    history = [
        {"role": h["role"], "content": h["content"]}
        for h in (data.get("history") or [])
        if isinstance(h, dict) and h.get("role") in ("user", "assistant") and h.get("content")
    ]
    reply, used_ai = ai.assistant_reply(
        message, history=history, user_context=build_user_context(current_user),
    )
    return jsonify({"reply": reply, "ai": used_ai})
