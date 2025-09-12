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
    
    # Поддержка как старого формата (массовое обновление), так и нового (одиночное)
    if 'lesson_id' in data and 'attendance' in data:
        # Старый формат - массовое обновление
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
    else:
        # Новый формат - одиночное обновление
        student_id = data.get('student_id')
        lesson_id = data.get('lesson_id')
        attendance_value = data.get('attendance', '')
        
        if not student_id or not lesson_id:
            return jsonify({'error': 'Missing required fields'}), 400
            
        lesson = Lesson.query.get_or_404(lesson_id)
        
        # Проверяем, что урок принадлежит текущему преподавателю
        if lesson.teacher_id != current_user.id:
            return jsonify({'error': 'Unauthorized'}), 403
        
        attendance = Attendance.query.filter_by(
            student_id=student_id,
            lesson_id=lesson_id
        ).first()

        if attendance:
            # Обновляем существующую запись
            if attendance_value.upper() in ['Н', 'НЕ', 'ABSENT', '']:
                attendance.present = False
            elif attendance_value.upper() in ['П', 'ПРИСУТСТВИЕ', 'PRESENT', '1', '+']:
                attendance.present = True
            else:
                # Сохраняем оценку или другую информацию
                attendance.attendance_mark = attendance_value
        else:
            # Создаем новую запись
            attendance = Attendance(
                student_id=student_id,
                lesson_id=lesson_id,
                present=attendance_value.upper() not in ['Н', 'НЕ', 'ABSENT', ''],
                attendance_mark=attendance_value if attendance_value.upper() not in ['П', 'ПРИСУТСТВИЕ', 'PRESENT', '1', '+'] else None
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

    try:
        group_id = request.args.get('group_id')
        print(f"API Lessons called with group_id: {group_id}")
        
        lessons = Lesson.query.filter_by(teacher_id=current_user.id)
        if group_id:
            # Проверяем, что группа принадлежит текущему преподавателю
            group = Group.query.filter_by(id=group_id, teacher_id=current_user.id).first()
            if not group:
                print(f"Group {group_id} not found or not owned by teacher {current_user.id}")
                return jsonify({'error': 'Group not found or unauthorized'}), 404
            lessons = lessons.filter_by(group_id=group_id)

        # Сортируем занятия по дате (новые сверху)
        lessons = lessons.order_by(Lesson.date.desc())
        
        result = lessons.all()
        print(f"Found {len(result)} lessons for group {group_id}")

        # Без прямой связи l.group (в модели Lesson нет relationship)
        group_map = {g.id: g.name for g in Group.query.all()}
        return jsonify([{
            'id': l.id,
            'date': l.date.isoformat(),
            'topic': l.topic,
            'notes': l.notes,
            'group_id': l.group_id,
            'group_name': group_map.get(l.group_id, 'Неизвестная группа')
        } for l in result])
    except Exception as e:
        print(f"Error in lessons API: {e}")
        return jsonify({'error': str(e)}), 500


@journal_bp.route('/api/lessons/<int:lesson_id>', methods=['PUT'])
@login_required
def update_lesson(lesson_id):
    lesson = Lesson.query.get_or_404(lesson_id)
    
    # Проверяем, что урок принадлежит текущему преподавателю
    if lesson.teacher_id != current_user.id:
        return jsonify({'error': 'Unauthorized'}), 403
    
    data = request.json
    
    if 'topic' in data:
        lesson.topic = data['topic']
    if 'notes' in data:
        lesson.notes = data['notes']
    if 'date' in data:
        lesson.date = datetime.fromisoformat(data['date'])
    
    db.session.commit()
    return jsonify({'status': 'success'})


@journal_bp.route('/api/attendance/<int:student_id>/<int:lesson_id>')
@login_required
def get_attendance(student_id, lesson_id):
    attendance = Attendance.query.filter_by(
        student_id=student_id,
        lesson_id=lesson_id
    ).first()
    
    if attendance:
        # Возвращаем оценку или отметку о присутствии
        if attendance.attendance_mark:
            return jsonify({'attendance': attendance.attendance_mark})
        elif attendance.present:
            return jsonify({'attendance': 'П'})
        else:
            return jsonify({'attendance': 'Н'})
    else:
        return jsonify({'attendance': ''})


@journal_bp.route('/api/students')
@login_required
def api_students():
    try:
        group_id = request.args.get('group_id')
        print(f"API Students called with group_id: {group_id}")
        
        if not group_id:
            return jsonify({'error': 'group_id is required'}), 400
            
        # Проверяем, что группа принадлежит текущему преподавателю
        group = Group.query.filter_by(id=group_id, teacher_id=current_user.id).first()
        if not group:
            print(f"Group {group_id} not found or not owned by teacher {current_user.id}")
            return jsonify({'error': 'Group not found or unauthorized'}), 404
        
        students = Student.query.filter_by(group_id=group_id).all()
        print(f"Found {len(students)} students for group {group_id}")
        
        result = [{'id': s.id, 'name': s.name, 'email': s.email, 'group_id': s.group_id} for s in students]
        return jsonify(result)
    except Exception as e:
        print(f"Error in api_students: {e}")
        return jsonify({'error': str(e)}), 500


@journal_bp.route('/api/lessons/all')
@login_required
def all_lessons():
    """Получить все занятия преподавателя с информацией о группах"""
    lessons = Lesson.query.filter_by(teacher_id=current_user.id)\
                         .join(Group)\
                         .order_by(Lesson.date.desc()).all()
    
    return jsonify([{
        'id': l.id,
        'date': l.date.strftime('%d.%m.%Y %H:%M'),
        'topic': l.topic,
        'notes': l.notes,
        'group_id': l.group_id,
        'group_name': l.group.name,
        'group_color': l.group.color or '#3788d8'
    } for l in lessons])


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