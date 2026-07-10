"""
AI-ассистент (моя часть).

  POST /api/assistant/chat  -> {message, history?} -> {reply, ai}

Ассистент получает КОНТЕКСТ сотрудника (его слабые темы, security score,
проваленные фишинги) и подстраивает советы — это делает его персональным
AI-тренером, а не просто чат-ботом.
"""
from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user

from models import QuizAttempt, PhishingResult, PhishingEmail
import ai

assistant_bp = Blueprint("assistant", __name__, url_prefix="/api/assistant")


def build_user_context(user):
    """Короткая справка о сотруднике для персонализации ответов ассистента."""
    lines = [
        f"- Имя: {user.name}, отдел: {user.department}.",
        f"- Security Score: {user.security_score}/100 "
        f"({'высокий' if user.security_score >= 80 else 'средний' if user.security_score >= 50 else 'низкий, в зоне риска'}).",
    ]

    # средний балл по квизам
    attempts = QuizAttempt.query.filter_by(user_id=user.id).all()
    if attempts:
        avg = round(sum(a.score for a in attempts) / len(attempts))
        lines.append(f"- Средний балл по квизам: {avg}%.")
        if avg < 70:
            lines.append("- Слабо справляется с квизами — объясняй подробнее.")

    # проваленные фишинги -> слабые темы
    failed = (
        PhishingResult.query
        .filter_by(user_id=user.id, correct=False)
        .all()
    )
    if failed:
        subjects = []
        for r in failed[:3]:
            em = PhishingEmail.query.get(r.email_id)
            if em:
                subjects.append(f"«{em.subject}»")
        if subjects:
            lines.append(
                "- Не распознал фишинг в письмах: " + ", ".join(subjects) +
                ". Обрати внимание на эти сценарии."
            )
    else:
        lines.append("- Пока не попадался на фишинг — хвали и держи в тонусе.")

    return "\n".join(lines)


@assistant_bp.post("/chat")
@login_required
def chat():
    data = request.get_json(silent=True) or {}
    message = (data.get("message") or "").strip()
    if not message:
        return jsonify(error="Пустое сообщение"), 400

    history = data.get("history") or []
    clean = [
        {"role": h["role"], "content": h["content"]}
        for h in history
        if isinstance(h, dict) and h.get("role") in ("user", "assistant") and h.get("content")
    ]

    ctx = build_user_context(current_user)
    reply, used_ai = ai.assistant_reply(message, history=clean, user_context=ctx)
    return jsonify({"reply": reply, "ai": used_ai})
