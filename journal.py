from flask import Blueprint, render_template, request, jsonify, flash
from flask_login import login_required, current_user
from models import db, Student, Group, Attendance, Lesson
from datetime import datetime
import pandas as pd

journal_bp = Blueprint('journal', __name__)


@journal_bp.route('/journal')
@login_required
def journal():
    groups = Group.query.filter_by(teacher_id=current_user.id).all()
    return render_template('journal.html', groups=groups)


@journal_bp.route('/api/attendance', methods=['POST'])
@login_required
def mark_attendance():
    data = request.json
    lesson = Lesson.query.get_or_404(data['lesson_id'])

    for student_id, present in data['attendance'].items():
        attendance = Attendance.query.filter_by(
            student_id=student_id,
            lesson_id=lesson.id
        ).first()

        if attendance:
            attendance.present = present
        else:
            attendance = Attendance(
                student_id=student_id,
                lesson_id=lesson.id,
                present=present
            )
            db.session.add(attendance)

    db.session.commit()
    return jsonify({'status': 'success'})


@journal_bp.route('/api/lessons', methods=['GET', 'POST'])
@login_required
def lessons():
    if request.method == 'POST':
        data = request.json
        lesson = Lesson(
            date=datetime.fromisoformat(data['date']),
            group_id=data['group_id'],
            topic=data['topic'],
            notes=data.get('notes', ''),
            teacher_id=current_user.id
        )
        db.session.add(lesson)
        db.session.commit()
        return jsonify({'id': lesson.id, 'status': 'success'})

    group_id = request.args.get('group_id')
    lessons = Lesson.query.filter_by(teacher_id=current_user.id)
    if group_id:
        lessons = lessons.filter_by(group_id=group_id)

    return jsonify([{
        'id': l.id,
        'date': l.date.isoformat(),
        'topic': l.topic,
        'notes': l.notes,
        'group_id': l.group_id
    } for l in lessons.all()])


@journal_bp.route('/api/journal/group')
@login_required
def group_journal():
    """Возвращает структуру журнала для группы: список студентов, список занятий и отметки."""
    group_id = request.args.get('group_id', type=int)
    month_str = request.args.get('month')  # Ожидаем формат YYYY-MM
    if not group_id:
        return jsonify({'error': 'group_id is required'}), 400

    # Проверяем, что группа принадлежит преподавателю
    group = Group.query.filter_by(id=group_id, teacher_id=current_user.id).first_or_404()

    students = Student.query.filter_by(group_id=group_id).order_by(Student.name.asc()).all()

    lessons_query = Lesson.query.filter_by(group_id=group_id, teacher_id=current_user.id)

    # Фильтрация по месяцу, если указано
    if month_str:
        try:
            from datetime import datetime, timedelta
            start = datetime.strptime(month_str + '-01', '%Y-%m-%d')
            # вычисляем следующий месяц
            if start.month == 12:
                end = start.replace(year=start.year + 1, month=1, day=1)
            else:
                end = start.replace(month=start.month + 1, day=1)
            lessons_query = lessons_query.filter(Lesson.date >= start, Lesson.date < end)
        except Exception:
            pass

    lessons = lessons_query.order_by(Lesson.date.asc()).all()

    # Подсчеты занятий
    month_count = len(lessons)
    total_count = Lesson.query.filter_by(group_id=group_id, teacher_id=current_user.id).count()

    # Загружаем все Attendance для данной группы разом
    attendance_rows = db.session.query(Attendance).join(Student, Attendance.student_id == Student.id).join(Lesson, Attendance.lesson_id == Lesson.id).filter(
        Student.group_id == group_id,
        Lesson.group_id == group_id
    ).all()

    marks = {}
    for a in attendance_rows:
        key = f"{a.student_id}:{a.lesson_id}"
        marks[key] = {
            'present': bool(a.present),
            'mark': a.attendance_mark or ''
        }

    # Определяем читаемое название дисциплины: если course пустой/числовой, берём самое частое Lesson.topic
    subject = (group.course or '').strip()
    def _is_numeric(value: str) -> bool:
        try:
            float(value)
            return True
        except Exception:
            return False

    if not subject or _is_numeric(subject):
        topics = [l.topic.strip() for l in lessons if (l.topic or '').strip()]
        if topics:
            from collections import Counter
            subject = Counter(topics).most_common(1)[0][0]

    return jsonify({
        'group': {
            'id': group.id,
            'name': group.name,
            'course': group.course,
            'subject': subject or group.course,
            'education_form': group.education_form
        },
        'students': [{'id': s.id, 'name': s.name} for s in students],
        'lessons': [{'id': l.id, 'date': l.date.isoformat(), 'topic': l.topic, 'notes': l.notes} for l in lessons],
        'marks': marks,
        'stats': {
            'month_lessons': month_count,
            'total_lessons': total_count
        }
    })


@journal_bp.route('/api/journal/mark', methods=['POST'])
@login_required
def save_mark():
    """Сохраняет отметку/оценку для студента на занятии. Значения: 'н' (отсутствовал) или оценка."""
    data = request.get_json(force=True)
    student_id = data.get('student_id')
    lesson_id = data.get('lesson_id')
    value = (data.get('value') or '').strip()

    if not student_id or not lesson_id:
        return jsonify({'error': 'student_id and lesson_id are required'}), 400

    # Проверяем принадлежность к преподавателю
    lesson = Lesson.query.filter_by(id=lesson_id, teacher_id=current_user.id).first_or_404()
    student = Student.query.filter_by(id=student_id, group_id=lesson.group_id).first_or_404()

    is_absent = value.lower() in ('н', 'n', 'неявка', 'отс', 'н.')

    attendance = Attendance.query.filter_by(student_id=student.id, lesson_id=lesson.id).first()
    if not attendance:
        attendance = Attendance(student_id=student.id, lesson_id=lesson.id)
        db.session.add(attendance)

    if is_absent:
        attendance.present = False
        attendance.attendance_mark = 'Н'
    else:
        attendance.present = True
        attendance.attendance_mark = value if value != '' else None

    db.session.commit()

    return jsonify({'status': 'success', 'present': attendance.present, 'mark': attendance.attendance_mark or ''})


@journal_bp.route('/api/lesson/<int:lesson_id>')
@login_required
def lesson_detail(lesson_id):
    """Детали занятия по id"""
    lesson = Lesson.query.filter_by(id=lesson_id, teacher_id=current_user.id).first_or_404()
    return jsonify({
        'id': lesson.id,
        'date': lesson.date.isoformat(),
        'topic': lesson.topic,
        'notes': lesson.notes or ''
    })


@journal_bp.route('/api/students')
@login_required
def api_students():
    group_id = request.args.get('group_id')
    query = Student.query
    if group_id:
        query = query.filter_by(group_id=group_id)
    students = query.all()
    return jsonify([{'id': s.id, 'name': s.name, 'email': s.email, 'group_id': s.group_id} for s in students])


@journal_bp.route('/api/attendance/stats')
@login_required
def attendance_stats():
    group_id = request.args.get('group_id')
    date_from = request.args.get('date_from')
    date_to = request.args.get('date_to')

    query = db.session.query(
        Student.name,
        db.func.count(Attendance.id).label('total'),
        db.func.sum(db.case([(Attendance.present == True, 1)], else_=0)).label('present')
    ).join(Attendance).join(Lesson)

    if group_id:
        query = query.filter(Student.group_id == group_id)
    if date_from:
        query = query.filter(Lesson.date >= datetime.fromisoformat(date_from))
    if date_to:
        query = query.filter(Lesson.date <= datetime.fromisoformat(date_to))

    stats = query.group_by(Student.id).all()

    return jsonify([{
        'student': s.name,
        'total': s.total,
        'present': s.present,
        'percentage': round((s.present / s.total * 100) if s.total > 0 else 0, 2)
    } for s in stats])


@journal_bp.route('/export/attendance/<int:group_id>')
@login_required
def export_attendance(group_id):
    group = Group.query.get_or_404(group_id)
    students = Student.query.filter_by(group_id=group_id).all()
    lessons = Lesson.query.filter_by(group_id=group_id).all()

    data = []
    for student in students:
        row = {'Студент': student.name}
        for lesson in lessons:
            attendance = Attendance.query.filter_by(
                student_id=student.id,
                lesson_id=lesson.id
            ).first()
            row[lesson.date.strftime('%d.%m.%Y')] = '+' if attendance and attendance.present else '-'
        data.append(row)

    df = pd.DataFrame(data)
    filename = f'attendance_{group.name}_{datetime.now().strftime("%Y%m%d")}.csv'
    df.to_csv(f'static/exports/{filename}', index=False)

    return jsonify({'file': f'/static/exports/{filename}'})