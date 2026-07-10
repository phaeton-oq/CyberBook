"""
AI-ассистент (моя часть).

  POST /api/assistant/chat  -> {message, history?} -> {reply, ai}
"""
from flask import Blueprint, request, jsonify
from flask_login import login_required

import ai

assistant_bp = Blueprint("assistant", __name__, url_prefix="/api/assistant")


@assistant_bp.post("/chat")
@login_required
def chat():
    data = request.get_json(silent=True) or {}
    message = (data.get("message") or "").strip()
    if not message:
        return jsonify(error="Пустое сообщение"), 400

    history = data.get("history") or []
    # оставляем только валидные пары role/content
    clean = [
        {"role": h["role"], "content": h["content"]}
        for h in history
        if isinstance(h, dict) and h.get("role") in ("user", "assistant") and h.get("content")
    ]

    reply, used_ai = ai.assistant_reply(message, history=clean)
    return jsonify({"reply": reply, "ai": used_ai})
