import base64
import hashlib
import time
from urllib.parse import urlparse

import httpx
from flask import current_app

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


def _poll_analysis(analysis_id, wait_sec=3.0):
    headers = _headers()
    if not headers:
        return None
    time.sleep(wait_sec)
    try:
        with httpx.Client(timeout=30.0) as client:
            resp = client.get(f"{VT_BASE}/analyses/{analysis_id}", headers=headers)
            if resp.status_code != 200:
                return None
            attrs = resp.json().get("data", {}).get("attributes", {})
            stats = attrs.get("stats") or {}
            return {
                "stats": stats,
                "verdict": verdict_from_stats(stats),
                "status": attrs.get("status"),
            }
    except Exception as exc:
        current_app.logger.warning("vt analysis: %s", exc)
        return None


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
                    current_app.logger.warning("vt url submit %s", sub.status_code)
                    return None
                analysis_id = sub.json().get("data", {}).get("id")
                if not analysis_id:
                    return None
                polled = _poll_analysis(analysis_id, wait_sec=4.0)
                if polled:
                    return {
                        "stats": polled["stats"],
                        "verdict": polled["verdict"],
                        "categories": {},
                        "threat_names": [],
                        "url": url,
                        "queued": polled.get("status") != "completed",
                    }
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
        upload_headers = {**headers, "Content-Type": "application/octet-stream"}
        with httpx.Client(timeout=120.0) as client:
            resp = client.post(f"{VT_BASE}/files", headers=upload_headers, content=file_bytes)
            if resp.status_code not in (200, 201):
                current_app.logger.warning("vt upload %s", resp.status_code)
                return scan_file_hash(sha256) or {
                    "stats": {}, "verdict": "unknown",
                    "sha256": sha256, "filename": filename, "not_in_db": True,
                }
            analysis_id = resp.json().get("data", {}).get("id")
            if analysis_id:
                polled = _poll_analysis(analysis_id, wait_sec=8.0)
                if polled:
                    return {
                        "stats": polled["stats"],
                        "verdict": polled["verdict"],
                        "sha256": sha256,
                        "filename": filename,
                        "queued": polled.get("status") != "completed",
                    }
            return scan_file_hash(sha256) or {
                "stats": {}, "verdict": "unknown", "sha256": sha256, "filename": filename,
            }
    except Exception as exc:
        current_app.logger.warning("vt upload: %s", exc)
        return None


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
