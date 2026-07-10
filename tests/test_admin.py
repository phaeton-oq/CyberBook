def test_update_own_profile(emp_client):
    r = emp_client.patch("/api/auth/me", json={"name": "Новое Имя", "department": "IT"})
    assert r.status_code == 200
    data = r.get_json()
    assert data["name"] == "Новое Имя"
    assert data["department"] == "IT"
    assert emp_client.get("/api/auth/me").get_json()["name"] == "Новое Имя"


def test_update_password_then_login(client):
    client.post("/api/auth/login", json={"email": "emp@test.ru", "password": "emppass"})
    assert client.patch("/api/auth/me", json={"password": "newpass123"}).status_code == 200
    client.post("/api/auth/logout")
    assert client.post("/api/auth/login", json={"email": "emp@test.ru", "password": "emppass"}).status_code == 401
    assert client.post("/api/auth/login", json={"email": "emp@test.ru", "password": "newpass123"}).status_code == 200


def test_update_email_conflict(emp_client):
    r = emp_client.patch("/api/auth/me", json={"email": "admin@test.ru"})
    assert r.status_code == 409


def test_update_profile_requires_auth(client):
    assert client.patch("/api/auth/me", json={"name": "X"}).status_code == 401


def test_admin_create_user(admin_client):
    r = admin_client.post("/api/admin/users", json={
        "name": "Новичок", "email": "newbie@test.ru", "password": "pass1234", "department": "HR",
    })
    assert r.status_code == 201
    assert r.get_json()["email"] == "newbie@test.ru"
    admin_client.post("/api/auth/logout")
    assert admin_client.post("/api/auth/login",
                             json={"email": "newbie@test.ru", "password": "pass1234"}).status_code == 200


def test_admin_create_duplicate(admin_client):
    payload = {"name": "Дубль", "email": "emp@test.ru", "password": "pass1234"}
    assert admin_client.post("/api/admin/users", json=payload).status_code == 409


def test_employee_cannot_create_user(emp_client):
    r = emp_client.post("/api/admin/users",
                        json={"name": "X", "email": "x@test.ru", "password": "pass1234"})
    assert r.status_code == 403


def test_admin_delete_employee(admin_client, app):
    from models import User
    with app.app_context():
        emp_id = User.query.filter_by(email="emp@test.ru").first().id
    r = admin_client.delete(f"/api/admin/users/{emp_id}")
    assert r.status_code == 200
    with app.app_context():
        assert User.query.filter_by(email="emp@test.ru").first() is None


def test_admin_cannot_delete_self(admin_client, app):
    from models import User
    with app.app_context():
        admin_id = User.query.filter_by(email="admin@test.ru").first().id
    assert admin_client.delete(f"/api/admin/users/{admin_id}").status_code == 400


def test_employee_cannot_delete(emp_client, app):
    from models import User
    with app.app_context():
        other = User.query.filter_by(email="admin@test.ru").first().id
    assert emp_client.delete(f"/api/admin/users/{other}").status_code == 403
