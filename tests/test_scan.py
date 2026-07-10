import virustotal as vt


def test_status_offline(emp_client):
    data = emp_client.get("/api/scan/status").get_json()
    assert data["virustotal_configured"] is False
    assert "max_file_mb" in data


def test_scan_url_offline(emp_client):
    r = emp_client.post("/api/scan/url",
                        json={"url": "http://mts-verify-login.ru/confirm"})
    assert r.status_code == 200
    data = r.get_json()
    assert data["verdict"] in ("clean", "suspicious", "malicious", "unknown")
    assert isinstance(data["red_flags"], list)
    assert "scan_id" in data


def test_scan_url_empty(emp_client):
    assert emp_client.post("/api/scan/url", json={"url": ""}).status_code == 400


def test_scan_requires_auth(client):
    assert client.post("/api/scan/url", json={"url": "http://x.ru"}).status_code == 401


def test_heuristic_flags_detects_ip_url():
    flags = vt.heuristic_url_flags("http://185.12.3.4/login")
    assert isinstance(flags, list)
    assert flags, "URL с IP-адресом должен давать эвристические флаги"
