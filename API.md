# CyberBook — API-контракт

Один сервер: Flask отдаёт `/api/*` (JSON) и статику фронта из `static/`.
Авторизация — cookie-сессия (Flask-Login). Фронт шлёт `fetch(..., {credentials:"same-origin"})`
(в `static/js/api.js` уже настроено).

Base URL при разработке: `http://localhost:5000`

## Демо-аккаунты
| роль | email | пароль |
|------|-------|--------|
| admin | admin@mts.ru | admin123 |
| employee | ivan@mts.ru | user123 |

---

## Auth
| метод | путь | тело | ответ |
|-------|------|------|-------|
| POST | `/api/auth/register` | `{name, email, password, department?}` | user |
| POST | `/api/auth/login` | `{email, password}` | user |
| POST | `/api/auth/logout` | — | `{ok:true}` |
| GET  | `/api/auth/me` | — | user / 401 |
| PATCH | `/api/auth/me` | `{name?, department?, email?, password?}` | обновлённый user |

## Админ — управление сотрудниками  *(только admin)*
| метод | путь | тело | ответ |
|-------|------|------|-------|
| POST | `/api/admin/users` | `{name, email, password, department?}` | созданный user |
| DELETE | `/api/admin/users/<id>` | — | `{ok:true}` (нельзя удалить себя/админа) |

`user = {id, name, email, role, department, security_score, points, badges:[{name,icon}]}`

## Курсы и уроки  *(владелец: 2-й бэкенд)*
| метод | путь | тело | ответ |
|-------|------|------|-------|
| GET | `/api/courses` | — | `[{id,title,...,completed}]` |
| GET | `/api/courses/<id>` | — | курс + `content`, `lessons[]`, `quizzes[]`, `completed` |
| POST | `/api/courses` (admin) | `{title, description?, content?, video_url?, topic?, order?}` | курс |
| PUT | `/api/courses/<id>` (admin) | поля курса | курс |
| DELETE | `/api/courses/<id>` (admin) | — | `{ok:true}` |
| POST | `/api/courses/<id>/complete` | — | `{completed, security_score, points, new_badges[]}` |
| GET | `/api/courses/progress/me` | — | `{courses[], lessons[]}` |
| GET | `/api/courses/<id>/lessons` | — | `[{id,title,content,video_url,order,completed}]` |
| POST | `/api/courses/<id>/lessons` (admin) | `{title, content?, video_url?, order?}` | урок |
| GET | `/api/courses/lessons/<id>` | — | урок + `completed` |
| PUT | `/api/courses/lessons/<id>` (admin) | поля урока | урок |
| DELETE | `/api/courses/lessons/<id>` (admin) | — | `{ok:true}` |
| POST | `/api/courses/lessons/<id>/complete` | — | `{completed, security_score, points, new_badges[]}` |

## Квизы  *(владелец: 2-й бэкенд)*
| метод | путь | тело | ответ |
|-------|------|------|-------|
| GET | `/api/quiz` | — | список квизов |
| GET | `/api/quiz/history` | — | история попыток текущего пользователя |
| GET | `/api/quiz/<id>` | — | квиз БЕЗ правильных ответов |
| POST | `/api/quiz/<id>/submit` | `{answers:[idx,...]}` | `{score,correct,total,review[],security_score,points,new_badges[]}` |
| POST | `/api/quiz/generate` | `{topic,n?,difficulty?,course_id?}` | `{quiz, ai:bool}` |
| POST | `/api/quiz/personalized` | `{n?}` | `{quiz, ai, weak_topics[], selected_topic}` |
| POST | `/api/quiz` (admin) | `{title, course_id?, questions:[{text,options,correct_index,explanation?}]}` | квиз с ответами |
| PUT | `/api/quiz/<id>` (admin) | `{title?, course_id?, questions?}` | квиз |
| DELETE | `/api/quiz/<id>` (admin) | — | `{ok:true}` |

## Фишинг-тренажёр  *(владелец: ядро/я)*
| метод | путь | тело | ответ |
|-------|------|------|-------|
| GET | `/api/phishing/inbox` | — | `[{id,sender,sender_name,subject,body,difficulty,answered,was_correct}]` |
| GET | `/api/phishing/email/<id>` | — | письмо (раскрывает red_flags, если уже отвечал) |
| POST | `/api/phishing/answer` | `{email_id, action:"reported"\|"clicked"\|"trusted"}` | `{correct,is_phishing,red_flags[],explanation,security_score,points,new_badges[]}` |
| POST | `/api/phishing/generate` (admin) | `{difficulty?,theme?}` | `{email, ai:bool}` |

**Правило:** фишинг → правильно `reported`; легитимное письмо → правильно `trusted`.

## AI-ассистент  *(владелец: ядро/я)*
| метод | путь | тело | ответ |
|-------|------|------|-------|
| POST | `/api/assistant/chat` | `{message, history?:[{role,content}]}` | `{reply, ai:bool}` |

## Сканер угроз — VirusTotal + AI  *(новый модуль)*
| метод | путь | тело | ответ |
|-------|------|------|-------|
| GET | `/api/scan/status` | — | `{virustotal_configured, max_file_mb}` |
| GET | `/api/scan/history` | — | история проверок пользователя |
| POST | `/api/scan/url` | `{url}` | VT + AI: `{verdict, vt:{stats,threat_names}, ai_review, red_flags, recommendations, ai, points}` |
| POST | `/api/scan/file` | multipart `file` **или** `{sha256, filename?}` | проверка файла по загрузке или хешу |
| POST | `/api/scan/review` | `{text}` | разбор письма/СМС: извлекает URL → VT + AI |

**Вердикты:** `clean` | `suspicious` | `malicious` | `unknown`

Без `VIRUSTOTAL_API_KEY` работает AI + эвристика (домен, IP, подозрительные слова в URL).

Ключ VirusTotal: https://www.virustotal.com/gui/my-apikey → в `.env` как `VIRUSTOTAL_API_KEY`.

## Статистика и геймификация  *(владелец: 2-й бэкенд)*
| метод | путь | ответ |
|-------|------|-------|
| GET | `/api/stats/me` | личная статистика + `formula` (разбор Security Score) |
| GET | `/api/stats/leaderboard` | `[{rank,user_id,name,department,security_score,points,badges[],formula_score}]` |
| GET | `/api/stats/overview` (admin) | сводка: пользователи, фишинг (% кликов), квизы, курсы |
| GET | `/api/stats/timeline` (admin) | динамика за 30 дней: quiz, phishing, course_completions |
| GET | `/api/stats/users` (admin) | таблица сотрудников: кто прошёл, средний балл, % кликов |
| GET | `/api/stats/export/<user_id>` (admin) | CSV-отчёт по сотруднику |
| GET | `/api/stats/export/<user_id>/pdf` (admin) | PDF-отчёт (нужен fpdf2) |

### Формула Security Score
```
score = clamp(50
  + (avg_quiz - 50) * 0.35
  + (catch_rate - 50) * 0.35
  + course_completion% * 0.20
  - click_rate% * 0.15)
```
Поле `formula` в `/api/stats/me` показывает разбор по компонентам.

### Очки и бейджи
- Очки (`points`): квиз +10/правильный, фишинг +15, урок +20, курс +50
- Бейджи: Кибер-Страж (80+), Неприступный (95+), Отличник ИБ (100% квиз), Ученик ИБ, Мастер обучения, Знаток квизов, Охотник за очками

---

## Как поднять локально
```bash
python -m venv .venv
.venv\Scripts\activate           # Windows
pip install -r requirements.txt
copy .env.example .env           # вписать CEREBRAS_API_KEY
python seed.py                   # демо-данные (пересоздаёт БД)
python app.py                    # http://localhost:5000
```

`GET /api/health` → `{"status":"ok"}` — проверка, что сервер жив.
