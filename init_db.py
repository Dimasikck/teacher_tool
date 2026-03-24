# init_db.py
import os
import secrets
from datetime import datetime

from app import app, db
from models import Teacher, Group, Student


def _create_admin_if_missing() -> tuple[str, str | None]:
    """Create admin user if missing.

    Returns:
        (username, generated_password_or_none)
    """
    username = os.environ.get('INIT_ADMIN_USERNAME', 'admin')
    email = os.environ.get('INIT_ADMIN_EMAIL', 'admin@example.com')

    if Teacher.query.filter_by(username=username).first():
        return username, None

    password = os.environ.get('INIT_ADMIN_PASSWORD')
    generated_password = None
    if not password:
        # Generate one-time password when env value is not provided.
        password = secrets.token_urlsafe(16)
        generated_password = password

    admin = Teacher(username=username, email=email)
    admin.set_password(password)
    db.session.add(admin)
    return username, generated_password


def init_database() -> None:
    with app.app_context():
        db.create_all()

        admin_username, generated_password = _create_admin_if_missing()

        # Seed demo data only for a new/empty database.
        if not Group.query.first():
            teacher = Teacher.query.first()
            if teacher is not None:
                group1 = Group(name='Group A-101', teacher_id=teacher.id)
                group2 = Group(name='Group B-202', teacher_id=teacher.id)
                db.session.add(group1)
                db.session.add(group2)
                db.session.commit()

                students_a = [
                    Student(name='Ivanov Ivan', email='ivanov@mail.ru', group_id=group1.id),
                    Student(name='Petrov Petr', email='petrov@mail.ru', group_id=group1.id),
                    Student(name='Sidorov Sidor', email='sidorov@mail.ru', group_id=group1.id),
                ]

                students_b = [
                    Student(name='Smirnova Anna', email='smirnova@mail.ru', group_id=group2.id),
                    Student(name='Kozlov Dmitriy', email='kozlov@mail.ru', group_id=group2.id),
                    Student(name='Novikova Elena', email='novikova@mail.ru', group_id=group2.id),
                ]

                for student in students_a + students_b:
                    db.session.add(student)

        db.session.commit()

        print('Database initialized.')
        print(f'Admin username: {admin_username}')
        if generated_password:
            print('Generated admin password (save it now):')
            print(generated_password)
        else:
            print('Admin password was taken from INIT_ADMIN_PASSWORD or existing account remains unchanged.')


if __name__ == '__main__':
    init_database()
