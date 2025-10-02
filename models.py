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


class Schedule(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200))
    start_time = db.Column(db.DateTime, nullable=False)
    end_time = db.Column(db.DateTime, nullable=False)
    group_id = db.Column(db.Integer, db.ForeignKey('group.id'))
    color = db.Column(db.String(7))
    classroom = db.Column(db.String(50))  # Аудитория
    teacher_id = db.Column(db.Integer, db.ForeignKey('teacher.id'))


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


class CloudCategory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    teacher_id = db.Column(db.Integer, db.ForeignKey('teacher.id'), nullable=False)
    name = db.Column(db.String(200), nullable=False)
    cloud_path = db.Column(db.String(500), nullable=False)
    description = db.Column(db.Text)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)