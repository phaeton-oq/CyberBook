def _quiz_id(client):
    return client.get("/api/quiz").get_json()[0]["id"]


def test_quiz_hides_answers(emp_client):
    qid = _quiz_id(emp_client)
    quiz = emp_client.get(f"/api/quiz/{qid}").get_json()
    assert quiz["questions"], "квиз должен содержать вопросы"
    for q in quiz["questions"]:
        assert "correct_index" not in q, "правильный ответ не должен утекать на фронт"
        assert "options" in q


def test_quiz_submit_all_correct(emp_client):
    qid = _quiz_id(emp_client)
    r = emp_client.post(f"/api/quiz/{qid}/submit", json={"answers": [1, 1, 1]})
    assert r.status_code == 200
    data = r.get_json()
    assert data["score"] == 100
    assert data["correct"] == data["total"] == 3
    assert data["points"] > 0
    assert len(data["review"]) == 3
    assert all(item["is_correct"] for item in data["review"])


def test_quiz_submit_some_wrong(emp_client):
    qid = _quiz_id(emp_client)
    r = emp_client.post(f"/api/quiz/{qid}/submit", json={"answers": [0, 1, 0]})
    data = r.get_json()
    assert data["correct"] == 1
    assert data["score"] == 33


def test_quiz_requires_auth(client):
    qid = _quiz_id_via_admin(client)
    assert client.get(f"/api/quiz/{qid}").status_code == 401


def _quiz_id_via_admin(client):
    client.post("/api/auth/login", json={"email": "admin@test.ru", "password": "adminpass"})
    qid = client.get("/api/quiz").get_json()[0]["id"]
    client.post("/api/auth/logout")
    return qid
