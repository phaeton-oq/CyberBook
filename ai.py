import json
import re

from flask import current_app

# Cerebras (OpenAI-compatible). Нет ключа или ошибка API -> статические fallback-и ниже.

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

_client = None

SYSTEM_ASSISTANT = (
    "Ты — Кибер-Ассистент CyberBook, корпоративный помощник по кибербезопасности "
    "для сотрудников МТС. Отвечай кратко, по-русски, дружелюбно и по делу. "
    "Помогай распознавать фишинг, социальную инженерию, объясняй правила ИБ, "
    "давай пошаговые советы в рабочих ситуациях. Если ситуация опасная — "
    "чётко скажи, что делать (не переходить по ссылкам, сообщить в СБ и т.п.). "
    "Не выдумывай внутренние регламенты, если не уверен — советуй обратиться в СБ."
)

_FALLBACK_QUIZ = {
    "title": "Экспресс-квиз по кибербезопасности",
    "questions": [
        {
            "text": "Вам пришло СМС с кодом, которого вы не запрашивали, и звонок «из банка» с просьбой его назвать. Что делать?",
            "options": [
                "Назвать код, раз звонят из банка",
                "Положить трубку и никому не сообщать код",
                "Переслать код коллеге для проверки",
                "Ввести код на сайте из СМС",
            ],
            "correct_index": 1,
            "explanation": "Коды из СМС нельзя сообщать никому. Настоящий банк никогда не просит их назвать.",
        },
        {
            "text": "Какой признак чаще всего выдаёт фишинговое письмо?",
            "options": [
                "Наличие логотипа компании",
                "Срочность и угрозы + ссылка на чужой домен",
                "Обращение по имени",
                "Наличие подписи",
            ],
            "correct_index": 1,
            "explanation": "Давление срочностью и ссылка на посторонний домен — классические признаки фишинга.",
        },
    ],
}

_FALLBACK_PHISH = {
    "sender": "security-alert@mts-verify.ru",
    "sender_name": "Служба безопасности МТС",
    "subject": "СРОЧНО: обнаружен вход в ваш аккаунт",
    "body": (
        "Здравствуйте!\n\nМы зафиксировали подозрительный вход в вашу корпоративную "
        "учётную запись. Если это были не вы, немедленно подтвердите личность по ссылке "
        "в течение 2 часов, иначе аккаунт будет заблокирован:\n\n"
        "http://mts-verify.ru/login\n\nСлужба безопасности МТС"
    ),
    "is_phishing": True,
    "red_flags": [
        "Домен mts-verify.ru не является официальным доменом mts.ru",
        "Давление срочностью и угроза блокировки",
        "Прямая ссылка на ввод учётных данных",
    ],
    "difficulty": "medium",
}


def _get_client():
    global _client
    if _client is not None:
        return _client
    key = current_app.config.get("CEREBRAS_API_KEY")
    if not key or OpenAI is None:
        return None
    _client = OpenAI(api_key=key, base_url=current_app.config.get("CEREBRAS_BASE_URL"))
    return _client


def _chat(messages, temperature=0.5, max_tokens=800, json_mode=False):
    client = _get_client()
    if client is None:
        return None
    try:
        kwargs = {
            "model": current_app.config.get("AI_MODEL", "gpt-oss-120b"),
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        resp = client.chat.completions.create(**kwargs)
        return resp.choices[0].message.content
    except Exception as exc:
        current_app.logger.warning("cerebras: %s", exc)
        return None


def _extract_json(text):
    if not text:
        return None
    text = text.strip()
    match = re.search(r"\{.*\}|\[.*\]", text, re.DOTALL)
    raw = match.group(0) if match else text
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


def assistant_reply(user_message, history=None, user_context=None):
    system = SYSTEM_ASSISTANT
    if user_context:
        system += (
            "\n\nКонтекст о сотруднике (для персонализации, не зачитывай вслух):\n"
            + user_context
        )
    messages = [{"role": "system", "content": system}]
    if history:
        messages.extend(history[-8:])
    messages.append({"role": "user", "content": user_message})

    reply = _chat(messages, temperature=0.4, max_tokens=600)
    if reply:
        return reply, True
    return (
        "Кибер-Ассистент временно недоступен. Не переходите по подозрительным ссылкам, "
        "не сообщайте пароли и коды из СМС. При сомнениях — служба безопасности.",
        False,
    )


def generate_quiz(topic="общая кибербезопасность", n=4, difficulty="medium"):
    prompt = (
        f"Сгенерируй квиз из {n} вопросов по теме «{topic}» для сотрудников компании. "
        f"Сложность: {difficulty}. Каждый вопрос — 4 варианта, один верный. "
        'JSON: {"title": str, "questions": [{"text": str, "options": [str,str,str,str], '
        '"correct_index": int, "explanation": str}]}. '
        "По-русски, рабочие ситуации."
    )
    raw = _chat(
        [
            {"role": "system", "content": "Генератор квизов по ИБ. Только JSON."},
            {"role": "user", "content": prompt},
        ],
        temperature=0.7,
        max_tokens=1500,
        json_mode=True,
    )
    data = _extract_json(raw)
    if data and isinstance(data.get("questions"), list) and data["questions"]:
        return data, True
    return _FALLBACK_QUIZ, False


def generate_phishing(difficulty="medium", theme="корпоративная почта МТС"):
    prompt = (
        f"Фишинговое письмо для учебной симуляции (тема: {theme}, сложность: {difficulty}). "
        'JSON: {"sender": email, "sender_name": str, "subject": str, "body": str, '
        '"is_phishing": true, "red_flags": [str], "difficulty": str}. '
        "По-русски. Домен похожий, но не официальный."
    )
    raw = _chat(
        [
            {"role": "system", "content": "Генератор учебных фишинговых писем. Только JSON."},
            {"role": "user", "content": prompt},
        ],
        temperature=0.8,
        max_tokens=900,
        json_mode=True,
    )
    data = _extract_json(raw)
    if data and data.get("subject") and data.get("body"):
        data.setdefault("is_phishing", True)
        data.setdefault("red_flags", [])
        data.setdefault("difficulty", difficulty)
        return data, True
    return _FALLBACK_PHISH, False


def explain_mistake(context):
    reply = _chat(
        [
            {"role": "system", "content": SYSTEM_ASSISTANT},
            {"role": "user", "content": (
                f"Сотрудник ошибся: {context}. "
                "Коротко объясни ошибку, признаки и правильные действия. 3-4 предложения."
            )},
        ],
        temperature=0.5,
        max_tokens=400,
    )
    if reply:
        return reply, True
    return (
        "Срочность, угрозы и ссылки на ввод данных — признаки атаки. "
        "Не переходите по ссылке, проверьте отправителя, сообщите в СБ.",
        False,
    )


def _threat_review_fallback(vt_report, flags, scan_type="file"):
    vt_verdict = (vt_report or {}).get("verdict", "unknown")
    is_url = scan_type == "url"
    threats = (vt_report or {}).get("threat_names") or []
    merged = threats[:5] + list(flags)

    stats = (vt_report or {}).get("stats") or {}
    mal = stats.get("malicious") or 0
    sus = stats.get("suspicious") or 0
    engines = sum(stats.get(k, 0) or 0 for k in (
        "malicious", "suspicious", "harmless", "undetected", "failure", "type-unsupported",
    ))
    ratio = f"{mal + sus}/{engines}" if engines else ""

    rec_url = [
        "Не переходите по ссылке без проверки отправителя",
        "Сверьте домен с официальным сайтом",
        "При сомнениях обратитесь в СБ",
    ]
    rec_file = [
        "Не открывайте файл",
        "Сообщите в службу безопасности",
        "Удалите вложение",
    ]
    recs = rec_url if is_url else rec_file

    if vt_verdict == "clean":
        summary = f"VT: {ratio}. Вредоносных детектов нет." if ratio else "VT: вредоносных детектов нет."
        if flags and is_url:
            summary += " Эвристика видит признаки фишинга, но антивирусы ссылку не пометили."
        elif flags:
            summary += " Эвристика отметила несколько признаков."
        return {
            "verdict": "clean",
            "summary": summary,
            "recommendations": recs[:2],
            "red_flags": threats[:5],
        }

    if vt_verdict == "malicious":
        summary = f"VT: {ratio}. " if ratio else ""
        summary += "Обнаружены признаки угрозы."
        if threats:
            summary += f" Детекты: {', '.join(threats[:3])}."
        return {
            "verdict": "malicious",
            "summary": summary,
            "recommendations": recs,
            "red_flags": merged[:8],
        }

    if vt_verdict == "suspicious":
        summary = f"VT: {ratio}. " if ratio else ""
        summary += "Антивирусы пометили как подозрительное."
        if threats:
            summary += f" Детекты: {', '.join(threats[:3])}."
        return {
            "verdict": "suspicious",
            "summary": summary,
            "recommendations": recs,
            "red_flags": merged[:8],
        }

    if flags and is_url:
        return {
            "verdict": "suspicious",
            "summary": "VT не дал отчёт. Эвристика видит признаки фишинга.",
            "recommendations": recs,
            "red_flags": list(flags)[:8],
        }
    if flags:
        return {
            "verdict": "suspicious",
            "summary": "Данных VT мало, есть эвристические признаки.",
            "recommendations": recs,
            "red_flags": list(flags)[:8],
        }
    return {
        "verdict": "unknown",
        "summary": "Данных мало, действуйте осторожно.",
        "recommendations": recs[:2],
        "red_flags": [],
    }


def review_threat_scan(scan_type, target, vt_report=None, heuristic_flags=None):
    flags = heuristic_flags or []
    vt_line = "VirusTotal: нет данных."
    if vt_report:
        if vt_report.get("error") == "rate_limit":
            vt_line = "VirusTotal: лимит запросов."
        elif vt_report.get("not_in_db"):
            vt_line = "Файл не найден в базе VT."
        else:
            stats = vt_report.get("stats") or {}
            vt_line = (
                f"VT verdict={vt_report.get('verdict')}, stats={stats}, "
                f"threats={vt_report.get('threat_names', [])}"
            )

    prompt = (
        f"Проверка ({scan_type}): {target}\n{vt_line}\n"
        f"Эвристика: {', '.join(flags) if flags else 'нет'}\n"
        'JSON: {"verdict":"clean|suspicious|malicious|unknown",'
        '"summary":"...", "recommendations":["..."], "red_flags":["..."]}'
    )
    raw = _chat(
        [
            {"role": "system", "content": "Аналитик ИБ CyberBook. Только JSON."},
            {"role": "user", "content": prompt},
        ],
        temperature=0.3,
        max_tokens=700,
        json_mode=True,
    )
    data = _extract_json(raw)
    if data and data.get("summary"):
        return data, True
    return _threat_review_fallback(vt_report, flags, scan_type), False


def review_suspicious_text(text, url_reports=None):
    url_ctx = ""
    if url_reports:
        chunks = []
        for item in url_reports:
            vt = item.get("vt") or {}
            chunks.append(
                f"{item.get('url')}: {vt.get('verdict', 'n/a')}, flags={item.get('heuristic_flags', [])}"
            )
        url_ctx = "Ссылки:\n" + "\n".join(chunks)

    prompt = (
        f"Подозрительный текст:\n\n{text[:4000]}\n\n{url_ctx}\n"
        'JSON: {"verdict":"clean|suspicious|malicious|unknown",'
        '"summary":"...", "recommendations":["..."], "red_flags":["..."]}'
    )
    raw = _chat(
        [
            {"role": "system", "content": "Аналитик ИБ. Только JSON."},
            {"role": "user", "content": prompt},
        ],
        temperature=0.3,
        max_tokens=800,
        json_mode=True,
    )
    data = _extract_json(raw)
    if data and data.get("summary"):
        return data, True
    return {
        "verdict": "suspicious",
        "summary": "Возможны признаки фишинга. Не переходите по ссылкам, не сообщайте коды.",
        "recommendations": [
            "Проверьте отправителя",
            "Сообщите в СБ",
            "Не открывайте вложения",
        ],
        "red_flags": ["AI недоступен, нужна ручная проверка"],
    }, False
