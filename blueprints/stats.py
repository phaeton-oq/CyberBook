import csv
import io
from datetime import datetime, timedelta
from pathlib import Path

from flask import Blueprint, Response, jsonify
from flask_login import current_user, login_required
from sqlalchemy import Integer, cast, func

from blueprints.helpers import admin_required
from extensions import db
from models import Course, CourseProgress, LessonProgress, PhishingResult, QuizAttempt, User
import scoring

stats_bp = Blueprint("stats", __name__, url_prefix="/api/stats")


def _user_report(user):
    attempts = QuizAttempt.query.filter_by(user_id=user.id)\
        .order_by(QuizAttempt.created_at.desc()).all()
    phish = PhishingResult.query.filter_by(user_id=user.id).all()
    caught = sum(1 for p in phish if p.correct)
    clicked = sum(1 for p in phish if p.action == "clicked")
    total_phish = len(phish)

    return {
        "user": user.to_dict(),
        "security_score": user.security_score,
        "points": user.points or 0,
        "formula": scoring.formula_breakdown(user),
        "quiz": {
            "attempts": len(attempts),
            "avg_score": round(sum(a.score for a in attempts) / len(attempts)) if attempts else 0,
            "history": [a.to_dict(with_quiz=True) for a in attempts[:20]],
        },
        "phishing": {
            "seen": total_phish,
            "caught": caught,
            "clicked": clicked,
            "click_rate_pct": round(100 * clicked / total_phish) if total_phish else 0,
            "catch_rate_pct": round(100 * caught / total_phish) if total_phish else 0,
        },
        "courses_completed": CourseProgress.query.filter_by(user_id=user.id, completed=True).count(),
        "lessons_completed": LessonProgress.query.filter_by(user_id=user.id, completed=True).count(),
        "badges": [b.to_dict() for b in user.badges],
    }


@stats_bp.get("/overview")
@admin_required
def overview():
    employees = User.query.filter_by(role="employee").all()
    total_users = len(employees)
    phish_total = PhishingResult.query.count()
    phish_caught = PhishingResult.query.filter_by(correct=True).count()
    phish_clicked = PhishingResult.query.filter_by(action="clicked").count()
    total_courses = Course.query.count()
    progress_count = CourseProgress.query.filter_by(completed=True).count()

    dept_rows = db.session.query(
        User.department, func.avg(User.security_score), func.count(User.id),
    ).filter(User.role == "employee").group_by(User.department).all()

    return jsonify({
        "total_users": total_users,
        "avg_security_score": round(
            db.session.query(func.avg(User.security_score)).filter(User.role == "employee").scalar() or 0,
        ),
        "avg_formula_score": round(
            sum(scoring.compute_formula_score(u) for u in employees) / total_users,
        ) if total_users else 0,
        "phishing": {
            "total": phish_total,
            "caught": phish_caught,
            "failed": phish_total - phish_caught,
            "clicked": phish_clicked,
            "catch_rate": round(100 * phish_caught / phish_total) if phish_total else 0,
            "click_rate": round(100 * phish_clicked / phish_total) if phish_total else 0,
        },
        "quiz": {
            "attempts": QuizAttempt.query.count(),
            "avg_score": round(db.session.query(func.avg(QuizAttempt.score)).scalar() or 0),
        },
        "courses": {
            "total": total_courses,
            "completions": progress_count,
            "users_completed_any": db.session.query(
                func.count(func.distinct(CourseProgress.user_id)),
            ).filter(CourseProgress.completed.is_(True)).scalar() or 0,
            "completion_rate_pct": round(100 * progress_count / (total_users * total_courses))
            if total_users and total_courses else 0,
        },
        "departments": [
            {"department": d, "avg_score": round(s or 0), "count": c}
            for d, s, c in dept_rows
        ],
        "at_risk": [
            u.to_dict() for u in User.query.filter(
                User.role == "employee", User.security_score < 50,
            ).order_by(User.security_score).limit(10).all()
        ],
    })


@stats_bp.get("/leaderboard")
@login_required
def leaderboard():
    users = User.query.filter_by(role="employee")\
        .order_by(User.security_score.desc(), User.points.desc()).limit(20).all()
    return jsonify([
        {
            "rank": i + 1,
            "user_id": u.id,
            "name": u.name,
            "department": u.department,
            "security_score": u.security_score,
            "points": u.points or 0,
            "badges": [b.to_dict() for b in u.badges],
            "formula_score": scoring.compute_formula_score(u),
        }
        for i, u in enumerate(users)
    ])


@stats_bp.get("/me")
@login_required
def my_stats():
    attempts = QuizAttempt.query.filter_by(user_id=current_user.id).all()
    phish = PhishingResult.query.filter_by(user_id=current_user.id).all()
    return jsonify({
        "security_score": current_user.security_score,
        "points": current_user.points or 0,
        "formula": scoring.formula_breakdown(current_user),
        "quiz_attempts": len(attempts),
        "avg_quiz_score": round(sum(a.score for a in attempts) / len(attempts)) if attempts else 0,
        "quiz_history": [a.to_dict(with_quiz=True) for a in attempts[:10]],
        "phishing_seen": len(phish),
        "phishing_caught": sum(1 for p in phish if p.correct),
        "phishing_clicked": sum(1 for p in phish if p.action == "clicked"),
        "courses_completed": CourseProgress.query.filter_by(
            user_id=current_user.id, completed=True,
        ).count(),
        "lessons_completed": LessonProgress.query.filter_by(
            user_id=current_user.id, completed=True,
        ).count(),
        "badges": [b.to_dict() for b in current_user.badges],
    })


@stats_bp.get("/timeline")
@admin_required
def timeline():
    since = datetime.utcnow() - timedelta(days=30)
    quiz = db.session.query(
        func.date(QuizAttempt.created_at).label("day"),
        func.count(QuizAttempt.id),
        func.avg(QuizAttempt.score),
    ).filter(QuizAttempt.created_at >= since).group_by("day").order_by("day").all()

    phish = db.session.query(
        func.date(PhishingResult.created_at).label("day"),
        func.count(PhishingResult.id),
        func.sum(cast(PhishingResult.correct, Integer)),
    ).filter(PhishingResult.created_at >= since).group_by("day").order_by("day").all()

    courses = db.session.query(
        func.date(CourseProgress.completed_at).label("day"),
        func.count(CourseProgress.id),
    ).filter(
        CourseProgress.completed.is_(True),
        CourseProgress.completed_at >= since,
    ).group_by("day").order_by("day").all()

    return jsonify({
        "days": 30,
        "quiz": [{"date": str(d), "attempts": c, "avg_score": round(s or 0)} for d, c, s in quiz],
        "phishing": [{"date": str(d), "answers": c, "caught": int(ok or 0)} for d, c, ok in phish],
        "course_completions": [{"date": str(d), "count": c} for d, c in courses],
    })


@stats_bp.get("/users")
@admin_required
def users_stats():
    total_courses = Course.query.count()
    rows = []
    for user in User.query.filter_by(role="employee").order_by(User.name).all():
        attempts = QuizAttempt.query.filter_by(user_id=user.id).all()
        phish = PhishingResult.query.filter_by(user_id=user.id).all()
        done = CourseProgress.query.filter_by(user_id=user.id, completed=True).count()
        rows.append({
            "id": user.id,
            "name": user.name,
            "email": user.email,
            "department": user.department,
            "security_score": user.security_score,
            "formula_score": scoring.compute_formula_score(user),
            "points": user.points or 0,
            "courses_completed": done,
            "courses_total": total_courses,
            "quiz_attempts": len(attempts),
            "avg_quiz_score": round(sum(a.score for a in attempts) / len(attempts)) if attempts else 0,
            "phishing_seen": len(phish),
            "phishing_clicked_pct": round(
                100 * sum(1 for p in phish if p.action == "clicked") / len(phish),
            ) if phish else 0,
            "completed_any_course": done > 0,
        })
    return jsonify(rows)


@stats_bp.get("/export/<int:user_id>")
@admin_required
def export_csv(user_id):
    user = User.query.get_or_404(user_id)
    if user.role == "admin":
        return jsonify(error="Отчёт только для сотрудников"), 400

    report = _user_report(user)
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["Отчёт CyberBook", datetime.utcnow().strftime("%Y-%m-%d %H:%M")])
    w.writerow(["Имя", user.name])
    w.writerow(["Email", user.email])
    w.writerow(["Отдел", user.department])
    w.writerow(["Security Score", report["security_score"]])
    w.writerow(["Очки", report["points"]])
    w.writerow(["Формульный Score", report["formula"]["formula_score"]])
    w.writerow([])
    w.writerow(["Попыток квизов", report["quiz"]["attempts"]])
    w.writerow(["Средний балл квизов", report["quiz"]["avg_score"]])
    w.writerow(["Фишинг просмотрено", report["phishing"]["seen"]])
    w.writerow(["Фишинг кликов %", report["phishing"]["click_rate_pct"]])
    w.writerow([])
    w.writerow(["Дата", "Квиз", "Балл", "Верно", "Всего"])
    for row in report["quiz"]["history"]:
        w.writerow([row["created_at"], row.get("quiz_title", ""), row["score"], row["correct"], row["total"]])

    return Response(
        "\ufeff" + buf.getvalue(),
        mimetype="text/csv; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename=cyberbook_{user.id}.csv"},
    )


@stats_bp.get("/export/<int:user_id>/pdf")
@admin_required
def export_pdf(user_id):
    user = User.query.get_or_404(user_id)
    if user.role == "admin":
        return jsonify(error="Отчёт только для сотрудников"), 400

    report = _user_report(user)
    try:
        from fpdf import FPDF
    except ImportError:
        return jsonify(error="Установите fpdf2"), 503

    font_path = Path(__file__).resolve().parent.parent / "assets" / "fonts" / "DejaVuSans.ttf"
    p = report["phishing"]

    pdf = FPDF()
    pdf.add_page()
    if font_path.exists():
        # DejaVu из assets/fonts — иначе кириллица в PDF не отрисуется
        pdf.add_font("DejaVu", "", str(font_path))
        pdf.set_font("DejaVu", size=16)
        pdf.cell(0, 12, "CyberBook: отчёт по сотруднику", ln=True)
        pdf.set_font("DejaVu", size=12)
        pdf.cell(0, 8, f"Сотрудник: {user.name} ({user.department})", ln=True)
        pdf.cell(0, 8, f"Email: {user.email}", ln=True)
        pdf.cell(0, 8, f"Security Score: {report['security_score']}/100", ln=True)
        pdf.cell(0, 8, f"Очки: {report['points']}", ln=True)
        pdf.cell(0, 8, f"Квизы: средний балл {report['quiz']['avg_score']}%", ln=True)
        pdf.cell(0, 8, f"Фишинг: {p['seen']} просмотров, {p['clicked']} кликов", ln=True)
    else:
        # запасной вариант без кириллицы, если шрифт не положили в репозиторий
        pdf.set_font("Helvetica", size=12)
        pdf.cell(0, 8, f"CyberBook report (user #{user.id})", ln=True)
        pdf.cell(0, 8, f"Score {report['security_score']}, ochki {report['points']}", ln=True)
        pdf.cell(0, 8, f"Kviz sredniy {report['quiz']['avg_score']}%", ln=True)
        pdf.cell(0, 8, f"Fishing: {p['seen']} prosmotrov, {p['clicked']} klikov", ln=True)

    return Response(
        bytes(pdf.output()),
        mimetype="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=cyberbook_{user.id}.pdf"},
    )
