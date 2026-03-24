"""
Telegram Bot Module for teacherTools application.
Integrates with Flask-SQLAlchemy models using webhook mode for PythonAnywhere.
"""

import os
import logging
import asyncio
from datetime import datetime, timedelta
from typing import Optional, List

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Global variables for database access
_db = None
_app = None
_bot_application = None


def init_bot(db, flask_app):
    """Initialize bot with database and Flask app references."""
    global _db, _app, _bot_application
    _db = db
    _app = flask_app
    
    # Initialize bot application for webhook mode
    token = os.environ.get('TELEGRAM_BOT_TOKEN')
    if token:
        _bot_application = Application.builder().token(token).build()
        _setup_handlers(_bot_application)
        logger.info("Bot application initialized for webhook mode")


# ============================================================================
# Database Models
# ============================================================================

def get_teacher_telegram_model():
    """Get or create TeacherTelegram model."""
    from models import db

    class TeacherTelegram(db.Model):
        """Model to link Telegram users to Teachers."""
        __tablename__ = 'teacher_telegram'

        id = db.Column(db.Integer, primary_key=True)
        teacher_id = db.Column(db.Integer, db.ForeignKey('teacher.id'), nullable=False, unique=True)
        telegram_chat_id = db.Column(db.BigInteger, nullable=False, unique=True)
        telegram_username = db.Column(db.String(100))
        first_name = db.Column(db.String(100))
        last_name = db.Column(db.String(100))
        is_active = db.Column(db.Boolean, default=True)
        created_at = db.Column(db.DateTime, default=datetime.utcnow)
        updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

        def __repr__(self):
            return f'<TeacherTelegram teacher_id={self.teacher_id} chat_id={self.telegram_chat_id}>'

    return TeacherTelegram


# ============================================================================
# Helper Functions
# ============================================================================

def get_teacher_by_chat_id(chat_id: int) -> Optional[object]:
    """Get teacher by Telegram chat ID."""
    from models import Teacher
    TeacherTelegram = get_teacher_telegram_model()

    with _app.app_context():
        link = TeacherTelegram.query.filter_by(
            telegram_chat_id=chat_id,
            is_active=True
        ).first()

        if link:
            return Teacher.query.get(link.teacher_id)
    return None


def get_teacher_groups(teacher_id: int) -> List[object]:
    """Get all groups for a teacher."""
    from models import Group

    with _app.app_context():
        return Group.query.filter_by(teacher_id=teacher_id).all()


def get_group_by_name(teacher_id: int, group_name: str) -> Optional[object]:
    """Get group by name for a specific teacher."""
    from models import Group

    with _app.app_context():
        return Group.query.filter_by(
            teacher_id=teacher_id,
            name=group_name
        ).first()


def get_schedule_for_date(teacher_id: int, date: datetime.date) -> List[object]:
    """Get schedule for a specific date."""
    from models import Schedule, Group

    with _app.app_context():
        start_of_day = datetime.combine(date, datetime.min.time())
        end_of_day = datetime.combine(date, datetime.max.time())

        schedules = Schedule.query.filter(
            Schedule.teacher_id == teacher_id,
            Schedule.start_time >= start_of_day,
            Schedule.start_time <= end_of_day
        ).order_by(Schedule.start_time).all()

        return schedules


def format_schedule_list(schedules: List[object]) -> str:
    """Format schedule list for display."""
    from models import Group

    if not schedules:
        return "📅 На этот день занятий не запланировано."

    lines = ["📅 Расписание на день:"]

    for sched in schedules:
        start_time = sched.start_time.strftime('%H:%M')
        end_time = sched.end_time.strftime('%H:%M')

        # Get group name
        group_name = ""
        if sched.group_id:
            with _app.app_context():
                group = Group.query.get(sched.group_id)
                if group:
                    group_name = f" ({group.name})"

        classroom = f" 🏫 {sched.classroom}" if sched.classroom else ""

        lines.append(f"\n🕐 {start_time}-{end_time}{group_name}{classroom}")
        lines.append(f"   📖 {sched.title}")

    return "\n".join(lines)


def parse_date(date_str: str) -> Optional[datetime.date]:
    """Parse date string in various formats."""
    formats = ['%Y-%m-%d', '%d.%m.%Y', '%d/%m/%Y']

    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt).date()
        except ValueError:
            continue
    return None


def parse_time(time_str: str) -> Optional[datetime.time]:
    """Parse time string in HH:MM format."""
    try:
        return datetime.strptime(time_str, '%H:%M').time()
    except ValueError:
        return None


# ============================================================================
# Command Handlers
# ============================================================================

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command."""
    chat_id = update.effective_chat.id
    teacher = get_teacher_by_chat_id(chat_id)

    if teacher:
        await update.message.reply_text(
            f"👋 Здравствуйте, {teacher.username}!\n\n"
            "✅ Ваш Telegram аккаунт уже привязан к системе.\n\n"
            "📋 Доступные команды:\n"
            "/help - Показать все команды\n"
            "/today - Расписание на сегодня\n"
            "/schedule ДАТА - Расписание на конкретную дату (ГГГГ-ММ-ДД)\n"
            "/groups - Список групп\n"
            "/students ГРУППА - Список студентов группы\n"
            "/addgroup НАЗВАНИЕ КУРС ФОРМА - Добавить группу\n"
            "/addstudent ГРУППА ФИО [EMAIL] - Добавить студента\n"
            "/addlesson ГРУППА ДАТА НАЧАЛО КОНЕЦ ТЕМА [АУДИТОРИЯ] - Добавить занятие\n"
            "/deletelesson ID - Удалить занятие"
        )
    else:
        await update.message.reply_text(
            "👋 Добро пожаловать в teacherTools!\n\n"
            "❌ Ваш Telegram аккаунт не привязан к системе.\n\n"
            "🔑 Для привязки аккаунта:\n"
            "1. Войдите в веб-приложение teacherTools\n"
            "2. Перейдите в раздел настроек мессенджеров\n"
            "3. Добавьте ваш Telegram ID\n\n"
            "📋 Ваш Telegram ID: {}".format(chat_id)
        )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /help command."""
    await update.message.reply_text(
        "📚 *Справка по командам*\n\n"
        "*Расписание:*\n"
        "/today - Расписание на сегодня\n"
        "/schedule ДАТА - Расписание на дату (формат: ГГГГ-ММ-ДД)\n\n"
        "*Группы:*\n"
        "/groups - Список всех групп\n"
        "/addgroup НАЗВАНИЕ КУРС ФОРМА - Добавить группу\n"
        "  ФОРМА: очная, заочная, дистанционная\n\n"
        "*Студенты:*\n"
        "/students ГРУППА - Список студентов группы\n"
        "/addstudent ГРУППА ФИО [EMAIL] - Добавить студента\n\n"
        "*Занятия:*\n"
        "/addlesson ГРУППА ДАТА НАЧАЛО КОНЕЦ ТЕМА [АУДИТОРИЯ]\n"
        "  Пример: /addlesson ИВТ-101 2024-02-01 09:00 10:30 Математика 101\n"
        "/deletelesson ID - Удалить занятие по ID",
        parse_mode='Markdown'
    )


async def today_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /today command."""
    chat_id = update.effective_chat.id
    teacher = get_teacher_by_chat_id(chat_id)

    if not teacher:
        await update.message.reply_text(
            "❌ Вы не авторизованы. Используйте /start для получения информации о привязке аккаунта."
        )
        return

    today = datetime.now().date()
    schedules = get_schedule_for_date(teacher.id, today)

    message = format_schedule_list(schedules)
    await update.message.reply_text(message)


async def schedule_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /schedule command."""
    chat_id = update.effective_chat.id
    teacher = get_teacher_by_chat_id(chat_id)

    if not teacher:
        await update.message.reply_text(
            "❌ Вы не авторизованы. Используйте /start для получения информации о привязке аккаунта."
        )
        return

    if not context.args:
        await update.message.reply_text(
            "⚠️ Укажите дату в формате: /schedule ГГГГ-ММ-ДД\n"
            "Пример: /schedule 2024-02-01"
        )
        return

    date_str = context.args[0]
    date = parse_date(date_str)

    if not date:
        await update.message.reply_text(
            "❌ Неверный формат даты. Используйте: ГГГГ-ММ-ДД\n"
            "Пример: /schedule 2024-02-01"
        )
        return

    schedules = get_schedule_for_date(teacher.id, date)

    message = format_schedule_list(schedules)
    await update.message.reply_text(message)


async def groups_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /groups command."""
    chat_id = update.effective_chat.id
    teacher = get_teacher_by_chat_id(chat_id)

    if not teacher:
        await update.message.reply_text(
            "❌ Вы не авторизованы. Используйте /start для получения информации о привязке аккаунта."
        )
        return

    groups = get_teacher_groups(teacher.id)

    if not groups:
        await update.message.reply_text("📂 У вас пока нет групп.")
        return

    lines = ["📂 Ваши группы:"]
    for group in groups:
        lines.append(f"\n👥 {group.name}")
        lines.append(f"   📚 Курс: {group.course}")
        lines.append(f"   🎓 Форма: {group.education_form}")

    await update.message.reply_text("\n".join(lines))


async def students_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /students command."""
    chat_id = update.effective_chat.id
    teacher = get_teacher_by_chat_id(chat_id)

    if not teacher:
        await update.message.reply_text(
            "❌ Вы не авторизованы. Используйте /start для получения информации о привязке аккаунта."
        )
        return

    if not context.args:
        await update.message.reply_text(
            "⚠️ Укажите название группы: /students ГРУППА"
        )
        return

    group_name = context.args[0]
    group = get_group_by_name(teacher.id, group_name)

    if not group:
        await update.message.reply_text(
            f"❌ Группа '{group_name}' не найдена.\n"
            "Используйте /groups для просмотра доступных групп."
        )
        return

    with _app.app_context():
        from models import Student
        students = Student.query.filter_by(group_id=group.id).all()

    if not students:
        await update.message.reply_text(f"👥 В группе '{group_name}' пока нет студентов.")
        return

    lines = [f"👥 Студенты группы {group_name}:"]
    for i, student in enumerate(students, 1):
        email = f" 📧 {student.email}" if student.email else ""
        lines.append(f"{i}. {student.name}{email}")

    await update.message.reply_text("\n".join(lines))


async def addgroup_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /addgroup command."""
    chat_id = update.effective_chat.id
    teacher = get_teacher_by_chat_id(chat_id)

    if not teacher:
        await update.message.reply_text(
            "❌ Вы не авторизованы. Используйте /start для получения информации о привязке аккаунта."
        )
        return

    if len(context.args) < 3:
        await update.message.reply_text(
            "⚠️ Использование: /addgroup НАЗВАНИЕ КУРС ФОРМА\n"
            "Пример: /addgroup ИВТ-101 'Информатика' очная\n\n"
            "Формы обучения: очная, заочная, дистанционная"
        )
        return

    name = context.args[0]
    course = context.args[1]
    education_form = context.args[2]

    # Validate education form
    valid_forms = ['очная', 'заочная', 'дистанционная']
    if education_form not in valid_forms:
        await update.message.reply_text(
            f"❌ Неверная форма обучения. Допустимые значения: {', '.join(valid_forms)}"
        )
        return

    from models import Group, db

    with _app.app_context():
        # Check if group already exists
        existing = Group.query.filter_by(
            teacher_id=teacher.id,
            name=name
        ).first()

        if existing:
            await update.message.reply_text(
                f"❌ Группа '{name}' уже существует."
            )
            return

        # Create new group
        new_group = Group(
            name=name,
            course=course,
            education_form=education_form,
            teacher_id=teacher.id,
            color='#007bff'
        )

        db.session.add(new_group)
        db.session.commit()

    await update.message.reply_text(
        f"✅ Группа '{name}' успешно создана!\n"
        f"📚 Курс: {course}\n"
        f"🎓 Форма: {education_form}"
    )


async def addstudent_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /addstudent command."""
    chat_id = update.effective_chat.id
    teacher = get_teacher_by_chat_id(chat_id)

    if not teacher:
        await update.message.reply_text(
            "❌ Вы не авторизованы. Используйте /start для получения информации о привязке аккаунта."
        )
        return

    if len(context.args) < 2:
        await update.message.reply_text(
            "⚠️ Использование: /addstudent ГРУППА ФИО [EMAIL]\n"
            "Пример: /addstudent ИВТ-101 'Иванов Иван Иванович' ivan@example.com"
        )
        return

    group_name = context.args[0]
    student_name = context.args[1]
    email = context.args[2] if len(context.args) > 2 else None

    from models import Student, db

    with _app.app_context():
        group = get_group_by_name(teacher.id, group_name)

        if not group:
            await update.message.reply_text(
                f"❌ Группа '{group_name}' не найдена."
            )
            return

        # Create new student
        new_student = Student(
            name=student_name,
            email=email,
            group_id=group.id
        )

        db.session.add(new_student)
        db.session.commit()

    email_text = f"\n📧 Email: {email}" if email else ""
    await update.message.reply_text(
        f"✅ Студент успешно добавлен!\n"
        f"👤 ФИО: {student_name}{email_text}\n"
        f"👥 Группа: {group_name}"
    )


async def addlesson_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /addlesson command."""
    chat_id = update.effective_chat.id
    teacher = get_teacher_by_chat_id(chat_id)

    if not teacher:
        await update.message.reply_text(
            "❌ Вы не авторизованы. Используйте /start для получения информации о привязке аккаунта."
        )
        return

    if len(context.args) < 5:
        await update.message.reply_text(
            "⚠️ Использование: /addlesson ГРУППА ДАТА НАЧАЛО КОНЕЦ ТЕМА [АУДИТОРИЯ]\n"
            "Пример: /addlesson ИВТ-101 2024-02-01 09:00 10:30 Математика 101\n\n"
            "Дата: ГГГГ-ММ-ДД\n"
            "Время: ЧЧ:ММ"
        )
        return

    group_name = context.args[0]
    date_str = context.args[1]
    start_time_str = context.args[2]
    end_time_str = context.args[3]
    topic = context.args[4]
    classroom = context.args[5] if len(context.args) > 5 else None

    # Parse date and time
    date = parse_date(date_str)
    if not date:
        await update.message.reply_text("❌ Неверный формат даты. Используйте: ГГГГ-ММ-ДД")
        return

    start_time = parse_time(start_time_str)
    end_time = parse_time(end_time_str)

    if not start_time or not end_time:
        await update.message.reply_text("❌ Неверный формат времени. Используйте: ЧЧ:ММ")
        return

    from models import Schedule, Lesson, Attendance, db

    with _app.app_context():
        group = get_group_by_name(teacher.id, group_name)

        if not group:
            await update.message.reply_text(f"❌ Группа '{group_name}' не найдена.")
            return

        # Create datetime objects
        start_datetime = datetime.combine(date, start_time)
        end_datetime = datetime.combine(date, end_time)

        # Create Schedule entry
        schedule = Schedule(
            title=topic,
            start_time=start_datetime,
            end_time=end_datetime,
            group_id=group.id,
            teacher_id=teacher.id,
            classroom=classroom,
            color=group.color or '#007bff'
        )

        db.session.add(schedule)
        db.session.flush()  # Get schedule.id

        # Create Lesson entry (like calendar_module.py does)
        lesson = Lesson(
            date=start_datetime,
            group_id=group.id,
            topic=topic,
            classroom=classroom,
            teacher_id=teacher.id,
            subject=topic
        )

        db.session.add(lesson)
        db.session.flush()  # Get lesson.id

        # Create Attendance records for all students in the group
        students = group.students
        for student in students:
            attendance = Attendance(
                student_id=student.id,
                lesson_id=lesson.id,
                present=False,
                date=start_datetime
            )
            db.session.add(attendance)

        db.session.commit()

    classroom_text = f"\n🏫 Аудитория: {classroom}" if classroom else ""
    await update.message.reply_text(
        f"✅ Занятие успешно добавлено!\n"
        f"📖 Тема: {topic}\n"
        f"👥 Группа: {group_name}\n"
        f"📅 Дата: {date.strftime('%d.%m.%Y')}\n"
        f"🕐 Время: {start_time_str}-{end_time_str}{classroom_text}"
    )


async def deletelesson_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /deletelesson command."""
    chat_id = update.effective_chat.id
    teacher = get_teacher_by_chat_id(chat_id)

    if not teacher:
        await update.message.reply_text(
            "❌ Вы не авторизованы. Используйте /start для получения информации о привязке аккаунта."
        )
        return

    if not context.args:
        await update.message.reply_text(
            "⚠️ Укажите ID занятия: /deletelesson ID\n"
            "Используйте /today или /schedule для просмотра ID занятий."
        )
        return

    try:
        lesson_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("❌ ID занятия должен быть числом.")
        return

    from models import Schedule, Lesson, Attendance, db

    with _app.app_context():
        # Find schedule by ID and verify it belongs to this teacher
        schedule = Schedule.query.filter_by(
            id=lesson_id,
            teacher_id=teacher.id
        ).first()

        if not schedule:
            await update.message.reply_text(
                f"❌ Занятие с ID {lesson_id} не найдено или у вас нет доступа."
            )
            return

        # Find and delete related lesson
        lesson = Lesson.query.filter_by(
            date=schedule.start_time,
            group_id=schedule.group_id,
            teacher_id=teacher.id,
            topic=schedule.title
        ).first()

        if lesson:
            # Delete attendance records
            Attendance.query.filter_by(lesson_id=lesson.id).delete()
            # Delete lesson
            db.session.delete(lesson)

        # Delete schedule
        db.session.delete(schedule)
        db.session.commit()

    await update.message.reply_text(f"✅ Занятие с ID {lesson_id} успешно удалено.")


async def unknown_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle unknown commands."""
    await update.message.reply_text(
        "❓ Неизвестная команда.\n"
        "Используйте /help для просмотра доступных команд."
    )


async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle errors."""
    logger.error(f"Update {update} caused error {context.error}")

    if update and update.effective_message:
        await update.effective_message.reply_text(
            "❌ Произошла ошибка при обработке команды.\n"
            "Пожалуйста, попробуйте позже или обратитесь к администратору."
        )


# ============================================================================
# Bot Setup and Start
# ============================================================================

def _setup_handlers(application: Application):
    """Set up command handlers for the bot."""
    # Add command handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("today", today_command))
    application.add_handler(CommandHandler("schedule", schedule_command))
    application.add_handler(CommandHandler("groups", groups_command))
    application.add_handler(CommandHandler("students", students_command))
    application.add_handler(CommandHandler("addgroup", addgroup_command))
    application.add_handler(CommandHandler("addstudent", addstudent_command))
    application.add_handler(CommandHandler("addlesson", addlesson_command))
    application.add_handler(CommandHandler("deletelesson", deletelesson_command))

    # Add unknown command handler
    application.add_handler(MessageHandler(filters.COMMAND, unknown_command))

    # Add error handler
    application.add_error_handler(error_handler)


def setup_bot(token: str) -> Application:
    """Set up the bot with all handlers."""
    application = Application.builder().token(token).build()
    _setup_handlers(application)
    return application


def run_bot_in_thread(token: str):
    """Run the bot in a separate thread - NOT RECOMMENDED for PythonAnywhere.
    Use webhook mode instead by calling init_bot() and process_update()."""
    import threading
    import asyncio

    async def start_bot_async():
        application = setup_bot(token)
        await application.initialize()
        await application.start()
        await application.updater.start_polling()

        # Keep the bot running
        while True:
            await asyncio.sleep(1)

    def run_async():
        asyncio.run(start_bot_async())

    bot_thread = threading.Thread(target=run_async, daemon=True)
    bot_thread.start()
    logger.info("Telegram bot started in separate thread (polling mode)")
    return bot_thread


async def process_update(update_data: dict):
    """Process a single update from Telegram webhook.
    
    This is the main entry point for webhook-based bot operation on PythonAnywhere.
    Call this function from your Flask webhook endpoint.
    
    Args:
        update_data: The JSON data received from Telegram webhook
        
    Returns:
        bool: True if update was processed successfully
    """
    global _bot_application
    
    if not _bot_application:
        logger.error("Bot application not initialized. Call init_bot() first.")
        return False
    
    try:
        # Initialize if not already done
        if not _bot_application.running:
            await _bot_application.initialize()
            await _bot_application.start()
        
        # Process the update
        update = Update.de_json(update_data, _bot_application.bot)
        await _bot_application.process_update(update)
        return True
    except Exception as e:
        logger.error(f"Error processing update: {e}")
        return False


def get_webhook_url() -> Optional[str]:
    """Get the webhook URL from environment variable."""
    return os.environ.get('TELEGRAM_WEBHOOK_URL')


async def set_webhook(url: str = None) -> bool:
    """Set the webhook URL for the bot.
    
    Args:
        url: The webhook URL. If None, uses TELEGRAM_WEBHOOK_URL env var.
        
    Returns:
        bool: True if webhook was set successfully
    """
    global _bot_application
    
    if not _bot_application:
        logger.error("Bot application not initialized")
        return False
    
    webhook_url = url or get_webhook_url()
    if not webhook_url:
        logger.error("No webhook URL provided")
        return False
    
    try:
        await _bot_application.bot.set_webhook(url=webhook_url)
        logger.info(f"Webhook set to: {webhook_url}")
        return True
    except Exception as e:
        logger.error(f"Failed to set webhook: {e}")
        return False


async def delete_webhook() -> bool:
    """Delete the bot webhook."""
    global _bot_application
    
    if not _bot_application:
        return False
    
    try:
        await _bot_application.bot.delete_webhook()
        logger.info("Webhook deleted")
        return True
    except Exception as e:
        logger.error(f"Failed to delete webhook: {e}")
        return False


def start_bot(db, flask_app):
    """
    Initialize the Telegram bot for webhook mode.
    Call this function from app.py to initialize the bot.
    
    For PythonAnywhere, use webhook mode instead of polling.
    The bot will process updates via the /webhook endpoint.
    
    Returns:
        bool: True if bot was initialized successfully
    """
    token = os.environ.get('TELEGRAM_BOT_TOKEN')

    if not token:
        logger.warning("TELEGRAM_BOT_TOKEN not set. Bot will not start.")
        return False

    # Initialize global references and bot application
    init_bot(db, flask_app)

    # Create database tables for TeacherTelegram model
    with flask_app.app_context():
        TeacherTelegram = get_teacher_telegram_model()
        db.create_all()
        logger.info("TeacherTelegram table created/verified")
    
    logger.info("Telegram bot initialized for webhook mode")
    logger.info("Make sure to set TELEGRAM_WEBHOOK_URL and call set_webhook()")
    return True


def start_bot_polling(db, flask_app):
    """
    Start the Telegram bot in polling mode (for local development only).
    NOT RECOMMENDED for PythonAnywhere - use webhook mode instead.
    """
    token = os.environ.get('TELEGRAM_BOT_TOKEN')

    if not token:
        logger.warning("TELEGRAM_BOT_TOKEN not set. Bot will not start.")
        return None

    # Initialize global references
    init_bot(db, flask_app)

    # Create database tables for TeacherTelegram model
    with flask_app.app_context():
        TeacherTelegram = get_teacher_telegram_model()
        db.create_all()
        logger.info("TeacherTelegram table created/verified")

    # Start bot in separate thread
    return run_bot_in_thread(token)


# ============================================================================
# Web Interface Functions
# ============================================================================

def link_telegram_to_teacher(teacher_id: int, telegram_chat_id: int,
                             telegram_username: str = None,
                             first_name: str = None,
                             last_name: str = None) -> bool:
    """
    Link a Telegram account to a teacher profile.
    Call this from the web interface when teacher adds their Telegram ID.
    """
    if not _app:
        raise RuntimeError("Bot not initialized. Call init_bot() first.")

    TeacherTelegram = get_teacher_telegram_model()

    with _app.app_context():
        # Check if already linked
        existing = TeacherTelegram.query.filter_by(telegram_chat_id=telegram_chat_id).first()
        if existing:
            if existing.teacher_id != teacher_id:
                return False  # Already linked to another teacher
            return True  # Already linked to this teacher

        # Create new link
        link = TeacherTelegram(
            teacher_id=teacher_id,
            telegram_chat_id=telegram_chat_id,
            telegram_username=telegram_username,
            first_name=first_name,
            last_name=last_name,
            is_active=True
        )

        _db.session.add(link)
        _db.session.commit()

    return True


def unlink_telegram_from_teacher(teacher_id: int) -> bool:
    """
    Unlink Telegram account from a teacher profile.
    """
    if not _app:
        raise RuntimeError("Bot not initialized. Call init_bot() first.")

    TeacherTelegram = get_teacher_telegram_model()

    with _app.app_context():
        link = TeacherTelegram.query.filter_by(teacher_id=teacher_id).first()
        if link:
            link.is_active = False
            _db.session.commit()
            return True
    return False


def get_teacher_telegram_info(teacher_id: int) -> Optional[dict]:
    """
    Get Telegram info for a teacher.
    Returns dict with telegram info or None.
    """
    if not _app:
        return None

    TeacherTelegram = get_teacher_telegram_model()

    with _app.app_context():
        link = TeacherTelegram.query.filter_by(
            teacher_id=teacher_id,
            is_active=True
        ).first()

        if link:
            return {
                'telegram_chat_id': link.telegram_chat_id,
                'telegram_username': link.telegram_username,
                'first_name': link.first_name,
                'last_name': link.last_name,
                'created_at': link.created_at.isoformat() if link.created_at else None
            }
    return None


def send_notification_to_teacher(teacher_id: int, message: str) -> bool:
    """
    Send notification to teacher via Telegram.
    Returns True if message was sent successfully.
    """
    import asyncio

    if not _app:
        return False

    TeacherTelegram = get_teacher_telegram_model()
    token = os.environ.get('TELEGRAM_BOT_TOKEN')

    if not token:
        return False

    with _app.app_context():
        link = TeacherTelegram.query.filter_by(
            teacher_id=teacher_id,
            is_active=True
        ).first()

        if not link:
            return False

        chat_id = link.telegram_chat_id

    async def send_message():
        from telegram import Bot
        bot = Bot(token=token)
        try:
            await bot.send_message(chat_id=chat_id, text=message)
            return True
        except Exception as e:
            logger.error(f"Failed to send message: {e}")
            return False

    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # If loop is already running, create a new task
            future = asyncio.run_coroutine_threadsafe(send_message(), loop)
            return future.result(timeout=10)
        else:
            return loop.run_until_complete(send_message())
    except Exception as e:
        logger.error(f"Error sending notification: {e}")
        return False


if __name__ == '__main__':
    # For testing purposes
    print("This module should be imported and started via start_bot()")
