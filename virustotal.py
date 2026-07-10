import base64
import hashlib
import time
from urllib.parse import urlparse

import httpx
from flask import current_app

# обёртка над VT API v3; без ключа в .env все функции возвращают None
VT_BASE = "https://www.virustotal.com/api/v3"
RISKY_EXTENSIONS = {"exe", "scr", "bat", "cmd", "ps1", "vbs", "js", "jar", "msi", "dll", "iso"}
SUSPICIOUS_TLDS = (".ru.com", ".tk", ".xyz", ".top", ".click", ".zip", ".mov")
BRAND_FAKES = ("mts-secure", "mts-verify", "mtssecurity", "secure-mts")


def _api_key():
    return current_app.config.get("VIRUSTOTAL_API_KEY", "")


def _headers():
    key = _api_key()
    return {"x-apikey": key, "Accept": "application/json"} if key else None


def _url_id(url):
    return base64.urlsafe_b64encode(url.encode()).decode().strip("=")


def is_configured():
    return bool(_api_key())


def verdict_from_stats(stats):
    if not stats:
        return "unknown"
    malicious = stats.get("malicious", 0) or 0
    suspicious = stats.get("suspicious", 0) or 0
    harmless = stats.get("harmless", 0) or 0
    undetected = stats.get("undetected", 0) or 0
    total = malicious + suspicious + harmless + undetected
    if malicious >= 2:
        return "malicious"
    if malicious >= 1 or suspicious >= 3:
        return "suspicious"
    if total and not malicious and not suspicious:
        return "clean"
    return "unknown"


def _threat_names(results):
    names = []
    for info in results.values():
        if not isinstance(info, dict):
            continue
        if info.get("category") not in ("malicious", "suspicious"):
            continue
        name = info.get("result")
        if name and name not in names:
            names.append(name)
    return names[:10]


def _extract_url_report(data):
    attrs = (data or {}).get("data", {}).get("attributes", {})
    stats = attrs.get("last_analysis_stats") or attrs.get("stats") or {}
    return {
        "stats": stats,
        "verdict": verdict_from_stats(stats),
        "categories": attrs.get("categories") or {},
        "threat_names": _threat_names(attrs.get("last_analysis_results") or {}),
        "reputation": attrs.get("reputation"),
        "url": attrs.get("url") or attrs.get("link"),
    }


def _extract_file_report(data):
    attrs = (data or {}).get("data", {}).get("attributes", {})
    stats = attrs.get("last_analysis_stats") or {}
    return {
        "stats": stats,
        "verdict": verdict_from_stats(stats),
        "threat_names": _threat_names(attrs.get("last_analysis_results") or {}),
        "meaningful_name": attrs.get("meaningful_name"),
        "type_description": attrs.get("type_description"),
        "sha256": attrs.get("sha256"),
        "size": attrs.get("size"),
        "reputation": attrs.get("reputation"),
    }


def _poll_analysis(analysis_id, initial_wait=2.0, interval=4.0, max_wait=90.0):
    """Ждём завершения анализа VT (после upload URL/файла)."""
    headers = _headers()
    if not headers:
        return None

    time.sleep(initial_wait)
    elapsed = initial_wait
    last = None
    try:
        with httpx.Client(timeout=30.0) as client:
            while elapsed <= max_wait:
                resp = client.get(f"{VT_BASE}/analyses/{analysis_id}", headers=headers)
                if resp.status_code != 200:
                    return last
                attrs = resp.json().get("data", {}).get("attributes", {})
                stats = attrs.get("stats") or {}
                last = {
                    "stats": stats,
                    "verdict": verdict_from_stats(stats),
                    "status": attrs.get("status"),
                }
                if last["status"] == "completed":
                    return last
                time.sleep(interval)
                elapsed += interval
    except Exception as exc:
        current_app.logger.warning("vt analysis: %s", exc)
    return last


def _has_vt_stats(stats):
    if not stats:
        return False
    return sum(v or 0 for v in stats.values()) > 0


def _get_url_report(client, url):
    resp = client.get(f"{VT_BASE}/urls/{_url_id(url)}", headers=_headers())
    if resp.status_code == 200:
        report = _extract_url_report(resp.json())
        report["url"] = url
        return report
    return None


def _get_large_upload_url(client):
    resp = client.get(f"{VT_BASE}/files/upload_url", headers=_headers())
    if resp.status_code != 200:
        current_app.logger.warning("vt upload_url %s %s", resp.status_code, resp.text[:200])
        return None
    return resp.json().get("data")


def scan_file_hash_retry(sha256, attempts=8, delay=4.0):
    """Повторяем GET /files/{hash}: после upload отчёт появляется не сразу."""
    report = None
    for i in range(attempts):
        report = scan_file_hash(sha256)
        if report and report.get("error") in ("rate_limit", "invalid_hash"):
            return report
        if report and not report.get("not_in_db") and (report.get("stats") or report.get("threat_names")):
            return report
        if i < attempts - 1:
            time.sleep(delay)
    return report


def scan_url(url):
    headers = _headers()
    if not headers:
        return None

    url = url.strip()
    try:
        with httpx.Client(timeout=30.0) as client:
            resp = client.get(f"{VT_BASE}/urls/{_url_id(url)}", headers=headers)
            if resp.status_code == 200:
                return _extract_url_report(resp.json())

            if resp.status_code == 404:
                sub = client.post(f"{VT_BASE}/urls", headers=headers, data={"url": url})
                if sub.status_code not in (200, 201):
                    current_app.logger.warning("vt url submit %s %s", sub.status_code, sub.text[:200])
                    return None
                analysis_id = sub.json().get("data", {}).get("id")
                if analysis_id:
                    _poll_analysis(analysis_id, initial_wait=3.0)
                full = _get_url_report(client, url)
                if full:
                    return full
                return {"stats": {}, "verdict": "unknown", "url": url, "queued": True}

            if resp.status_code == 429:
                return {"error": "rate_limit", "message": "Лимит VirusTotal"}
            return None
    except Exception as exc:
        current_app.logger.warning("vt url: %s", exc)
        return None


def scan_file_hash(sha256):
    headers = _headers()
    if not headers:
        return None

    sha256 = sha256.strip().lower()
    if len(sha256) != 64 or not all(c in "0123456789abcdef" for c in sha256):
        return {"error": "invalid_hash"}

    try:
        with httpx.Client(timeout=30.0) as client:
            resp = client.get(f"{VT_BASE}/files/{sha256}", headers=headers)
            if resp.status_code == 200:
                return _extract_file_report(resp.json())
            if resp.status_code == 404:
                return {"stats": {}, "verdict": "unknown", "sha256": sha256, "not_in_db": True}
            if resp.status_code == 429:
                return {"error": "rate_limit", "message": "Лимит VirusTotal"}
            return None
    except Exception as exc:
        current_app.logger.warning("vt file: %s", exc)
        return None


def upload_and_scan_file(file_bytes, filename):
    headers = _headers()
    if not headers:
        return None

    sha256 = hashlib.sha256(file_bytes).hexdigest()
    existing = scan_file_hash(sha256)
    if existing and not existing.get("not_in_db"):
        existing["sha256"] = sha256
        existing["filename"] = filename
        return existing

    try:
        size = len(file_bytes)
        with httpx.Client(timeout=180.0) as client:
            # VT v3: multipart/form-data, поле file (не raw octet-stream)
            files = {"file": (filename, file_bytes, "application/octet-stream")}
            if size > 32 * 1024 * 1024:
                upload_url = _get_large_upload_url(client)
                if not upload_url:
                    return scan_file_hash_retry(sha256)
                resp = client.post(upload_url, headers=headers, files=files)
            else:
                resp = client.post(f"{VT_BASE}/files", headers=headers, files=files)

            if resp.status_code not in (200, 201):
                current_app.logger.warning("vt upload %s %s", resp.status_code, resp.text[:300])
            else:
                analysis_id = resp.json().get("data", {}).get("id")
                if analysis_id:
                    _poll_analysis(analysis_id, initial_wait=3.0)

            full = scan_file_hash_retry(sha256)
            if full and not full.get("not_in_db"):
                full["sha256"] = sha256
                full["filename"] = filename
                return full

            if existing and existing.get("not_in_db"):
                existing["filename"] = filename
                return existing
            return {
                "stats": {}, "verdict": "unknown",
                "sha256": sha256, "filename": filename, "not_in_db": True,
            }
    except Exception as exc:
        current_app.logger.warning("vt upload: %s", exc)
        return scan_file_hash_retry(sha256) or None


def heuristic_url_flags(url):
    flags = []
    try:
        parsed = urlparse(url)
    except ValueError:
        return ["Некорректный URL"]

    host = (parsed.hostname or "").lower()
    if not host:
        return ["Отсутствует домен"]

    if host.replace(".", "").isdigit() or host.startswith("["):
        flags.append("IP вместо домена")
    if "@" in url:
        flags.append("Символ @ в URL")
    if any(host.endswith(tld) for tld in SUSPICIOUS_TLDS):
        flags.append(f"Подозрительный TLD: {host}")
    lower = url.lower()
    if any(word in lower for word in ("login", "password", "verify")):
        flags.append("URL с login/password/verify")
    if any(fake in host for fake in BRAND_FAKES):
        flags.append(f"Похоже на подделку бренда: {host}")
    if len(url) > 120:
        flags.append("Слишком длинная ссылка")
    if parsed.scheme == "http":
        flags.append("Незащищённый HTTP")
    return flags


def risky_extension(filename):
    if "." not in filename:
        return None
    ext = filename.rsplit(".", 1)[-1].lower()
    return ext if ext in RISKY_EXTENSIONS else None
