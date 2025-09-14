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