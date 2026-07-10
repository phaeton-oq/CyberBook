def test_my_stats(emp_client):
    r = emp_client.get("/api/stats/me")
    assert r.status_code == 200
    data = r.get_json()
    assert "security_score" in data


def test_leaderboard(emp_client):
    r = emp_client.get("/api/stats/leaderboard")
    assert r.status_code == 200
    assert isinstance(r.get_json(), list)


def test_overview_forbidden_for_employee(emp_client):
    assert emp_client.get("/api/stats/overview").status_code == 403


def test_overview_ok_for_admin(admin_client):
    r = admin_client.get("/api/stats/overview")
    assert r.status_code == 200
    data = r.get_json()
    assert "total_users" in data


def test_admin_endpoints_reject_employee(emp_client):
    assert emp_client.get("/api/stats/timeline").status_code == 403
    assert emp_client.get("/api/stats/users").status_code == 403
