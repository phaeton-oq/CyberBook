from datetime import datetime

from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from extensions import db


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), default="employee")
    department = db.Column(db.String(80), default="Общий")
    security_score = db.Column(db.Integer, default=50)
    points = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    quiz_attempts = db.relationship("QuizAttempt", backref="user", lazy=True)
    phishing_results = db.relationship("PhishingResult", backref="user", lazy=True)
    badges = db.relationship("Badge", backref="user", lazy=True)
    course_progress = db.relationship("CourseProgress", backref="user", lazy=True)
    lesson_progress = db.relationship("LessonProgress", backref="user", lazy=True)

    def set_password(self, raw):
        self.password_hash = generate_password_hash(raw)

    def check_password(self, raw):
        return check_password_hash(self.password_hash, raw)

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "email": self.email,
            "role": self.role,
            "department": self.department,
            "security_score": self.security_score,
            "points": self.points or 0,
            "badges": [b.to_dict() for b in self.badges],
        }


class Course(db.Model):
    __tablename__ = "courses"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(160), nullable=False)
    description = db.Column(db.Text, default="")
    content = db.Column(db.Text, default="")
    video_url = db.Column(db.String(300), default="")
    topic = db.Column(db.String(80), default="Общее")
    order = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    quizzes = db.relationship("Quiz", backref="course", lazy=True)
    lessons = db.relationship(
        "Lesson", backref="course", lazy=True,
        cascade="all, delete-orphan", order_by="Lesson.order",
    )

    def to_dict(self, with_content=False, user_id=None):
        data = {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "video_url": self.video_url,
            "topic": self.topic,
            "order": self.order,
            "lesson_count": len(self.lessons),
        }
        if not with_content:
            return data

        data["content"] = self.content
        data["lessons"] = [l.to_dict() for l in self.lessons]
        data["quizzes"] = [{"id": q.id, "title": q.title} for q in self.quizzes]
        if user_id is None:
            return data

        done_lessons = {
            p.lesson_id for p in LessonProgress.query.filter_by(
                user_id=user_id, completed=True,
            ).all()
        }
        data["completed"] = CourseProgress.query.filter_by(
            user_id=user_id, course_id=self.id, completed=True,
        ).first() is not None
        for les in data["lessons"]:
            les["completed"] = les["id"] in done_lessons
        return data


class Lesson(db.Model):
    __tablename__ = "lessons"

    id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey("courses.id"), nullable=False)
    title = db.Column(db.String(160), nullable=False)
    content = db.Column(db.Text, default="")
    video_url = db.Column(db.String(300), default="")
    order = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "course_id": self.course_id,
            "title": self.title,
            "content": self.content,
            "video_url": self.video_url,
            "order": self.order,
        }


class CourseProgress(db.Model):
    __tablename__ = "course_progress"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    course_id = db.Column(db.Integer, db.ForeignKey("courses.id"), nullable=False)
    completed = db.Column(db.Boolean, default=True)
    completed_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (db.UniqueConstraint("user_id", "course_id", name="uq_course_progress"),)

    def to_dict(self):
        return {
            "course_id": self.course_id,
            "completed": self.completed,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }


class LessonProgress(db.Model):
    __tablename__ = "lesson_progress"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    lesson_id = db.Column(db.Integer, db.ForeignKey("lessons.id"), nullable=False)
    completed = db.Column(db.Boolean, default=True)
    completed_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (db.UniqueConstraint("user_id", "lesson_id", name="uq_lesson_progress"),)

    def to_dict(self):
        return {
            "lesson_id": self.lesson_id,
            "completed": self.completed,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }


class Quiz(db.Model):
    __tablename__ = "quizzes"

    id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey("courses.id"), nullable=True)
    title = db.Column(db.String(160), nullable=False)
    ai_generated = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    questions = db.relationship(
        "Question", backref="quiz", lazy=True, cascade="all, delete-orphan",
    )

    def to_dict(self, with_answers=False):
        return {
            "id": self.id,
            "course_id": self.course_id,
            "title": self.title,
            "ai_generated": self.ai_generated,
            "questions": [q.to_dict(with_answers=with_answers) for q in self.questions],
        }


class Question(db.Model):
    __tablename__ = "questions"

    id = db.Column(db.Integer, primary_key=True)
    quiz_id = db.Column(db.Integer, db.ForeignKey("quizzes.id"), nullable=False)
    text = db.Column(db.Text, nullable=False)
    options = db.Column(db.JSON, nullable=False)
    correct_index = db.Column(db.Integer, nullable=False)
    explanation = db.Column(db.Text, default="")

    def to_dict(self, with_answers=False):
        data = {"id": self.id, "text": self.text, "options": self.options}
        if with_answers:
            data["correct_index"] = self.correct_index
            data["explanation"] = self.explanation
        return data


class QuizAttempt(db.Model):
    __tablename__ = "quiz_attempts"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    quiz_id = db.Column(db.Integer, db.ForeignKey("quizzes.id"), nullable=False)
    score = db.Column(db.Integer, default=0)
    total = db.Column(db.Integer, default=0)
    correct = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    quiz = db.relationship("Quiz", backref="attempts", lazy=True)

    def to_dict(self, with_quiz=False):
        data = {
            "id": self.id,
            "user_id": self.user_id,
            "quiz_id": self.quiz_id,
            "score": self.score,
            "total": self.total,
            "correct": self.correct,
            "created_at": self.created_at.isoformat(),
        }
        if with_quiz and self.quiz:
            data["quiz_title"] = self.quiz.title
            data["course_id"] = self.quiz.course_id
        return data


class PhishingEmail(db.Model):
    __tablename__ = "phishing_emails"

    id = db.Column(db.Integer, primary_key=True)
    sender = db.Column(db.String(160), nullable=False)
    sender_name = db.Column(db.String(120), default="")
    subject = db.Column(db.String(200), nullable=False)
    body = db.Column(db.Text, nullable=False)
    is_phishing = db.Column(db.Boolean, default=True)
    red_flags = db.Column(db.JSON, default=list)
    difficulty = db.Column(db.String(20), default="medium")
    ai_generated = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self, reveal=False):
        data = {
            "id": self.id,
            "sender": self.sender,
            "sender_name": self.sender_name,
            "subject": self.subject,
            "body": self.body,
            "difficulty": self.difficulty,
        }
        if reveal:
            data["is_phishing"] = self.is_phishing
            data["red_flags"] = self.red_flags
        return data


class PhishingResult(db.Model):
    __tablename__ = "phishing_results"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    email_id = db.Column(db.Integer, db.ForeignKey("phishing_emails.id"), nullable=False)
    action = db.Column(db.String(20), nullable=False)
    correct = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "email_id": self.email_id,
            "action": self.action,
            "correct": self.correct,
            "created_at": self.created_at.isoformat(),
        }


class Badge(db.Model):
    __tablename__ = "badges"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    name = db.Column(db.String(80), nullable=False)
    icon = db.Column(db.String(16), default="🛡️")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {"name": self.name, "icon": self.icon}


class ThreatScan(db.Model):
    __tablename__ = "threat_scans"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    scan_type = db.Column(db.String(16), nullable=False)
    target = db.Column(db.String(500), nullable=False)
    verdict = db.Column(db.String(20), default="unknown")
    vt_stats = db.Column(db.JSON, default=dict)
    vt_available = db.Column(db.Boolean, default=False)
    ai_review = db.Column(db.Text, default="")
    ai_used = db.Column(db.Boolean, default=False)
    red_flags = db.Column(db.JSON, default=list)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship("User", backref=db.backref("threat_scans", lazy=True))

    def to_dict(self):
        return {
            "id": self.id,
            "scan_type": self.scan_type,
            "target": self.target,
            "verdict": self.verdict,
            "vt_stats": self.vt_stats,
            "vt_available": self.vt_available,
            "ai_review": self.ai_review,
            "ai_used": self.ai_used,
            "red_flags": self.red_flags,
            "created_at": self.created_at.isoformat(),
        }
