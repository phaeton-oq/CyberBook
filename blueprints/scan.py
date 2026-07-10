"""Сканер угроз: VirusTotal, эвристика, AI-разбор."""
import hashlib
import re

from flask import Blueprint, jsonify, request, current_app
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename

from extensions import db
from models import ThreatScan
import ai
import scoring
import virustotal as vt

scan_bp = Blueprint("scan", __name__, url_prefix="/api/scan")

_SHA256 = re.compile(r"^[a-fA-F0-9]{64}$")
_VERDICT_RANK = {"malicious": 3, "suspicious": 2, "unknown": 1, "clean": 0}


def _pick_verdict(*values):
    best = "unknown"
    for val in values:
        if not val:
            continue
        if _VERDICT_RANK.get(val, 0) > _VERDICT_RANK.get(best, 0):
            best = val
    return best


def _persist(scan_type, target, verdict, vt_report, ai_data, ai_used):
    row = ThreatScan(
        user_id=current_user.id,
        scan_type=scan_type,
        target=target[:500],
        verdict=verdict,
        vt_stats=(vt_report or {}).get("stats") or {},
        vt_available=bool(vt_report and not vt_report.get("error")),
        ai_review=ai_data.get("summary", ""),
        ai_used=ai_used,
        red_flags=ai_data.get("red_flags") or [],
    )
    db.session.add(row)
    scoring.add_points(current_user, 5)
    badges = []
    if scoring.award_badge(current_user, "Аналитик угроз", "🔍"):
        badges.append("Аналитик угроз")
    db.session.commit()
    return row, badges


def _vt_block(report):
    return {
        "available": vt.is_configured() and report is not None,
        "stats": (report or {}).get("stats") or {},
        "threat_names": (report or {}).get("threat_names") or [],
        "categories": (report or {}).get("categories") or {},
    }


def _response(row, payload):
    payload["scan_id"] = row.id
    payload["points"] = current_user.points
    return jsonify(payload)


@scan_bp.get("/status")
@login_required
def status():
    return jsonify({
        "virustotal_configured": vt.is_configured(),
        "max_file_mb": current_app.config.get("SCAN_MAX_FILE_MB", 32),
    })


@scan_bp.get("/history")
@login_required
def history():
    rows = ThreatScan.query.filter_by(user_id=current_user.id)\
        .order_by(ThreatScan.created_at.desc()).limit(30).all()
    return jsonify([r.to_dict() for r in rows])


@scan_bp.post("/url")
@login_required
def scan_url():
    data = request.get_json(silent=True) or {}
    url = (data.get("url") or "").strip()
    if not url:
        return jsonify(error="Укажите url"), 400
    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    vt_report = vt.scan_url(url) if vt.is_configured() else None
    if vt_report and vt_report.get("error") == "rate_limit":
        return jsonify(error=vt_report.get("message", "Лимит VirusTotal")), 429

    flags = vt.heuristic_url_flags(url)
    ai_data, ai_used = ai.review_threat_scan("url", url, vt_report, flags)
    verdict = _pick_verdict((vt_report or {}).get("verdict"), ai_data.get("verdict"))
    row, badges = _persist("url", url, verdict, vt_report, ai_data, ai_used)

    return _response(row, {
        "scan_type": "url",
        "target": url,
        "verdict": verdict,
        "vt": _vt_block(vt_report),
        "heuristic_flags": flags,
        "ai_review": ai_data.get("summary", ""),
        "recommendations": ai_data.get("recommendations") or [],
        "red_flags": ai_data.get("red_flags") or flags,
        "ai": ai_used,
        "new_badges": badges,
    })


@scan_bp.post("/file")
@login_required
def scan_file():
    max_mb = current_app.config.get("SCAN_MAX_FILE_MB", 32)
    max_bytes = max_mb * 1024 * 1024
    vt_report = None
    filename = ""
    sha256 = ""

    upload = request.files.get("file")
    if upload and upload.filename:
        filename = secure_filename(upload.filename) or "upload.bin"
        blob = upload.read(max_bytes + 1)
        if len(blob) > max_bytes:
            return jsonify(error=f"Файл больше {max_mb} МБ"), 400
        sha256 = hashlib.sha256(blob).hexdigest()
        if vt.is_configured():
            vt_report = vt.upload_and_scan_file(blob, filename)
    else:
        data = request.get_json(silent=True) or {}
        sha256 = (data.get("sha256") or data.get("hash") or "").strip().lower()
        filename = (data.get("filename") or f"{sha256[:16]}...").strip()
        if not _SHA256.match(sha256):
            return jsonify(error="Нужен sha256 или upload"), 400
        if vt.is_configured():
            vt_report = vt.scan_file_hash(sha256)

    if vt_report and vt_report.get("error") == "rate_limit":
        return jsonify(error=vt_report.get("message", "Лимит VirusTotal")), 429

    target = f"{filename} ({sha256})" if sha256 else filename
    flags = []
    if vt_report and vt_report.get("not_in_db"):
        flags.append("Файл не найден в базе VT")
    risky = vt.risky_extension(filename)
    if risky:
        flags.append(f"Расширение .{risky} может запускать код")

    ai_data, ai_used = ai.review_threat_scan("file", target, vt_report, flags)
    verdict = _pick_verdict((vt_report or {}).get("verdict"), ai_data.get("verdict"))
    row, badges = _persist("file", target, verdict, vt_report, ai_data, ai_used)

    vt_payload = _vt_block(vt_report)
    vt_payload["not_in_db"] = bool((vt_report or {}).get("not_in_db"))

    return _response(row, {
        "scan_type": "file",
        "target": target,
        "sha256": sha256,
        "filename": filename,
        "verdict": verdict,
        "vt": vt_payload,
        "heuristic_flags": flags,
        "ai_review": ai_data.get("summary", ""),
        "recommendations": ai_data.get("recommendations") or [],
        "red_flags": ai_data.get("red_flags") or flags,
        "ai": ai_used,
        "new_badges": badges,
    })


@scan_bp.post("/review")
@login_required
def review_text():
    data = request.get_json(silent=True) or {}
    text = (data.get("text") or "").strip()
    if not text:
        return jsonify(error="Укажите text"), 400
    if len(text) > 8000:
        return jsonify(error="Максимум 8000 символов"), 400

    url_reports = []
    for url in re.findall(r"https?://[^\s<>\"']+", text)[:3]:
        report = vt.scan_url(url) if vt.is_configured() else None
        url_reports.append({
            "url": url,
            "vt": report,
            "heuristic_flags": vt.heuristic_url_flags(url),
        })

    ai_data, ai_used = ai.review_suspicious_text(text, url_reports)
    worst_vt = "unknown"
    for item in url_reports:
        v = (item["vt"] or {}).get("verdict")
        if v in ("malicious", "suspicious"):
            worst_vt = v
    verdict = _pick_verdict(worst_vt, ai_data.get("verdict"))

    row, badges = _persist(
        "url",
        f"review:{text[:80]}...",
        verdict,
        url_reports[0]["vt"] if url_reports else None,
        ai_data,
        ai_used,
    )

    return _response(row, {
        "verdict": verdict,
        "ai_review": ai_data.get("summary", ""),
        "recommendations": ai_data.get("recommendations") or [],
        "red_flags": ai_data.get("red_flags") or [],
        "urls_checked": url_reports,
        "ai": ai_used,
        "new_badges": badges,
    })
