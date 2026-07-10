"""
CyberBook — модели данных (SQLite через SQLAlchemy).

Это ОБЩИЙ КОНТРАКТ для всей команды. Если меняешь модель — предупреди в чате,
т.к. на неё завязаны фронт (JSON-поля) и другие бэкенд-модули.

Владельцы:
  - User, PhishingEmail, PhishingResult, Badge  -> ядро (я + phaeton)
  - Course, Quiz, Question, QuizAttempt          -> второй бэкенд
"""
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin

from extensions import db


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), default="employee")  # employee | admin
    department = db.Column(db.String(80), default="Общий")
    security_score = db.Column(db.Integer, default=50)  # 0..100, «здоровье» сотрудника
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    quiz_attempts = db.relationship("QuizAttempt", backref="user", lazy=True)
    phishing_results = db.relationship("PhishingResult", backref="user", lazy=True)
    badges = db.relationship("Badge", backref="user", lazy=True)

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
            "badges": [b.to_dict() for b in self.badges],
        }


class Course(db.Model):
    __tablename__ = "courses"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(160), nullable=False)
    description = db.Column(db.Text, default="")
    content = db.Column(db.Text, default="")        # текст урока (можно markdown)
    video_url = db.Column(db.String(300), default="")
    topic = db.Column(db.String(80), default="Общее")  # тема (для персонализации квизов)
    order = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    quizzes = db.relationship("Quiz", backref="course", lazy=True)

    def to_dict(self, with_content=False):
        data = {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "video_url": self.video_url,
            "topic": self.topic,
            "order": self.order,
        }
        if with_content:
            data["content"] = self.content
            data["quizzes"] = [{"id": q.id, "title": q.title} for q in self.quizzes]
        return data


class Quiz(db.Model):
    __tablename__ = "quizzes"

    id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey("courses.id"), nullable=True)
    title = db.Column(db.String(160), nullable=False)
    ai_generated = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    questions = db.relationship("Question", backref="quiz", lazy=True,
                                cascade="all, delete-orphan")

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
    options = db.Column(db.JSON, nullable=False)      # ["A", "B", "C", "D"]
    correct_index = db.Column(db.Integer, nullable=False)
    explanation = db.Column(db.Text, default="")

    def to_dict(self, with_answers=False):
        data = {
            "id": self.id,
            "text": self.text,
            "options": self.options,
        }
        if with_answers:
            data["correct_index"] = self.correct_index
            data["explanation"] = self.explanation
        return data


class QuizAttempt(db.Model):
    __tablename__ = "quiz_attempts"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    quiz_id = db.Column(db.Integer, db.ForeignKey("quizzes.id"), nullable=False)
    score = db.Column(db.Integer, default=0)          # % правильных
    total = db.Column(db.Integer, default=0)
    correct = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "quiz_id": self.quiz_id,
            "score": self.score,
            "total": self.total,
            "correct": self.correct,
            "created_at": self.created_at.isoformat(),
        }


class PhishingEmail(db.Model):
    __tablename__ = "phishing_emails"

    id = db.Column(db.Integer, primary_key=True)
    sender = db.Column(db.String(160), nullable=False)     # "no-reply@mts-security.ru"
    sender_name = db.Column(db.String(120), default="")    # "Служба безопасности МТС"
    subject = db.Column(db.String(200), nullable=False)
    body = db.Column(db.Text, nullable=False)              # HTML/текст письма
    is_phishing = db.Column(db.Boolean, default=True)      # бывают и легитимные письма!
    red_flags = db.Column(db.JSON, default=list)           # ["срочность", "чужой домен", ...]
    difficulty = db.Column(db.String(20), default="medium")  # easy | medium | hard
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
        if reveal:  # только после ответа сотрудника
            data["is_phishing"] = self.is_phishing
            data["red_flags"] = self.red_flags
        return data


class PhishingResult(db.Model):
    __tablename__ = "phishing_results"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    email_id = db.Column(db.Integer, db.ForeignKey("phishing_emails.id"), nullable=False)
    action = db.Column(db.String(20), nullable=False)   # reported | clicked | trusted
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
