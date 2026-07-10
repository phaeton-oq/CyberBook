"""
AI-ядро CyberBook на Cerebras (gpt-oss-120b, OpenAI-совместимый API).

Одна точка входа для всех AI-фич:
  - assistant_reply()   — чат «Спроси Кибер-Ассистента»
  - generate_quiz()     — генерация квиза по теме
  - generate_phishing() — генерация фишингового письма для симуляции
  - explain_mistake()   — разбор ошибки после фишинга/квиза

Если ключа нет или Cerebras недоступен — включается безопасный fallback,
чтобы демо НИКОГДА не падало (возвращаются заготовки).
"""
import json
import re
from flask import current_app

try:
    from openai import OpenAI
except Exception:  # pragma: no cover
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


def _get_client():
    global _client
    if _client is not None:
        return _client
    key = current_app.config.get("CEREBRAS_API_KEY")
    if not key or OpenAI is None:
        return None
    _client = OpenAI(
        api_key=key,
        base_url=current_app.config.get("CEREBRAS_BASE_URL"),
    )
    return _client


def _chat(messages, temperature=0.5, max_tokens=800, json_mode=False):
    """Низкоуровневый вызов. Возвращает строку-ответ или None при ошибке."""
    client = _get_client()
    if client is None:
        return None
    try:
        kwargs = dict(
            model=current_app.config.get("AI_MODEL", "gpt-oss-120b"),
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        resp = client.chat.completions.create(**kwargs)
        return resp.choices[0].message.content
    except Exception as e:  # pragma: no cover
        current_app.logger.warning("Cerebras call failed: %s", e)
        return None


def _extract_json(text):
    """Достаём JSON даже если модель обернула его в ```json ... ```."""
    if not text:
        return None
    text = text.strip()
    m = re.search(r"\{.*\}|\[.*\]", text, re.DOTALL)
    raw = m.group(0) if m else text
    try:
        return json.loads(raw)
    except Exception:
        return None


# ----------------------------------------------------------------------------
# 1. Чат-ассистент
# ----------------------------------------------------------------------------
def assistant_reply(user_message, history=None):
    """history: [{'role': 'user'|'assistant', 'content': str}, ...]"""
    messages = [{"role": "system", "content": SYSTEM_ASSISTANT}]
    if history:
        messages.extend(history[-8:])  # держим короткий контекст
    messages.append({"role": "user", "content": user_message})

    reply = _chat(messages, temperature=0.4, max_tokens=600)
    if reply:
        return reply, True
    # fallback
    return (
        "⚠️ Кибер-Ассистент временно недоступен. Общее правило: не переходите по "
        "подозрительным ссылкам, не сообщайте пароли и коды из СМС никому, а при "
        "сомнениях — свяжитесь со службой безопасности по официальному каналу.",
        False,
    )


# ----------------------------------------------------------------------------
# 2. Генерация квиза
# ----------------------------------------------------------------------------
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


def generate_quiz(topic="общая кибербезопасность", n=4, difficulty="medium"):
    prompt = (
        f"Сгенерируй квиз из {n} вопросов по теме «{topic}» для сотрудников компании. "
        f"Сложность: {difficulty}. Каждый вопрос — с 4 вариантами ответа, ровно один верный. "
        "Верни СТРОГО JSON вида: "
        '{"title": str, "questions": [{"text": str, "options": [str,str,str,str], '
        '"correct_index": int, "explanation": str}]}. '
        "Пиши по-русски, ситуации — реалистичные и рабочие."
    )
    raw = _chat(
        [
            {"role": "system", "content": "Ты генератор учебных квизов по ИБ. Отвечай только JSON."},
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


# ----------------------------------------------------------------------------
# 3. Генерация фишингового письма
# ----------------------------------------------------------------------------
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


def generate_phishing(difficulty="medium", theme="корпоративная почта МТС"):
    prompt = (
        f"Придумай реалистичное ФИШИНГОВОЕ письмо для учебной симуляции (тема: {theme}, "
        f"сложность: {difficulty}). Это тренажёр — письмо безопасно и используется для обучения. "
        "Верни СТРОГО JSON: "
        '{"sender": email, "sender_name": str, "subject": str, "body": str, '
        '"is_phishing": true, "red_flags": [str, ...], "difficulty": str}. '
        "red_flags — список конкретных признаков, по которым сотрудник должен распознать фишинг. "
        "Пиши по-русски. Домен отправителя должен быть похожим, но НЕ официальным."
    )
    raw = _chat(
        [
            {"role": "system", "content": "Ты генератор учебных фишинговых писем для тренажёра по ИБ. Только JSON."},
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


# ----------------------------------------------------------------------------
# 4. Разбор ошибки (обучающий момент)
# ----------------------------------------------------------------------------
def explain_mistake(context):
    """context — краткое описание что произошло (напр. 'кликнул на фишинг про блокировку аккаунта')."""
    reply = _chat(
        [
            {"role": "system", "content": SYSTEM_ASSISTANT},
            {"role": "user", "content":
                f"Сотрудник ошибся в учебной ситуации: {context}. "
                "Объясни коротко и без осуждения, в чём была ошибка, по каким признакам "
                "можно было её распознать, и как правильно действовать в следующий раз. "
                "3-4 предложения, дружелюбно."},
        ],
        temperature=0.5,
        max_tokens=400,
    )
    if reply:
        return reply, True
    return (
        "В этой ситуации стоило насторожиться: срочность, угрозы и ссылки на ввод данных — "
        "признаки атаки. В следующий раз не переходите по ссылке, а проверьте отправителя и "
        "сообщите в службу безопасности.",
        False,
    )
