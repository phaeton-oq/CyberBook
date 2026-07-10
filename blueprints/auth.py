from flask import Blueprint, request, jsonify
from flask_login import login_user, logout_user, login_required, current_user

from extensions import db
from models import User

auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")


@auth_bp.post("/register")
def register():
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    name = (data.get("name") or "").strip()
    password = data.get("password") or ""

    if not email or not password or not name:
        return jsonify(error="Нужны name, email и password"), 400
    if User.query.filter_by(email=email).first():
        return jsonify(error="Пользователь с таким email уже существует"), 409

    user = User(
        name=name,
        email=email,
        role="employee",
        department=(data.get("department") or "Общий").strip(),
    )
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    login_user(user)
    return jsonify(user.to_dict()), 201


@auth_bp.post("/login")
def login():
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""

    user = User.query.filter_by(email=email).first()
    if not user or not user.check_password(password):
        return jsonify(error="Неверный email или пароль"), 401

    login_user(user)
    return jsonify(user.to_dict())


@auth_bp.post("/logout")
@login_required
def logout():
    logout_user()
    return jsonify(ok=True)


@auth_bp.get("/me")
def me():
    if not current_user.is_authenticated:
        return jsonify(error="Не авторизован"), 401
    return jsonify(current_user.to_dict())


@auth_bp.patch("/me")
@login_required
def update_me():
    data = request.get_json(silent=True) or {}

    if "name" in data:
        name = (data.get("name") or "").strip()
        if not name:
            return jsonify(error="Имя не может быть пустым"), 400
        current_user.name = name

    if "department" in data:
        current_user.department = (data.get("department") or "Общий").strip()

    if "email" in data:
        email = (data.get("email") or "").strip().lower()
        if not email:
            return jsonify(error="Email не может быть пустым"), 400
        other = User.query.filter_by(email=email).first()
        if other and other.id != current_user.id:
            return jsonify(error="Этот email уже занят"), 409
        current_user.email = email

    if data.get("password"):
        if len(data["password"]) < 4:
            return jsonify(error="Пароль слишком короткий"), 400
        current_user.set_password(data["password"])

    db.session.commit()
    return jsonify(current_user.to_dict())
