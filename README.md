# CyberBook 🛡️

Корпоративный ассистент по кибербезопасности (кейс МТС). AI-тренер на Cerebras
(gpt-oss-120b), который обучает сотрудников, генерирует квизы и фишинговые письма,
симулирует атаки и разбирает ошибки.

**Стек:** Python Flask + SQLite + vanilla JS. AI — Cerebras (OpenAI-совместимый API).

## Быстрый старт
```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env      # вписать CEREBRAS_API_KEY
python seed.py              # демо-данные
python app.py               # http://localhost:5000
```
Демо: `admin@mts.ru / admin123` · `ivan@mts.ru / user123`

## Фичи
- 📚 Обучение: курсы, видео, материалы
- 🧠 Квизы с разбором (можно генерировать через AI)
- 📨 Симулятор фишинга: инбокс, распознавание, red flags
- 🤖 AI-ассистент «Спроси Кибер-Ассистента»
- 📊 Статистика, Security Score, бейджи, лидерборд отделов

См. [API.md](API.md) — контракт эндпоинтов, [TASKS.md](TASKS.md) — распределение задач.
