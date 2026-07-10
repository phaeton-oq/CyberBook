"""
Статистика и аналитика (админ-дашборд) + лидерборд.
БАЗА готова — второй бэкенд расширяет (графики по датам, срезы по отделам, экспорт CSV).

  GET /api/stats/overview     -> сводка по компании (admin)
  GET /api/stats/leaderboard  -> топ сотрудников по security_score
  GET /api/stats/me           -> личная статистика текущего сотрудника
"""
from flask import Blueprint, jsonify
from flask_login import login_required, current_user
from sqlalchemy import func

from extensions import db
from models import User, QuizAttempt, PhishingResult

stats_bp = Blueprint("stats", __name__, url_prefix="/api/stats")


@stats_bp.get("/overview")
@login_required
def overview():
    if current_user.role != "admin":
        return jsonify(error="Только для админа"), 403

    total_users = User.query.filter_by(role="employee").count()
    avg_score = db.session.query(func.avg(User.security_score))\
        .filter(User.role == "employee").scalar() or 0

    phish_total = PhishingResult.query.count()
    phish_caught = PhishingResult.query.filter_by(correct=True).count()
    phish_failed = phish_total - phish_caught
    catch_rate = round(100 * phish_caught / phish_total) if phish_total else 0

    quiz_attempts = QuizAttempt.query.count()
    avg_quiz = db.session.query(func.avg(QuizAttempt.score)).scalar() or 0

    # срез по отделам
    dept_rows = db.session.query(
        User.department, func.avg(User.security_score), func.count(User.id)
    ).filter(User.role == "employee").group_by(User.department).all()
    departments = [
        {"department": d, "avg_score": round(s or 0), "count": c}
        for d, s, c in dept_rows
    ]

    # кто в зоне риска (низкий score)
    at_risk = [
        u.to_dict()
        for u in User.query.filter(User.role == "employee",
                                   User.security_score < 50)
        .order_by(User.security_score).limit(10).all()
    ]

    return jsonify({
        "total_users": total_users,
        "avg_security_score": round(avg_score),
        "phishing": {
            "total": phish_total,
            "caught": phish_caught,
            "failed": phish_failed,
            "catch_rate": catch_rate,
        },
        "quiz": {
            "attempts": quiz_attempts,
            "avg_score": round(avg_quiz),
        },
        "departments": departments,
        "at_risk": at_risk,
    })


@stats_bp.get("/leaderboard")
@login_required
def leaderboard():
    users = User.query.filter_by(role="employee")\
        .order_by(User.security_score.desc()).limit(20).all()
    return jsonify([
        {
            "rank": i + 1,
            "name": u.name,
            "department": u.department,
            "security_score": u.security_score,
            "badges": [b.to_dict() for b in u.badges],
        }
        for i, u in enumerate(users)
    ])


@stats_bp.get("/me")
@login_required
def my_stats():
    attempts = QuizAttempt.query.filter_by(user_id=current_user.id).all()
    phish = PhishingResult.query.filter_by(user_id=current_user.id).all()
    phish_caught = sum(1 for p in phish if p.correct)

    return jsonify({
        "security_score": current_user.security_score,
        "quiz_attempts": len(attempts),
        "avg_quiz_score": round(sum(a.score for a in attempts) / len(attempts)) if attempts else 0,
        "phishing_seen": len(phish),
        "phishing_caught": phish_caught,
        "badges": [b.to_dict() for b in current_user.badges],
    })
