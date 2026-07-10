def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.get_json()["status"] == "ok"


def test_me_requires_auth(client):
    assert client.get("/api/auth/me").status_code == 401


def test_login_ok(client):
    r = client.post("/api/auth/login", json={"email": "emp@test.ru", "password": "emppass"})
    assert r.status_code == 200
    data = r.get_json()
    assert data["email"] == "emp@test.ru"
    assert data["role"] == "employee"


def test_login_bad_password(client):
    r = client.post("/api/auth/login", json={"email": "emp@test.ru", "password": "wrong"})
    assert r.status_code == 401


def test_register_and_me(client):
    r = client.post("/api/auth/register", json={
        "name": "Новый", "email": "new@test.ru", "password": "pass12345", "department": "IT",
    })
    assert r.status_code == 201
    # после регистрации сессия активна
    me = client.get("/api/auth/me")
    assert me.status_code == 200
    assert me.get_json()["email"] == "new@test.ru"


def test_register_duplicate(client):
    payload = {"name": "Дубль", "email": "emp@test.ru", "password": "pass12345"}
    assert client.post("/api/auth/register", json=payload).status_code == 409


def test_logout(emp_client):
    assert emp_client.post("/api/auth/logout").status_code == 200
    assert emp_client.get("/api/auth/me").status_code == 401
