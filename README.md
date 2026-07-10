# CyberBook 🛡️

Корпоративный ассистент по кибербезопасности (кейс МТС). AI-тренер на Cerebras
(gpt-oss-120b), который обучает сотрудников, генерирует квизы и фишинговые письма,
симулирует атаки и разбирает ошибки.

**Стек:** Python Flask + SQLite + vanilla JS. AI: Cerebras (OpenAI-совместимый API).

## Быстрый старт
```powershell
.\build.ps1 -Seed          # секреты + deps + демо-данные
python app.py              # http://localhost:5000
```

Или вручную:
```bash
python scripts/gen_secrets.py
pip install -r requirements.txt
copy .env.example .env      # CEREBRAS_API_KEY, VIRUSTOTAL_API_KEY
python seed.py
python app.py
```
Демо: `admin@mts.ru / admin123` · `ivan@mts.ru / user123`

## Фичи
- Курсы, уроки, видео, прогресс
- Квизы с разбором и персонализацией
- Симулятор фишинга
- AI-ассистент
- Сканер ссылок/файлов (VirusTotal + AI)
- Статистика, Security Score, бейджи, экспорт отчётов

См. [API.md](API.md): контракт эндпоинтов, [CODE_REVIEW.md](CODE_REVIEW.md): ревью блоков и ответы на вопросы, [TASKS.md](TASKS.md): распределение задач.
