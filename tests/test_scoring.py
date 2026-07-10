"""Юнит-тесты логики Security Score, очков и бейджей."""
import scoring


def test_clamp():
    assert scoring.clamp(150) == 100
    assert scoring.clamp(-10) == 0
    assert scoring.clamp(42) == 42


def test_apply_delta_bounds(app):
    from extensions import db
    from models import User
    with app.app_context():
        u = User.query.filter_by(email="emp@test.ru").first()
        u.security_score = 95
        scoring.apply_delta(u, 20)
        assert u.security_score == 100  # не превышает 100
        scoring.apply_delta(u, -200)
        assert u.security_score == 0    # не уходит ниже 0


def test_add_points_never_negative(app):
    from models import User
    with app.app_context():
        u = User.query.filter_by(email="emp@test.ru").first()
        start = u.points or 0
        scoring.add_points(u, 30)
        assert u.points == start + 30
        scoring.add_points(u, -999)     # отрицательное игнорируется
        assert u.points == start + 30


def test_award_badge_idempotent(app):
    from extensions import db
    from models import User
    with app.app_context():
        u = User.query.filter_by(email="emp@test.ru").first()
        assert scoring.award_badge(u, "Тестовый", "🧪") is True
        db.session.commit()
        assert scoring.award_badge(u, "Тестовый", "🧪") is False  # второй раз не выдаём


def test_formula_score_in_range(app):
    from models import User
    with app.app_context():
        u = User.query.filter_by(email="emp@test.ru").first()
        score = scoring.compute_formula_score(u)
        assert 0 <= score <= 100
        breakdown = scoring.formula_breakdown(u)
        assert "components" in breakdown and "inputs" in breakdown
