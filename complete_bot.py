"""
https://github.com/MakerMagic/
"""

import logging
import sqlite3
from datetime import datetime, timedelta
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
import pytz

# ============= НАСТРОЙКИ =============
BOT_TOKEN = "blablaboobpip"  # Твой токен
ADMIN_ID = 67676767  # Твой ID
ALMATY_TZ = pytz.timezone('Asia/Almaty')

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

WEEKDAYS = ['Понедельник', 'Вторник', 'Среда', 'Четверг', 'Пятница', 'Суббота', 'Воскресенье']

# ============= БАЗА ДАННЫХ =============

def get_db():
    conn = sqlite3.connect('tutor_bot.db')
    conn.row_factory = sqlite3.Row
    return conn

def init_database():
    conn = get_db()
    c = conn.cursor()

    c.execute('''CREATE TABLE IF NOT EXISTS registration_requests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER UNIQUE NOT NULL,
        username TEXT,
        full_name TEXT,
        request_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        status TEXT DEFAULT 'pending'
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS students (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER UNIQUE NOT NULL,
        username TEXT,
        nickname TEXT,
        full_name TEXT,
        subject TEXT,
        rate INTEGER,
        lesson_duration INTEGER DEFAULT 60,
        payment_type TEXT DEFAULT 'месяц',
        lessons_per_week INTEGER DEFAULT 1,
        paid_until DATE,
        remaining_lessons INTEGER DEFAULT 0,
        next_payment_date DATE,
        added_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS permanent_schedule (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id INTEGER,
        day_of_week INTEGER,
        time TEXT,
        UNIQUE(student_id, day_of_week),
        FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS schedule_changes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id INTEGER,
        original_date DATE,
        new_date DATE,
        new_time TEXT,
        week_start DATE,
        UNIQUE(student_id, original_date),
        FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS homework (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id INTEGER,
        due_date DATE,
        description TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS payments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id INTEGER,
        payment_type TEXT,
        lessons_count INTEGER,
        payment_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        valid_until DATE,
        FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS sent_notifications (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id INTEGER,
        notification_type TEXT,
        notification_date DATE,
        UNIQUE(student_id, notification_type, notification_date)
    )''')

    # Добавляем nickname если не существует (для старых баз)
    try:
        c.execute("ALTER TABLE students ADD COLUMN nickname TEXT")
    except:
        pass

    conn.commit()
    conn.close()
    logger.info("✅ Database initialized")

# ============= ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ =============

def is_admin(user_id):
    return user_id == ADMIN_ID

def get_week_start(date=None):
    if date is None:
        date = datetime.now(ALMATY_TZ).date()
    return date - timedelta(days=date.weekday())

def parse_date(date_str):
    if not date_str:
        return None
    if hasattr(date_str, 'weekday'):
        return date_str
    try:
        return datetime.strptime(str(date_str), '%Y-%m-%d').date()
    except:
        try:
            return datetime.strptime(str(date_str), '%d.%m.%Y').date()
        except:
            return None

def fmt_date(date_str):
    d = parse_date(date_str)
    if not d:
        return str(date_str)
    return f"{d.strftime('%d.%m.%Y')} ({WEEKDAYS[d.weekday()]})"

def get_student_by_nickname(name):
    """Найти ученика по никнейму ИЛИ @username"""
    conn = get_db()
    c = conn.cursor()
    clean = name.replace('@', '')
    c.execute("SELECT * FROM students WHERE nickname = ? OR username = ?", (clean, clean))
    s = c.fetchone()
    conn.close()
    return s

def get_student_by_user_id(user_id):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM students WHERE user_id = ?", (user_id,))
    s = c.fetchone()
    conn.close()
    return s

def display_name(student):
    """Отображаемое имя ученика"""
    return student['nickname'] or student['full_name'] or student['username'] or 'Неизвестный'

# ============= КОМАНДЫ УЧЕНИКОВ =============

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if is_admin(user_id):
        await update.message.reply_text(
            "👨‍💼 АДМИН-ПАНЕЛЬ\n\n"
            "📋 Запросы:\n"
            "/requests - Посмотреть запросы\n"
            "/accept @username - Принять\n"
            "/reject @username - Отклонить\n\n"
            "👥 Ученики:\n"
            "/students - Список учеников\n"
            "/remove Никнейм - Удалить ученика\n"
            "/setnickname @username Никнейм - Задать никнейм\n\n"
            "📅 Расписание:\n"
            "/addschedule Никнейм день время\n"
            "  Пример: /addschedule Макс 1 14:00\n"
            "  Дни: 0=Пн, 1=Вт, 2=Ср, 3=Чт, 4=Пт, 5=Сб, 6=Вс\n"
            "/removeschedule Никнейм день\n"
            "/reschedule Никнейм стар_дата нов_дата время\n\n"
            "📝 Домашка:\n"
            "/addhw Никнейм дата текст\n"
            "/deletehw Никнейм дата\n\n"
            "📚 Тема и настройки:\n"
            "/setsubject Никнейм тема\n"
            "/setrate Никнейм ставка\n"
            "/setduration Никнейм минуты\n\n"
            "💰 Оплата:\n"
            "/addpayment Никнейм тип количество\n"
            "  Типы: день, неделя, месяц\n"
            "/clearpayment Никнейм - Очистить оплату\n\n"
            "📢 /announce текст - Объявление всем"
        )
        return

    student = get_student_by_user_id(user_id)
    if student:
        name = display_name(student)
        await update.message.reply_text(
            f"👋 Привет, {name}!\n\n"
            "📋 Доступные команды:\n"
            "/schedule - Моё постоянное расписание\n"
            "/thisweek - Расписание на этой неделе\n"
            "/homework - Моя домашка\n"
            "/info - Моя информация\n"
            "/payment - Информация об оплате"
        )
        return

    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM registration_requests WHERE user_id = ? AND status = 'pending'", (user_id,))
    existing = c.fetchone()
    conn.close()

    if existing:
        await update.message.reply_text(
            "⏳ Твой запрос уже отправлен!\n\nОжидай подтверждения от преподавателя."
        )
        return

    await update.message.reply_text(
        "👋 Привет! Добро пожаловать!\n\n"
        "Чтобы начать, отправь запрос на регистрацию.\n"
        "Используй команду: /register"
    )

async def register(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    username = update.effective_user.username or ""
    full_name = update.effective_user.full_name or ""

    conn = get_db()
    c = conn.cursor()

    c.execute("SELECT * FROM registration_requests WHERE user_id = ? AND status = 'pending'", (user_id,))
    if c.fetchone():
        await update.message.reply_text("⏳ Твой запрос уже отправлен! Ожидай подтверждения.")
        conn.close()
        return

    c.execute("SELECT * FROM students WHERE user_id = ?", (user_id,))
    if c.fetchone():
        await update.message.reply_text("✅ Ты уже зарегистрирован! Используй /start")
        conn.close()
        return

    c.execute("INSERT INTO registration_requests (user_id, username, full_name, status) VALUES (?, ?, ?, 'pending')",
              (user_id, username, full_name))
    conn.commit()
    conn.close()

    await update.message.reply_text(
        "✅ Твой запрос отправлен преподавателю!\n\nОжидай подтверждения. Тебе придёт уведомление."
    )

    try:
        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=f"🔔 Новый запрос на регистрацию!\n\n"
                 f"👤 Имя: {full_name}\n"
                 f"ID: @{username}\n\n"
                 f"/accept @{username} - Принять\n"
                 f"/reject @{username} - Отклонить"
        )
    except Exception as e:
        logger.error(f"Failed to notify admin: {e}")

async def my_schedule(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    student = get_student_by_user_id(user_id)

    if not student:
        await update.message.reply_text("❌ Ты не зарегистрирован. Используй /register")
        return

    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT day_of_week, time FROM permanent_schedule WHERE student_id = ? ORDER BY day_of_week",
              (student['id'],))
    schedule = c.fetchall()
    conn.close()

    if not schedule:
        await update.message.reply_text("📭 У тебя пока нет постоянного расписания.")
        return

    text = "📅 Твоё постоянное расписание:\n\n"
    for item in schedule:
        text += f"▪️ {WEEKDAYS[item['day_of_week']]} в {item['time']}\n"

    await update.message.reply_text(text)

async def this_week_schedule(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    student = get_student_by_user_id(user_id)

    if not student:
        await update.message.reply_text("❌ Ты не зарегистрирован. Используй /register")
        return

    week_start = get_week_start()
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT day_of_week, time FROM permanent_schedule WHERE student_id = ?", (student['id'],))
    permanent = c.fetchall()

    c.execute("SELECT * FROM schedule_changes WHERE student_id = ? AND week_start = ?",
              (student['id'], str(week_start)))
    changes = c.fetchall()
    conn.close()

    if not permanent:
        await update.message.reply_text("📭 У тебя пока нет расписания.")
        return

    changes_dict = {row['original_date']: row for row in changes}

    text = "📅 Расписание на этой неделе:\n\n"
    for item in permanent:
        lesson_date = week_start + timedelta(days=item['day_of_week'])
        lesson_date_str = str(lesson_date)

        if lesson_date_str in changes_dict:
            change = changes_dict[lesson_date_str]
            text += f"▪️ {fmt_date(lesson_date_str)} в {item['time']} → ПЕРЕНОС на {fmt_date(change['new_date'])} в {change['new_time']}\n"
        else:
            text += f"▪️ {fmt_date(lesson_date_str)} в {item['time']}\n"

    if changes:
        text += "\n⚠️ На этой неделе есть переносы!"
    else:
        text += "\n✅ Переносов нет."

    await update.message.reply_text(text)

async def my_homework(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    student = get_student_by_user_id(user_id)

    if not student:
        await update.message.reply_text("❌ Ты не зарегистрирован. Используй /register")
        return

    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM homework WHERE student_id = ? AND due_date >= date('now') ORDER BY due_date",
              (student['id'],))
    homework = c.fetchall()
    conn.close()

    if not homework:
        await update.message.reply_text("📭 Нет домашних заданий.")
        return

    text = "📝 Твои домашние задания:\n\n"
    for hw in homework:
        text += f"📅 {fmt_date(hw['due_date'])}\n"
        text += f"📖 {hw['description']}\n\n"

    await update.message.reply_text(text)

async def my_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    student = get_student_by_user_id(user_id)

    if not student:
        await update.message.reply_text("❌ Ты не зарегистрирован. Используй /register")
        return

    name = display_name(student)
    text = f"👤 Информация:\n\n"
    text += f"📚 Предмет: {student['subject'] or 'не указан'}\n"
    text += f"💰 Ставка: {student['rate'] or 'не указана'} тенге\n"
    text += f"⏱ Длительность: {student['lesson_duration']} минут\n"

    await update.message.reply_text(text)

async def my_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    student = get_student_by_user_id(user_id)

    if not student:
        await update.message.reply_text("❌ Ты не зарегистрирован. Используй /register")
        return

    text = "💳 Информация об оплате:\n\n"
    text += f"📋 Тип оплаты: {student['payment_type']}\n"

    if student['remaining_lessons']:
        text += f"📊 Осталось занятий: {student['remaining_lessons']}\n"

    if student['paid_until']:
        text += f"✅ Оплачено до (включительно): {fmt_date(student['paid_until'])}\n"

    if student['next_payment_date']:
        text += f"⏰ Следующая оплата с: {fmt_date(student['next_payment_date'])}\n"
    else:
        text += "\n⚠️ Информация об оплате не установлена."

    await update.message.reply_text(text)

# ============= КОМАНДЫ АДМИНА =============

async def view_requests(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return

    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM registration_requests WHERE status = 'pending' ORDER BY request_date")
    requests = c.fetchall()
    conn.close()

    if not requests:
        await update.message.reply_text("📭 Нет новых запросов.")
        return

    text = "📋 Запросы на регистрацию:\n\n"
    for req in requests:
        text += f"👤 {req['full_name']}\n"
        text += f"🆔 @{req['username']}\n"
        text += f"/accept @{req['username']} - Принять\n"
        text += f"/reject @{req['username']} - Отклонить\n\n"

    await update.message.reply_text(text)

async def accept_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return

    if not context.args:
        await update.message.reply_text("Используй: /accept @username")
        return

    username = context.args[0].replace('@', '')
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM registration_requests WHERE username = ? AND status = 'pending'", (username,))
    req = c.fetchone()

    if not req:
        await update.message.reply_text(f"❌ Запрос от @{username} не найден.")
        conn.close()
        return

    c.execute("INSERT INTO students (user_id, username, full_name) VALUES (?, ?, ?)",
              (req['user_id'], req['username'], req['full_name']))
    c.execute("UPDATE registration_requests SET status = 'accepted' WHERE id = ?", (req['id'],))
    conn.commit()
    conn.close()

    await update.message.reply_text(f"✅ Ученик @{username} добавлен!\n\nНе забудь задать никнейм:\n/setnickname @{username} Имя")

    try:
        await context.bot.send_message(
            chat_id=req['user_id'],
            text="🎉 Твой запрос одобрен!\n\nТеперь ты в базе. Используй /start"
        )
    except Exception as e:
        logger.error(f"Failed to notify: {e}")

async def reject_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return

    if not context.args:
        await update.message.reply_text("Используй: /reject @username")
        return

    username = context.args[0].replace('@', '')
    conn = get_db()
    c = conn.cursor()
    c.execute("UPDATE registration_requests SET status = 'rejected' WHERE username = ? AND status = 'pending'",
              (username,))
    affected = c.rowcount
    conn.commit()
    conn.close()

    if affected:
        await update.message.reply_text(f"❌ Запрос от @{username} отклонён.")
    else:
        await update.message.reply_text("❌ Запрос не найден.")

async def list_students(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return

    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM students ORDER BY nickname, username")
    students = c.fetchall()
    conn.close()

    if not students:
        await update.message.reply_text("📭 Пока нет учеников.")
        return

    text = "👥 Список учеников:\n\n"
    for s in students:
        name = display_name(s)
        text += f"▪️ {name} (@{s['username']})\n"
        if s['subject']:
            text += f"   📚 {s['subject']}\n"

    await update.message.reply_text(text)

async def set_nickname(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /setnickname @username Никнейм"""
    if not is_admin(update.effective_user.id):
        return

    if len(context.args) < 2:
        await update.message.reply_text(
            "Используй: /setnickname @username Никнейм\n"
            "Пример: /setnickname @ivan Макс"
        )
        return

    username = context.args[0].replace('@', '')
    nickname = ' '.join(context.args[1:])

    conn = get_db()
    c = conn.cursor()
    c.execute("UPDATE students SET nickname = ? WHERE username = ?", (nickname, username))
    affected = c.rowcount
    conn.commit()
    conn.close()

    if affected:
        await update.message.reply_text(f"✅ Никнейм для @{username}: {nickname}\n\nТеперь можешь обращаться как:\n/addhw {nickname} ...")
    else:
        await update.message.reply_text(f"❌ Ученик @{username} не найден.")

async def remove_student(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return

    if not context.args:
        await update.message.reply_text("Используй: /remove Никнейм")
        return

    name = ' '.join(context.args).replace('@', '')
    student = get_student_by_nickname(name)

    if not student:
        await update.message.reply_text(f"❌ Ученик {name} не найден.")
        return

    conn = get_db()
    c = conn.cursor()
    c.execute("DELETE FROM students WHERE id = ?", (student['id'],))
    conn.commit()
    conn.close()

    name_display = display_name(student)
    await update.message.reply_text(f"✅ Ученик {name_display} удалён.")

    try:
        await context.bot.send_message(
            chat_id=student['user_id'],
            text="👋 Рад был с тобой поработать!\n\nТы удалён из базы. Если захочешь вернуться - /register"
        )
    except Exception as e:
        logger.error(f"Failed to notify: {e}")

async def add_schedule(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return

    if len(context.args) < 3:
        await update.message.reply_text(
            "Используй: /addschedule Никнейм день время\n\n"
            "Пример: /addschedule Макс 1 14:00\n"
            "Дни: 0=Пн, 1=Вт, 2=Ср, 3=Чт, 4=Пт, 5=Сб, 6=Вс"
        )
        return

    name = context.args[0].replace('@', '')
    try:
        day = int(context.args[1])
        time_str = context.args[2]
    except:
        await update.message.reply_text("❌ День - число 0-6, время - ЧЧ:ММ")
        return

    student = get_student_by_nickname(name)
    if not student:
        await update.message.reply_text(f"❌ Ученик {name} не найден.")
        return

    conn = get_db()
    c = conn.cursor()
    try:
        c.execute("INSERT OR REPLACE INTO permanent_schedule (student_id, day_of_week, time) VALUES (?, ?, ?)",
                  (student['id'], day, time_str))
        conn.commit()
        name_display = display_name(student)
        await update.message.reply_text(f"✅ Добавлено: {name_display} - {WEEKDAYS[day]} в {time_str}")
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка: {e}")
    finally:
        conn.close()

async def remove_schedule(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return

    if len(context.args) < 2:
        await update.message.reply_text("Используй: /removeschedule Никнейм день\nПример: /removeschedule Макс 1")
        return

    name = context.args[0].replace('@', '')
    try:
        day = int(context.args[1])
    except:
        await update.message.reply_text("❌ День должен быть числом 0-6")
        return

    student = get_student_by_nickname(name)
    if not student:
        await update.message.reply_text(f"❌ Ученик {name} не найден.")
        return

    conn = get_db()
    c = conn.cursor()
    c.execute("DELETE FROM permanent_schedule WHERE student_id = ? AND day_of_week = ?", (student['id'], day))
    affected = c.rowcount
    conn.commit()
    conn.close()

    if affected:
        name_display = display_name(student)
        await update.message.reply_text(f"✅ Удалено занятие {name_display} в {WEEKDAYS[day]}")
    else:
        await update.message.reply_text("❌ Занятие не найдено")

async def reschedule_lesson(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return

    if len(context.args) < 4:
        await update.message.reply_text(
            "Используй: /reschedule Никнейм старая_дата новая_дата время\n\n"
            "Пример: /reschedule Макс 18.02.2026 19.02.2026 15:00"
        )
        return

    name = context.args[0].replace('@', '')
    try:
        old_date = datetime.strptime(context.args[1], '%d.%m.%Y').date()
        new_date = datetime.strptime(context.args[2], '%d.%m.%Y').date()
        new_time = context.args[3]
    except:
        await update.message.reply_text("❌ Формат даты: ДД.ММ.ГГГГ")
        return

    student = get_student_by_nickname(name)
    if not student:
        await update.message.reply_text(f"❌ Ученик {name} не найден.")
        return

    week_start = get_week_start(old_date)
    conn = get_db()
    c = conn.cursor()
    try:
        c.execute("""INSERT OR REPLACE INTO schedule_changes
                     (student_id, original_date, new_date, new_time, week_start)
                     VALUES (?, ?, ?, ?, ?)""",
                  (student['id'], str(old_date), str(new_date), new_time, str(week_start)))
        conn.commit()
        name_display = display_name(student)
        await update.message.reply_text(
            f"✅ Перенос создан!\n\n"
            f"{name_display}\n"
            f"С {fmt_date(old_date)}\n"
            f"На {fmt_date(new_date)} в {new_time}"
        )
        try:
            await context.bot.send_message(
                chat_id=student['user_id'],
                text=f"📅 ПЕРЕНОС ЗАНЯТИЯ\n\nЗанятие {fmt_date(old_date)}\nперенесено на {fmt_date(new_date)} в {new_time}"
            )
        except:
            pass
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка: {e}")
    finally:
        conn.close()

async def add_homework(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return

    if len(context.args) < 3:
        await update.message.reply_text(
            "Используй: /addhw Никнейм дата текст\n\n"
            "Пример: /addhw Макс 20.02.2026 Решить задачи 1-10"
        )
        return

    name = context.args[0].replace('@', '')
    try:
        due_date = datetime.strptime(context.args[1], '%d.%m.%Y').date()
    except:
        await update.message.reply_text("❌ Формат даты: ДД.ММ.ГГГГ")
        return

    description = ' '.join(context.args[2:])
    student = get_student_by_nickname(name)
    if not student:
        await update.message.reply_text(f"❌ Ученик {name} не найден.")
        return

    conn = get_db()
    c = conn.cursor()
    c.execute("INSERT INTO homework (student_id, due_date, description) VALUES (?, ?, ?)",
              (student['id'], str(due_date), description))
    conn.commit()
    conn.close()

    name_display = display_name(student)
    await update.message.reply_text(f"✅ Домашка добавлена для {name_display}\nНа {fmt_date(due_date)}")

    try:
        await context.bot.send_message(
            chat_id=student['user_id'],
            text=f"📝 Новая домашка!\n\nНа {fmt_date(due_date)}\n📖 {description}"
        )
    except:
        pass

async def delete_homework(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /deletehw Никнейм дата"""
    if not is_admin(update.effective_user.id):
        return

    if len(context.args) < 2:
        await update.message.reply_text(
            "Используй: /deletehw Никнейм дата\n\n"
            "Пример: /deletehw Макс 20.02.2026"
        )
        return

    name = context.args[0].replace('@', '')
    try:
        due_date = datetime.strptime(context.args[1], '%d.%m.%Y').date()
    except:
        await update.message.reply_text("❌ Формат даты: ДД.ММ.ГГГГ")
        return

    student = get_student_by_nickname(name)
    if not student:
        await update.message.reply_text(f"❌ Ученик {name} не найден.")
        return

    conn = get_db()
    c = conn.cursor()
    c.execute("DELETE FROM homework WHERE student_id = ? AND due_date = ?", (student['id'], str(due_date)))
    affected = c.rowcount
    conn.commit()
    conn.close()

    name_display = display_name(student)
    if affected:
        await update.message.reply_text(f"✅ Домашка для {name_display} на {fmt_date(due_date)} удалена!")
    else:
        await update.message.reply_text("❌ Домашка на эту дату не найдена.")

async def set_subject(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return

    if len(context.args) < 2:
        await update.message.reply_text("Используй: /setsubject Никнейм тема\nПример: /setsubject Макс SAT MATH")
        return

    name = context.args[0].replace('@', '')
    subject = ' '.join(context.args[1:])
    student = get_student_by_nickname(name)
    if not student:
        await update.message.reply_text(f"❌ Ученик {name} не найден.")
        return

    conn = get_db()
    c = conn.cursor()
    c.execute("UPDATE students SET subject = ? WHERE id = ?", (subject, student['id']))
    conn.commit()
    conn.close()

    name_display = display_name(student)
    await update.message.reply_text(f"✅ Тема для {name_display}: {subject}")

async def set_rate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return

    if len(context.args) < 2:
        await update.message.reply_text("Используй: /setrate Никнейм ставка\nПример: /setrate Макс 5000")
        return

    name = context.args[0].replace('@', '')
    try:
        rate = int(context.args[1])
    except:
        await update.message.reply_text("❌ Ставка должна быть числом")
        return

    student = get_student_by_nickname(name)
    if not student:
        await update.message.reply_text(f"❌ Ученик {name} не найден.")
        return

    conn = get_db()
    c = conn.cursor()
    c.execute("UPDATE students SET rate = ? WHERE id = ?", (rate, student['id']))
    conn.commit()
    conn.close()

    name_display = display_name(student)
    await update.message.reply_text(f"✅ Ставка для {name_display}: {rate} тенге")

async def set_duration(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return

    if len(context.args) < 2:
        await update.message.reply_text("Используй: /setduration Никнейм минуты\nПример: /setduration Макс 75")
        return

    name = context.args[0].replace('@', '')
    try:
        duration = int(context.args[1])
    except:
        await update.message.reply_text("❌ Длительность должна быть числом")
        return

    student = get_student_by_nickname(name)
    if not student:
        await update.message.reply_text(f"❌ Ученик {name} не найден.")
        return

    conn = get_db()
    c = conn.cursor()
    c.execute("UPDATE students SET lesson_duration = ? WHERE id = ?", (duration, student['id']))
    conn.commit()
    conn.close()

    name_display = display_name(student)
    await update.message.reply_text(f"✅ Длительность для {name_display}: {duration} минут")

async def add_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return

    if len(context.args) < 3:
        await update.message.reply_text(
            "Используй: /addpayment Никнейм тип количество\n\n"
            "Пример: /addpayment Макс месяц 8\n"
            "Типы: день, неделя, месяц"
        )
        return

    name = context.args[0].replace('@', '')
    payment_type = context.args[1].lower()
    try:
        lessons_count = int(context.args[2])
    except:
        await update.message.reply_text("❌ Количество должно быть числом")
        return

    if payment_type not in ['день', 'неделя', 'месяц']:
        await update.message.reply_text("❌ Тип: день, неделя или месяц")
        return

    student = get_student_by_nickname(name)
    if not student:
        await update.message.reply_text(f"❌ Ученик {name} не найден.")
        return

    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT day_of_week FROM permanent_schedule WHERE student_id = ? ORDER BY day_of_week",
              (student['id'],))
    schedule = c.fetchall()

    if not schedule:
        await update.message.reply_text("❌ У ученика нет расписания! Сначала добавь через /addschedule")
        conn.close()
        return

    lesson_days = [row['day_of_week'] for row in schedule]
    lessons_per_week = len(lesson_days)
    today = datetime.now(ALMATY_TZ).date()

    # Считаем дату последнего оплаченного занятия
    paid_until = today
    count = 0
    check_date = today
    while count < lessons_count:
        check_date += timedelta(days=1)
        if check_date.weekday() in lesson_days:
            count += 1
            paid_until = check_date

    # Следующая дата оплаты = следующий день занятия после paid_until
    next_payment = paid_until + timedelta(days=1)
    while next_payment.weekday() not in lesson_days:
        next_payment += timedelta(days=1)

    # Текущие remaining_lessons
    current_remaining = student['remaining_lessons'] or 0

    c.execute(
        """UPDATE students SET
           payment_type = ?,
           lessons_per_week = ?,
           remaining_lessons = ?,
           paid_until = ?,
           next_payment_date = ?
           WHERE id = ?""",
        (payment_type, lessons_per_week, current_remaining + lessons_count,
         str(paid_until), str(next_payment), student['id'])
    )
    c.execute("INSERT INTO payments (student_id, payment_type, lessons_count, valid_until) VALUES (?, ?, ?, ?)",
              (student['id'], payment_type, lessons_count, str(paid_until)))
    conn.commit()
    conn.close()

    name_display = display_name(student)
    await update.message.reply_text(
        f"✅ Оплата добавлена!\n\n"
        f"👤 {name_display}\n"
        f"💳 Тип: {payment_type}\n"
        f"📊 Занятий: {lessons_count}\n"
        f"✅ Оплачено до (включительно): {fmt_date(paid_until)}\n"
        f"⏰ Следующая оплата с: {fmt_date(next_payment)}"
    )

async def clear_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /clearpayment Никнейм - очистить информацию об оплате"""
    if not is_admin(update.effective_user.id):
        return

    if not context.args:
        await update.message.reply_text("Используй: /clearpayment Никнейм\nПример: /clearpayment Макс")
        return

    name = ' '.join(context.args).replace('@', '')
    student = get_student_by_nickname(name)
    if not student:
        await update.message.reply_text(f"❌ Ученик {name} не найден.")
        return

    conn = get_db()
    c = conn.cursor()
    c.execute("""UPDATE students SET
               paid_until = NULL,
               next_payment_date = NULL,
               remaining_lessons = 0
               WHERE id = ?""", (student['id'],))
    conn.commit()
    conn.close()

    name_display = display_name(student)
    await update.message.reply_text(f"✅ Информация об оплате для {name_display} очищена!")

async def announce(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return

    if not context.args:
        await update.message.reply_text("Используй: /announce текст объявления")
        return

    announcement = ' '.join(context.args)
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT user_id, username, nickname FROM students")
    students = c.fetchall()
    conn.close()

    if not students:
        await update.message.reply_text("📭 Нет учеников.")
        return

    success = 0
    failed = 0
    for student in students:
        try:
            await context.bot.send_message(
                chat_id=student['user_id'],
                text=f"📢 ОБЪЯВЛЕНИЕ\n\n{announcement}"
            )
            success += 1
        except Exception as e:
            logger.error(f"Failed: {e}")
            failed += 1

    await update.message.reply_text(f"✅ Отправлено: {success}\n❌ Ошибок: {failed}")

# ============= ПЛАНИРОВЩИК =============

async def send_lesson_reminders(context):
    conn = get_db()
    c = conn.cursor()
    c.execute("""SELECT DISTINCT s.*, ps.day_of_week, ps.time
                 FROM students s
                 JOIN permanent_schedule ps ON s.id = ps.student_id""")
    students = c.fetchall()

    today = datetime.now(ALMATY_TZ).date()
    today_weekday = today.weekday()

    for student in students:
        if student['day_of_week'] != today_weekday:
            continue

        c.execute("""SELECT * FROM sent_notifications
                     WHERE student_id = ? AND notification_type = 'lesson_reminder' AND notification_date = ?""",
                  (student['id'], str(today)))
        if c.fetchone():
            continue

        c.execute("SELECT * FROM schedule_changes WHERE student_id = ? AND original_date = ?",
                  (student['id'], str(today)))
        change = c.fetchone()

        name = display_name(student)

        if change:
            text = (f"⏰ {name}, напоминание о занятии!\n\n"
                    f"Сегодня ПЕРЕНОС\n"
                    f"На {fmt_date(change['new_date'])} в {change['new_time']}\n"
                    f"Предмет: {student['subject'] or 'не указан'}")
        else:
            text = (f"⏰ {name}, напоминание о занятии!\n\n"
                    f"Сегодня {fmt_date(today)} в {student['time']}\n"
                    f"Предмет: {student['subject'] or 'не указан'}")

        try:
            await context.bot.send_message(chat_id=student['user_id'], text=text)
            c.execute("""INSERT OR IGNORE INTO sent_notifications
                         (student_id, notification_type, notification_date) VALUES (?, 'lesson_reminder', ?)""",
                      (student['id'], str(today)))
            conn.commit()
        except Exception as e:
            logger.error(f"Failed to send reminder: {e}")

    conn.close()

async def send_payment_reminders(context):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM students WHERE next_payment_date IS NOT NULL")
    students = c.fetchall()
    today = datetime.now(ALMATY_TZ).date()

    for student in students:
        next_payment = parse_date(student['next_payment_date'])
        if not next_payment:
            continue

        payment_type = student['payment_type']
        remind_days = 5 if payment_type == 'месяц' else (1 if payment_type == 'неделя' else 0)
        remind_date = next_payment - timedelta(days=remind_days)

        if today != remind_date:
            continue

        c.execute("""SELECT * FROM sent_notifications
                     WHERE student_id = ? AND notification_type = 'payment_reminder' AND notification_date = ?""",
                  (student['id'], str(today)))
        if c.fetchone():
            continue

        name = display_name(student)
        text = (f"💳 {name}, напоминание об оплате!\n\n"
                f"Оплачено до: {fmt_date(student['paid_until'])}\n"
                f"Следующая оплата с: {fmt_date(student['next_payment_date'])}\n"
                f"Осталось занятий: {student['remaining_lessons']}\n"
                f"Ставка: {student['rate']} тенге")

        try:
            await context.bot.send_message(chat_id=student['user_id'], text=text)
            c.execute("""INSERT OR IGNORE INTO sent_notifications
                         (student_id, notification_type, notification_date) VALUES (?, 'payment_reminder', ?)""",
                      (student['id'], str(today)))
            conn.commit()
        except Exception as e:
            logger.error(f"Failed to send payment reminder: {e}")

    conn.close()

async def update_remaining_lessons(context):
    conn = get_db()
    c = conn.cursor()
    today = datetime.now(ALMATY_TZ).date()

    c.execute("""SELECT s.id, s.remaining_lessons FROM students s
                 JOIN permanent_schedule ps ON s.id = ps.student_id
                 WHERE ps.day_of_week = ? AND s.remaining_lessons > 0""",
              (today.weekday(),))
    students = c.fetchall()

    for student in students:
        c.execute("UPDATE students SET remaining_lessons = ? WHERE id = ?",
                  (student['remaining_lessons'] - 1, student['id']))

    conn.commit()
    conn.close()
