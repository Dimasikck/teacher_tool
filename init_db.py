# init_db.py
from app import app, db
from models import Teacher, Group, Student
from datetime import datetime


def init_database():
    with app.app_context():
        db.create_all()

        # Создание админа
        if not Teacher.query.filter_by(username='admin').first():
            admin = Teacher(username='d.subbotin', email='dmitriy.aleksandrovich.subbotin@mail.ru')
            admin.set_password('Dimasik0505')
            db.session.add(admin)

        # Создание тестовых данных
        if not Group.query.first():
            teacher = Teacher.query.first()

            group1 = Group(name='Группа А-101', teacher_id=teacher.id)
            group2 = Group(name='Группа Б-202', teacher_id=teacher.id)
            db.session.add(group1)
            db.session.add(group2)
            db.session.commit()

            students_a = [
                Student(name='Иванов Иван', email='ivanov@mail.ru', group_id=group1.id),
                Student(name='Петров Петр', email='petrov@mail.ru', group_id=group1.id),
                Student(name='Сидоров Сидор', email='sidorov@mail.ru', group_id=group1.id),
            ]

            students_b = [
                Student(name='Смирнова Анна', email='smirnova@mail.ru', group_id=group2.id),
                Student(name='Козлов Дмитрий', email='kozlov@mail.ru', group_id=group2.id),
                Student(name='Новикова Елена', email='novikova@mail.ru', group_id=group2.id),
            ]

            for s in students_a + students_b:
                db.session.add(s)

            db.session.commit()
            print("База данных инициализирована с тестовыми данными")

        print("База данных готова к работе")
        print("Логин: d.subbotin")
        print("Пароль: Dimasik0505")


if __name__ == '__main__':
    init_database()