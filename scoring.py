from extensions import db
from models import Badge, Course, CourseProgress, PhishingResult, QuizAttempt

PHISH_CORRECT = 8
PHISH_WRONG = -12
QUIZ_BONUS_MAX = 10
LESSON_COMPLETE = 3
COURSE_COMPLETE = 8

POINTS_QUIZ_PER_CORRECT = 10
POINTS_PHISH_CORRECT = 15
POINTS_LESSON = 20
POINTS_COURSE = 50


def clamp(v, lo=0, hi=100):
    return max(lo, min(hi, v))


def apply_delta(user, delta):
    user.security_score = clamp((user.security_score or 50) + delta)
    db.session.add(user)


def add_points(user, amount):
    user.points = (user.points or 0) + max(0, amount)
    db.session.add(user)


def award_badge(user, name, icon="🛡️"):
    if Badge.query.filter_by(user_id=user.id, name=name).first():
        return False
    db.session.add(Badge(user_id=user.id, name=name, icon=icon))
    return True


def check_score_badges(user):
    earned = []
    if user.security_score >= 80 and award_badge(user, "Кибер-Страж", "🛡️"):
        earned.append("Кибер-Страж")
    if user.security_score >= 95 and award_badge(user, "Неприступный", "🏆"):
        earned.append("Неприступный")
    return earned


def check_activity_badges(user):
    earned = []
    if QuizAttempt.query.filter_by(user_id=user.id).count() >= 3:
        if award_badge(user, "Знаток квизов", "📝"):
            earned.append("Знаток квизов")
    done = CourseProgress.query.filter_by(user_id=user.id, completed=True).count()
    if done >= 1 and award_badge(user, "Ученик ИБ", "📚"):
        earned.append("Ученик ИБ")
    if done >= 3 and award_badge(user, "Мастер обучения", "🎖️"):
        earned.append("Мастер обучения")
    if (user.points or 0) >= 200 and award_badge(user, "Охотник за очками", "⭐"):
        earned.append("Охотник за очками")
    return earned


def user_stats(user):
    attempts = QuizAttempt.query.filter_by(user_id=user.id).all()
    phish = PhishingResult.query.filter_by(user_id=user.id).all()

    avg_quiz = (sum(a.score for a in attempts) / len(attempts)) if attempts else 50
    phish_total = len(phish)
    phish_caught = sum(1 for p in phish if p.correct)
    phish_clicked = sum(1 for p in phish if p.action == "clicked")
    catch_rate = (100 * phish_caught / phish_total) if phish_total else 50
    click_rate = (100 * phish_clicked / phish_total) if phish_total else 0

    total_courses = Course.query.count()
    completed = CourseProgress.query.filter_by(user_id=user.id, completed=True).count()
    course_pct = (100 * completed / total_courses) if total_courses else 0

    return {
        "avg_quiz": round(avg_quiz),
        "catch_rate": round(catch_rate),
        "click_rate": round(click_rate),
        "course_completion_pct": round(course_pct),
        "quiz_attempts": len(attempts),
        "phishing_seen": phish_total,
        "courses_completed": completed,
        "courses_total": total_courses,
    }


def compute_formula_score(user):
    s = user_stats(user)
    raw = (
        50
        + (s["avg_quiz"] - 50) * 0.35
        + (s["catch_rate"] - 50) * 0.35
        + s["course_completion_pct"] * 0.20
        - s["click_rate"] * 0.15
    )
    return clamp(round(raw))


def formula_breakdown(user):
    s = user_stats(user)
    return {
        "current_score": user.security_score,
        "formula_score": compute_formula_score(user),
        "components": {
            "base": 50,
            "quiz_contribution": round((s["avg_quiz"] - 50) * 0.35),
            "phishing_catch_contribution": round((s["catch_rate"] - 50) * 0.35),
            "course_completion_contribution": round(s["course_completion_pct"] * 0.20),
            "phishing_click_penalty": -round(s["click_rate"] * 0.15),
        },
        "inputs": s,
    }
