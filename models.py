from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime
import bcrypt

db = SQLAlchemy()


class Teacher(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(128))
    email = db.Column(db.String(120), unique=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def set_password(self, password):
        self.password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

    def check_password(self, password):
        return bcrypt.checkpw(password.encode('utf-8'), self.password_hash.encode('utf-8'))


class Group(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)
    course = db.Column(db.String(100), nullable=False)  # Курс
    education_form = db.Column(db.String(50), nullable=False)  # Форма обучения (очная, заочная, дистанционная)
    teacher_id = db.Column(db.Integer, db.ForeignKey('teacher.id'))
    color = db.Column(db.String(7))
    students = db.relationship('Student', backref='group', lazy=True)


class Student(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120))
    group_id = db.Column(db.Integer, db.ForeignKey('group.id'))
    attendance = db.relationship('Attendance', backref='student', lazy=True)
    assignments = db.relationship('Assignment', backref='student', lazy=True)


class Lesson(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.DateTime, nullable=False)
    group_id = db.Column(db.Integer, db.ForeignKey('group.id'))
    topic = db.Column(db.String(200), nullable=False)
    notes = db.Column(db.Text)
    classroom = db.Column(db.String(50))  # Аудитория
    teacher_id = db.Column(db.Integer, db.ForeignKey('teacher.id'))
    subject = db.Column(db.String(200))  # Название дисциплины


class Attendance(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('student.id'))
    lesson_id = db.Column(db.Integer, db.ForeignKey('lesson.id'))
    present = db.Column(db.Boolean, default=False)
    attendance_mark = db.Column(db.String(10))  # Оценка или отметка (5, 4, 3, 2, Н, П, и т.д.)
    date = db.Column(db.DateTime, default=datetime.utcnow)


class ControlPoint(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    group_id = db.Column(db.Integer, db.ForeignKey('group.id'), nullable=False)
    teacher_id = db.Column(db.Integer, db.ForeignKey('teacher.id'), nullable=False)
    date = db.Column(db.Date, nullable=False)
    title = db.Column(db.String(200), default='КТ')
    max_points = db.Column(db.Integer, default=100)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    subject = db.Column(db.String(200))  # Название дисциплины


class ControlPointScore(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    control_point_id = db.Column(db.Integer, db.ForeignKey('control_point.id'), nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey('student.id'), nullable=False)
    points = db.Column(db.Integer)  # Баллы от 0 до 100, null если не оценено
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Assignment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey('student.id'))
    file_path = db.Column(db.String(500))
    cloud_url = db.Column(db.String(500))
    score = db.Column(db.Float)
    ai_analysis = db.Column(db.Text)
    submitted_at = db.Column(db.DateTime, default=datetime.utcnow)
    checked_at = db.Column(db.DateTime)
    teacher_id = db.Column(db.Integer, db.ForeignKey('teacher.id'))
    due_date = db.Column(db.Date)  # Срок выполнения задания
    subject = db.Column(db.String(200))  # Название дисциплины


class Schedule(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200))
    start_time = db.Column(db.DateTime, nullable=False)
    end_time = db.Column(db.DateTime, nullable=False)
    group_id = db.Column(db.Integer, db.ForeignKey('group.id'))
    color = db.Column(db.String(7))
    classroom = db.Column(db.String(50))  # Аудитория
    teacher_id = db.Column(db.Integer, db.ForeignKey('teacher.id'))
    # Поля для мероприятий
    is_event = db.Column(db.Boolean, default=False)  # Является ли мероприятием
    description = db.Column(db.Text)  # Описание мероприятия
    event_type = db.Column(db.String(50))  # Тип мероприятия


class TaskList(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    position = db.Column(db.Integer, default=0)
    teacher_id = db.Column(db.Integer, db.ForeignKey('teacher.id'))
    tasks = db.relationship('Task', backref='list', lazy=True, cascade='all, delete-orphan')


class Task(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    status = db.Column(db.String(20), default='new')  # new, in_progress, completed
    priority = db.Column(db.String(10), default='low')  # low, medium, high
    due_date = db.Column(db.DateTime)
    position = db.Column(db.Integer, default=0)
    list_id = db.Column(db.Integer, db.ForeignKey('task_list.id'))
    teacher_id = db.Column(db.Integer, db.ForeignKey('teacher.id'))


class CloudSettings(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    teacher_id = db.Column(db.Integer, db.ForeignKey('teacher.id'), nullable=False)
    cloud_type = db.Column(db.String(50), default='mail')  # mail, yandex, google
    api_url = db.Column(db.String(500))
    access_token = db.Column(db.Text)
    refresh_token = db.Column(db.Text)
    client_id = db.Column(db.String(200))
    client_secret = db.Column(db.String(200))
    is_active = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class EmailSettings(db.Model):
    """Настройки подключения к почтовому ящику преподавателя"""
    id = db.Column(db.Integer, primary_key=True)
    teacher_id = db.Column(db.Integer, db.ForeignKey('teacher.id'), nullable=False)
    email = db.Column(db.String(200), nullable=False)
    username = db.Column(db.String(200), nullable=False)
    password = db.Column(db.Text, nullable=False)  # Хранится в открытом виде для подключения к IMAP/SMTP
    imap_host = db.Column(db.String(200), nullable=False)
    imap_port = db.Column(db.Integer, default=993)
    imap_ssl = db.Column(db.Boolean, default=True)
    smtp_host = db.Column(db.String(200), nullable=False)
    smtp_port = db.Column(db.Integer, default=465)
    smtp_ssl = db.Column(db.Boolean, default=True)
    is_active = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class CloudCategory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    teacher_id = db.Column(db.Integer, db.ForeignKey('teacher.id'), nullable=False)
    name = db.Column(db.String(200), nullable=False)
    cloud_path = db.Column(db.String(500), nullable=False)
    description = db.Column(db.Text)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Note(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    teacher_id = db.Column(db.Integer, db.ForeignKey('teacher.id'), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)
    color = db.Column(db.String(7), default='#ffffff')  # Hex цвет
    is_pinned = db.Column(db.Boolean, default=False)
    is_archived = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'content': self.content,
            'color': self.color,
            'is_pinned': self.is_pinned,
            'is_archived': self.is_archived,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }


class MessengerSettings(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    teacher_id = db.Column(db.Integer, db.ForeignKey('teacher.id'), nullable=False)
    messenger_type = db.Column(db.String(50), nullable=False)  # whatsapp, telegram, max
    api_token = db.Column(db.Text)  # Токен API или токен бота
    api_id = db.Column(db.String(200))  # API ID (для Telegram)
    api_hash = db.Column(db.String(200))  # API Hash (для Telegram)
    phone_number = db.Column(db.String(50))  # Номер телефона (для WhatsApp)
    instance_id = db.Column(db.String(200))  # Instance ID (для WhatsApp Business API)
    webhook_url = db.Column(db.String(500))  # URL для webhook
    bot_username = db.Column(db.String(200))  # Username бота (для Telegram)
    is_active = db.Column(db.Boolean, default=False)
    last_sync = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'messenger_type': self.messenger_type,
            'api_token': self.api_token,
            'api_id': self.api_id,
            'api_hash': self.api_hash,
            'phone_number': self.phone_number,
            'instance_id': self.instance_id,
            'webhook_url': self.webhook_url,
            'bot_username': self.bot_username,
            'is_active': self.is_active,
            'last_sync': self.last_sync.isoformat() if self.last_sync else None
        }


class ConferenceSettings(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    teacher_id = db.Column(db.Integer, db.ForeignKey('teacher.id'), nullable=False)
    service_type = db.Column(db.String(50), nullable=False)  # kontur, yandex, zoom
    organization_id = db.Column(db.String(200))  # ID организации
    api_key = db.Column(db.Text)  # API ключ или токен
    api_secret = db.Column(db.Text)  # API Secret (для Zoom)
    account_id = db.Column(db.String(200))  # Account ID (для Zoom)
    client_id = db.Column(db.String(200))  # Client ID (для OAuth)
    client_secret = db.Column(db.String(200))  # Client Secret (для OAuth)
    access_token = db.Column(db.Text)  # Access Token (для OAuth)
    refresh_token = db.Column(db.Text)  # Refresh Token (для OAuth)
    is_active = db.Column(db.Boolean, default=False)
    last_sync = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'service_type': self.service_type,
            'organization_id': self.organization_id,
            'api_key': self.api_key,
            'api_secret': self.api_secret,
            'account_id': self.account_id,
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'is_active': self.is_active,
            'last_sync': self.last_sync.isoformat() if self.last_sync else None
        }


class Conference(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    teacher_id = db.Column(db.Integer, db.ForeignKey('teacher.id'), nullable=False)
    service_type = db.Column(db.String(50), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    scheduled_time = db.Column(db.DateTime)
    conference_url = db.Column(db.String(500))
    conference_id = db.Column(db.String(200))  # ID конференции в сервисе
    participants_count = db.Column(db.Integer, default=0)
    recording_url = db.Column(db.String(500))
    status = db.Column(db.String(50), default='scheduled')  # scheduled, active, completed, cancelled
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'service_type': self.service_type,
            'title': self.title,
            'scheduled_time': self.scheduled_time.isoformat() if self.scheduled_time else None,
            'conference_url': self.conference_url,
            'conference_id': self.conference_id,
            'participants_count': self.participants_count,
            'recording_url': self.recording_url,
            'status': self.status,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }