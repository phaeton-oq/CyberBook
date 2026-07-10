"""
Единая логика Security Score и бейджей.
Используется фишинг-движком и модулем квизов, чтобы очки считались одинаково.
"""
from extensions import db
from models import Badge

# на сколько двигаем score за события
PHISH_CORRECT = +8
PHISH_WRONG = -12
QUIZ_BONUS_MAX = +10  # умножается на долю правильных


def clamp(v, lo=0, hi=100):
    return max(lo, min(hi, v))


def apply_delta(user, delta):
    user.security_score = clamp((user.security_score or 50) + delta)
    db.session.add(user)


def award_badge(user, name, icon="🛡️"):
    """Выдаёт бейдж, если его ещё нет. Возвращает True, если выдали новый."""
    exists = Badge.query.filter_by(user_id=user.id, name=name).first()
    if exists:
        return False
    db.session.add(Badge(user_id=user.id, name=name, icon=icon))
    return True


def check_score_badges(user):
    """Начисляет бейджи по достижению порогов score."""
    new = []
    if user.security_score >= 80 and award_badge(user, "Кибер-Страж", "🛡️"):
        new.append("Кибер-Страж")
    if user.security_score >= 95 and award_badge(user, "Неприступный", "🏆"):
        new.append("Неприступный")
    return new
