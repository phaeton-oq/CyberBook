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

`user = {id, name, email, role, department, security_score, badges:[{name,icon}]}`

## Курсы  *(владелец: 2-й бэкенд)*
| метод | путь | ответ |
|-------|------|-------|
| GET | `/api/courses` | `[{id,title,description,video_url,topic,order}]` |
| GET | `/api/courses/<id>` | курс + `content`, `quizzes:[{id,title}]` |
| POST | `/api/courses` (admin) | `{title, description?, content?, video_url?, topic?}` |

## Квизы  *(владелец: 2-й бэкенд)*
| метод | путь | тело | ответ |
|-------|------|------|-------|
| GET | `/api/quiz/<id>` | — | квиз БЕЗ правильных ответов: `{id,title,questions:[{id,text,options[]}]}` |
| POST | `/api/quiz/<id>/submit` | `{answers:[idx,...]}` | `{score,correct,total,review:[{question_id,chosen,correct_index,is_correct,explanation}],security_score,new_badges[]}` |
| POST | `/api/quiz/generate` | `{topic,n?,difficulty?,course_id?}` | `{quiz, ai:bool}` — генерит через Cerebras |

## Фишинг-тренажёр  *(владелец: ядро/я)*
| метод | путь | тело | ответ |
|-------|------|------|-------|
| GET | `/api/phishing/inbox` | — | `[{id,sender,sender_name,subject,body,difficulty,answered,was_correct}]` |
| GET | `/api/phishing/email/<id>` | — | письмо (раскрывает red_flags, если уже отвечал) |
| POST | `/api/phishing/answer` | `{email_id, action:"reported"\|"clicked"\|"trusted"}` | `{correct,is_phishing,red_flags[],explanation,security_score,new_badges[]}` |
| POST | `/api/phishing/generate` (admin) | `{difficulty?,theme?}` | `{email, ai:bool}` |

**Правило:** фишинг → правильно `reported`; легитимное письмо → правильно `trusted`.
`explanation` приходит от AI, только если сотрудник ошибся.

## AI-ассистент  *(владелец: ядро/я)*
| метод | путь | тело | ответ |
|-------|------|------|-------|
| POST | `/api/assistant/chat` | `{message, history?:[{role,content}]}` | `{reply, ai:bool}` |

`ai:false` = сработал fallback (нет ключа/Cerebras недоступен) — демо не падает.

## Статистика  *(владелец: 2-й бэкенд)*
| метод | путь | ответ |
|-------|------|-------|
| GET | `/api/stats/me` | `{security_score,quiz_attempts,avg_quiz_score,phishing_seen,phishing_caught,badges[]}` |
| GET | `/api/stats/leaderboard` | `[{rank,name,department,security_score,badges[]}]` |
| GET | `/api/stats/overview` (admin) | сводка компании: `{total_users,avg_security_score,phishing:{...},quiz:{...},departments[],at_risk[]}` |

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
