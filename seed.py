"""
Наполнение демо-данными для CyberBook.
Запуск:  python seed.py   (пересоздаёт таблицы и заливает демо-контент)

Демо-аккаунты:
    admin@mts.ru / admin123      (роль admin)
    ivan@mts.ru  / user123       (роль employee)
    + несколько сотрудников для лидерборда/статистики
"""
import random

from app import create_app
from extensions import db
from models import (
    User, Course, Quiz, Question, PhishingEmail,
    PhishingResult, QuizAttempt,
)

app = create_app()


def run():
    with app.app_context():
        db.drop_all()
        db.create_all()

        # ---------------- Пользователи ----------------
        admin = User(name="Админ СБ", email="admin@mts.ru", role="admin",
                     department="Служба безопасности", security_score=100)
        admin.set_password("admin123")
        db.session.add(admin)

        ivan = User(name="Иван Петров", email="ivan@mts.ru", role="employee",
                    department="Продажи", security_score=55)
        ivan.set_password("user123")
        db.session.add(ivan)

        departments = ["Продажи", "Бухгалтерия", "IT", "HR", "Маркетинг"]
        names = ["Мария Смирнова", "Алексей Козлов", "Ольга Новикова",
                 "Дмитрий Волков", "Елена Морозова", "Сергей Соколов",
                 "Анна Лебедева", "Павел Егоров"]
        for i, nm in enumerate(names):
            u = User(name=nm, email=f"user{i}@mts.ru", role="employee",
                     department=random.choice(departments),
                     security_score=random.randint(30, 95))
            u.set_password("user123")
            db.session.add(u)

        # ---------------- Курсы ----------------
        courses_data = [
            {
                "title": "Основы кибербезопасности",
                "description": "С чего начинается защита: пароли, устройства, рабочее место.",
                "topic": "Основы",
                "order": 1,
                "video_url": "https://www.youtube.com/embed/inWWhr5tnEA",
                "content": (
                    "## Зачем это нужно\n"
                    "80% успешных атак начинаются с ошибки человека, а не с взлома техники.\n\n"
                    "### Правила гигиены\n"
                    "- Уникальный сложный пароль для каждого сервиса, лучше — менеджер паролей.\n"
                    "- Включите двухфакторную аутентификацию (2FA) везде, где можно.\n"
                    "- Блокируйте компьютер, отходя от рабочего места (Win+L).\n"
                    "- Не вставляйте найденные USB-флешки в рабочий ПК.\n"
                ),
            },
            {
                "title": "Фишинг и социальная инженерия",
                "description": "Как распознать поддельные письма, звонки и сообщения.",
                "topic": "Фишинг",
                "order": 2,
                "video_url": "https://www.youtube.com/embed/o_qHQMcVWMY",
                "content": (
                    "## Что такое фишинг\n"
                    "Попытка обманом выманить данные (пароли, коды, деньги) через письма, "
                    "СМС или звонки.\n\n"
                    "### Признаки фишинга\n"
                    "- Давление срочностью: «аккаунт заблокируют через 2 часа».\n"
                    "- Чужой домен отправителя (mts-verify.ru вместо mts.ru).\n"
                    "- Просьба ввести пароль/код по ссылке.\n"
                    "- Неожиданные вложения.\n\n"
                    "### Что делать\n"
                    "Не переходить по ссылкам, проверить отправителя, сообщить в СБ.\n"
                ),
            },
            {
                "title": "Защита данных и пароли",
                "description": "Менеджеры паролей, 2FA, безопасное хранение информации.",
                "topic": "Пароли",
                "order": 3,
                "video_url": "https://www.youtube.com/embed/3NjQ9b3pgIg",
                "content": (
                    "## Пароли\n"
                    "- Длина важнее сложности: парольная фраза из 4 слов надёжнее «P@ss1».\n"
                    "- Не используйте один пароль в разных местах.\n\n"
                    "## Двухфакторная аутентификация\n"
                    "Даже если пароль украдут, без второго фактора войти не смогут.\n"
                ),
            },
        ]
        courses = []
        for cd in courses_data:
            c = Course(**cd)
            db.session.add(c)
            courses.append(c)
        db.session.flush()

        # ---------------- Квизы ----------------
        quiz = Quiz(title="Квиз: Распознай фишинг", course_id=courses[1].id)
        db.session.add(quiz)
        db.session.flush()
        qs = [
            {
                "text": "Пришло письмо: «Ваш аккаунт МТС будет заблокирован через 1 час, "
                        "подтвердите данные по ссылке mts-secure.ru». Ваши действия?",
                "options": [
                    "Перейти по ссылке и ввести логин/пароль",
                    "Не переходить по ссылке и сообщить в службу безопасности",
                    "Переслать письмо коллегам",
                    "Ответить на письмо своими данными",
                ],
                "correct_index": 1,
                "explanation": "Срочность + чужой домен + просьба ввести данные = фишинг. "
                               "Не переходим, сообщаем в СБ.",
            },
            {
                "text": "Звонит «сотрудник банка» и просит назвать код из СМС для «отмены операции». Что делать?",
                "options": [
                    "Назвать код — ведь звонят из банка",
                    "Положить трубку, код никому не сообщать",
                    "Продиктовать код по буквам для надёжности",
                    "Перезвонить по номеру из СМС",
                ],
                "correct_index": 1,
                "explanation": "Коды из СМС нельзя сообщать НИКОМУ. Банк никогда их не спрашивает.",
            },
            {
                "text": "Какой пароль надёжнее?",
                "options": [
                    "Qwerty123",
                    "Дата рождения",
                    "синий-кофе-мост-77-река",
                    "Название компании",
                ],
                "correct_index": 2,
                "explanation": "Длинная парольная фраза из случайных слов гораздо надёжнее коротких «сложных» паролей.",
            },
        ]
        for q in qs:
            db.session.add(Question(quiz_id=quiz.id, **q))

        # ---------------- Фишинговые письма (инбокс) ----------------
        emails = [
            PhishingEmail(
                sender="security-alert@mts-verify.ru",
                sender_name="Служба безопасности МТС",
                subject="СРОЧНО: обнаружен вход в ваш аккаунт",
                body=("Здравствуйте!\n\nМы зафиксировали подозрительный вход в вашу "
                      "корпоративную учётную запись из другого города. Если это были не вы, "
                      "немедленно подтвердите личность в течение 2 часов, иначе аккаунт будет "
                      "заблокирован:\n\nhttp://mts-verify.ru/login\n\nСлужба безопасности МТС"),
                is_phishing=True, difficulty="easy",
                red_flags=[
                    "Домен mts-verify.ru не является официальным mts.ru",
                    "Давление срочностью и угроза блокировки",
                    "Прямая ссылка на ввод учётных данных",
                ],
            ),
            PhishingEmail(
                sender="hr@mts.ru",
                sender_name="Отдел кадров МТС",
                subject="График отпусков на согласование",
                body=("Добрый день!\n\nВо вложении — предварительный график отпусков отдела "
                      "на следующий квартал. Просьба проверить свои даты и написать, если есть "
                      "изменения, до пятницы.\n\nС уважением, отдел кадров"),
                is_phishing=False, difficulty="medium",
                red_flags=[],
            ),
            PhishingEmail(
                sender="no-reply@bonus-mts.ru",
                sender_name="Бонусная программа МТС",
                subject="Вам начислено 5000 бонусов! Заберите приз",
                body=("Поздравляем! Вы стали победителем розыгрыша среди сотрудников. "
                      "Чтобы получить приз, авторизуйтесь и укажите данные карты для "
                      "зачисления:\n\nhttp://bonus-mts.ru/win\n\nСпешите, предложение сгорает сегодня!"),
                is_phishing=True, difficulty="easy",
                red_flags=[
                    "Слишком хорошо, чтобы быть правдой",
                    "Просьба указать данные карты",
                    "Чужой домен bonus-mts.ru и давление срочностью",
                ],
            ),
            PhishingEmail(
                sender="i.director@mts.ru.corp-mail.net",
                sender_name="Иван Директоров",
                subject="Срочная задача (конфиденциально)",
                body=("Привет! Я сейчас на переговорах, не могу говорить по телефону. "
                      "Нужно срочно оплатить счёт нашему новому подрядчику, реквизиты "
                      "пришлю следующим письмом. Сделай перевод в течение часа и никому "
                      "пока не говори — сделка конфиденциальная. Директор"),
                is_phishing=True, difficulty="hard",
                red_flags=[
                    "Поддельный домен-обманка mts.ru.corp-mail.net",
                    "Приём «CEO fraud» — давление авторитетом руководителя",
                    "Срочность, секретность и просьба о переводе денег",
                ],
            ),
        ]
        for e in emails:
            db.session.add(e)

        db.session.commit()

        # ---------------- Немного истории для статистики ----------------
        employees = User.query.filter_by(role="employee").all()
        all_emails = PhishingEmail.query.all()
        for u in employees:
            for e in random.sample(all_emails, k=random.randint(1, len(all_emails))):
                correct = random.random() > 0.4
                db.session.add(PhishingResult(
                    user_id=u.id, email_id=e.id,
                    action="reported" if (correct == e.is_phishing) else "clicked",
                    correct=correct,
                ))
            db.session.add(QuizAttempt(
                user_id=u.id, quiz_id=quiz.id,
                score=random.randint(40, 100), total=3,
                correct=random.randint(1, 3),
            ))
        db.session.commit()

        print("[OK] База наполнена.")
        print("   admin@mts.ru / admin123   (админ)")
        print("   ivan@mts.ru  / user123    (сотрудник)")


if __name__ == "__main__":
    run()
