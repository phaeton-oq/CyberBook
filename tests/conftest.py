"""
Общая инфраструктура тестов.

Поднимаем приложение на временной SQLite-базе, AI (Cerebras) и VirusTotal
намеренно НЕ сконфигурированы — код уходит в детерминированные fallback'и,
так что тесты не ходят в сеть и не зависят от ключей.
"""
import os
import tempfile

import pytest

from config import Config


class TestConfig(Config):
    TESTING = True
    CEREBRAS_API_KEY = ""      # -> ai._get_client() вернёт None -> fallback
    VIRUSTOTAL_API_KEY = ""    # -> vt.is_configured() == False
    SECRET_KEY = "test-secret"


def _seed(db):
    """Минимальный детерминированный набор данных (без random)."""
    from models import Course, PhishingEmail, Question, Quiz, User

    admin = User(name="Тест Админ", email="admin@test.ru", role="admin",
                 department="СБ", security_score=100)
    admin.set_password("adminpass")
    db.session.add(admin)

    emp = User(name="Тест Сотрудник", email="emp@test.ru", role="employee",
               department="Продажи", security_score=50, points=0)
    emp.set_password("emppass")
    db.session.add(emp)

    course = Course(title="Фишинг", description="", topic="Фишинг", order=1)
    db.session.add(course)
    db.session.flush()

    quiz = Quiz(title="Квиз: фишинг", course_id=course.id)
    db.session.add(quiz)
    db.session.flush()
    questions = [
        ("Пришло письмо с чужого домена с просьбой ввести пароль. Действия?",
         ["Ввести пароль", "Не переходить, сообщить в СБ", "Переслать коллеге", "Ответить"], 1),
        ("Надёжный корпоративный пароль — это:",
         ["123456", "Длинная уникальная фраза + 2FA", "Имя отдела", "qwerty"], 1),
        ("Коллега в мессенджере просит срочно перевести деньги от имени директора:",
         ["Перевести", "Проверить по officiальному каналу", "Игнор навсегда", "Дать реквизиты"], 1),
    ]
    for text, opts, ci in questions:
        db.session.add(Question(quiz_id=quiz.id, text=text, options=opts,
                                correct_index=ci, explanation="разбор"))

    db.session.add(PhishingEmail(
        sender="alert@mts-verify.ru", sender_name="Псевдо-СБ",
        subject="СРОЧНО: подтвердите доступ", body="Перейдите по ссылке...",
        is_phishing=True, difficulty="easy",
        red_flags=["Чужой домен", "Срочность"],
    ))
    db.session.add(PhishingEmail(
        sender="hr@mts.ru", sender_name="Отдел кадров",
        subject="График отпусков", body="Проверьте свои даты.",
        is_phishing=False, difficulty="medium", red_flags=[],
    ))
    db.session.commit()


@pytest.fixture
def app():
    from app import create_app
    from extensions import db

    db_fd, db_path = tempfile.mkstemp(suffix=".db")

    class Cfg(TestConfig):
        SQLALCHEMY_DATABASE_URI = f"sqlite:///{db_path}"

    application = create_app(Cfg)
    with application.app_context():
        db.create_all()
        _seed(db)
    yield application

    os.close(db_fd)
    try:
        os.unlink(db_path)
    except PermissionError:
        pass


@pytest.fixture
def client(app):
    return app.test_client()


def _login(client, email, password):
    return client.post("/api/auth/login", json={"email": email, "password": password})


@pytest.fixture
def emp_client(client):
    _login(client, "emp@test.ru", "emppass")
    return client


@pytest.fixture
def admin_client(client):
    _login(client, "admin@test.ru", "adminpass")
    return client
