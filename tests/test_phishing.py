def _inbox(client):
    return client.get("/api/phishing/inbox").get_json()


def test_inbox_hides_verdict(emp_client):
    inbox = _inbox(emp_client)
    assert len(inbox) == 2
    for e in inbox:
        assert "is_phishing" not in e, "вердикт не должен раскрываться до ответа"
        assert "red_flags" not in e


def test_report_phishing_correct(emp_client):
    inbox = _inbox(emp_client)
    phish = next(e for e in inbox if "verify" in e["sender"])
    r = emp_client.post("/api/phishing/answer",
                        json={"email_id": phish["id"], "action": "reported"})
    assert r.status_code == 200
    data = r.get_json()
    assert data["correct"] is True
    assert data["is_phishing"] is True
    assert isinstance(data["red_flags"], list) and data["red_flags"]


def test_trust_legit_email_correct(emp_client):
    inbox = _inbox(emp_client)
    legit = next(e for e in inbox if e["sender"] == "hr@mts.ru")
    r = emp_client.post("/api/phishing/answer",
                        json={"email_id": legit["id"], "action": "trusted"})
    data = r.get_json()
    assert data["correct"] is True
    assert data["is_phishing"] is False


def test_no_double_scoring(emp_client):
    inbox = _inbox(emp_client)
    phish = next(e for e in inbox if "verify" in e["sender"])
    first = emp_client.post("/api/phishing/answer",
                           json={"email_id": phish["id"], "action": "reported"}).get_json()
    score_after_first = first["security_score"]
    second = emp_client.post("/api/phishing/answer",
                            json={"email_id": phish["id"], "action": "reported"}).get_json()
    assert second["security_score"] == score_after_first


def test_bad_action_rejected(emp_client):
    inbox = _inbox(emp_client)
    r = emp_client.post("/api/phishing/answer",
                        json={"email_id": inbox[0]["id"], "action": "нажать"})
    assert r.status_code == 400
