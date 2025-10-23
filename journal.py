from flask import Blueprint, render_template, request, jsonify, flash
from flask_login import login_required, current_user
from models import db, Student, Group, Attendance, Lesson, ControlPoint, ControlPointScore
from datetime import datetime
import pandas as pd
import re

journal_bp = Blueprint('journal', __name__)
def normalize_subject_name(name: str) -> str:
    """Нормализует название дисциплины, убирая префиксы Лек./лаб./Пр. и лишние разделители."""
    if not name:
        return ''
    cleaned = name.strip()
    # Убираем распространенные префиксы форм занятий, но не обрезаем реальные названия типа "Профессиональные..."
    # Правила:
    # - Полные слова в начале: лекция, лабораторная, практика, семинар, консультация
    # - Аббревиатуры в начале: лек., лек.., лаб., лаб.., пр., пр.. (для "Пр" обязательна хотя бы одна точка)
    prefix_pattern = (
        r'^(?:'
        r'(?:лекция|лабораторная|практика|семинар|консультация)'
        r'|(?:лек\.{1,2})'
        r'|(?:лаб\.{1,2})'
        r'|(?:пр\.{1,2})'
        r')\s*[-:.,]?\s*'
    )
    cleaned = re.sub(prefix_pattern, '', cleaned, flags=re.IGNORECASE)
    # Сжимаем пробелы
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    return cleaned


@journal_bp.route('/journal')
@login_required
def journal():
    groups = Group.query.filter_by(teacher_id=current_user.id).order_by(Group.name.asc()).all()
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
        # Привязываем дисциплину, если передана, иначе используем course группы
        subject = normalize_subject_name(data.get('subject') or '')
        if not subject:
            try:
                group = Group.query.filter_by(id=data['group_id'], teacher_id=current_user.id).first()
                subject = normalize_subject_name((group.course or '') if group else '')
            except Exception:
                subject = ''
        if subject:
            lesson.subject = subject
        db.session.add(lesson)
        db.session.commit()
        return jsonify({'id': lesson.id, 'status': 'success'})

    group_id = request.args.get('group_id')
    subject = request.args.get('subject', type=str)
    lessons = Lesson.query.filter_by(teacher_id=current_user.id)
    if group_id:
        lessons = lessons.filter_by(group_id=group_id)
    if subject:
        lessons = lessons.filter((Lesson.subject == subject) | ((Lesson.subject == None) & (Group.course == subject)))

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
    subject = request.args.get('subject', type=str)
    if not group_id:
        return jsonify({'error': 'group_id is required'}), 400

    # Проверяем, что группа принадлежит преподавателю
    group = Group.query.filter_by(id=group_id, teacher_id=current_user.id).first_or_404()

    students = Student.query.filter_by(group_id=group_id).order_by(Student.name.asc()).all()

    lessons_query = Lesson.query.filter_by(group_id=group_id, teacher_id=current_user.id)
    # Фильтрация по предмету делается после выборки, с нормализацией

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
    if subject:
        norm_subj = normalize_subject_name(subject)
        lessons = [l for l in lessons if normalize_subject_name(l.subject or l.topic or '') == norm_subj]

    # Загружаем контрольные точки для группы
    control_points_query = ControlPoint.query.filter_by(group_id=group_id, teacher_id=current_user.id)
    
    # Фильтрация контрольных точек по месяцу, если указано
    if month_str:
        try:
            from datetime import datetime, timedelta
            start = datetime.strptime(month_str + '-01', '%Y-%m-%d').date()
            # вычисляем следующий месяц
            if start.month == 12:
                end = start.replace(year=start.year + 1, month=1, day=1)
            else:
                end = start.replace(month=start.month + 1, day=1)
            control_points_query = control_points_query.filter(ControlPoint.date >= start, ControlPoint.date < end)
        except Exception:
            pass

    control_points = control_points_query.order_by(ControlPoint.date.asc()).all()
    if subject:
        norm_subj = normalize_subject_name(subject)
        control_points = [
            cp for cp in control_points
            if (normalize_subject_name(cp.subject or '') == norm_subj) or not (cp.subject and cp.subject.strip())
        ]

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

    # Загружаем все оценки контрольных точек
    control_point_scores = db.session.query(ControlPointScore).join(Student, ControlPointScore.student_id == Student.id).join(ControlPoint, ControlPointScore.control_point_id == ControlPoint.id).filter(
        Student.group_id == group_id,
        ControlPoint.group_id == group_id
    ).all()

    control_point_marks = {}
    for score in control_point_scores:
        key = f"{score.student_id}:{score.control_point_id}"
        control_point_marks[key] = {
            'points': score.points
        }

    # Определяем читаемое название дисциплины: если не выбрана, возьмем из явного subject,
    # затем из наиболее частой темы занятий, иначе Group.course
    subject_name = normalize_subject_name(subject or '')
    if not subject_name:
        subject_name = normalize_subject_name(group.course or '')
    def _is_numeric(value: str) -> bool:
        try:
            float(value)
            return True
        except Exception:
            return False

    if not subject_name or _is_numeric(subject_name):
        topics = [l.topic.strip() for l in lessons if (l.topic or '').strip()]
        if topics:
            from collections import Counter
            subject_name = normalize_subject_name(Counter(topics).most_common(1)[0][0])

    return jsonify({
        'group': {
            'id': group.id,
            'name': group.name,
            'course': group.course,
            'subject': subject_name or group.course,
            'education_form': group.education_form
        },
        'students': [{'id': s.id, 'name': s.name} for s in students],
        'lessons': [{'id': l.id, 'date': l.date.isoformat(), 'topic': l.topic, 'notes': l.notes} for l in lessons],
        'control_points': [{'id': cp.id, 'date': cp.date.isoformat(), 'title': cp.title, 'max_points': cp.max_points} for cp in control_points],
        'marks': marks,
        'control_point_marks': control_point_marks,
        'stats': {
            'month_lessons': month_count,
            'total_lessons': total_count
        }
    })


@journal_bp.route('/api/group/subjects')
@login_required
def group_subjects():
    """Возвращает список дисциплин для группы (из Lesson.subject, ControlPoint.subject и Group.course)."""
    group_id = request.args.get('group_id', type=int)
    if not group_id:
        return jsonify({'error': 'group_id is required'}), 400

    Group.query.filter_by(id=group_id, teacher_id=current_user.id).first_or_404()

    subjects = set()

    # Явно заданные названия дисциплин в Lesson.subject
    lesson_subjects = db.session.query(Lesson.subject).filter(
        Lesson.group_id == group_id,
        Lesson.teacher_id == current_user.id,
        Lesson.subject != None,
        Lesson.subject != ''
    ).distinct().all()
    for (subj,) in lesson_subjects:
        norm = normalize_subject_name(subj)
        if norm:
            subjects.add(norm)

    # Названия дисциплин из контрольных точек
    cp_subjects = db.session.query(ControlPoint.subject).filter(
        ControlPoint.group_id == group_id,
        ControlPoint.teacher_id == current_user.id,
        ControlPoint.subject != None,
        ControlPoint.subject != ''
    ).distinct().all()
    for (subj,) in cp_subjects:
        norm = normalize_subject_name(subj)
        if norm:
            subjects.add(norm)

    # Если явных дисциплин нет, используем темы занятий как список дисциплин (fallback)
    if not subjects:
        lesson_topics = db.session.query(Lesson.topic).filter(
            Lesson.group_id == group_id,
            Lesson.teacher_id == current_user.id,
            Lesson.topic != None,
            Lesson.topic != ''
        ).distinct().all()
        for (top,) in lesson_topics:
            norm = normalize_subject_name(top)
            if norm:
                subjects.add(norm)

    # Не добавляем курс группы в список дисциплин - показываем только реальные дисциплины

    # Фильтруем мусор: числовые и слишком короткие значения
    cleaned_subjects = []
    for s in subjects:
        val = (s or '').strip()
        if not val:
            continue
        # отклоняем, если чисто число
        try:
            float(val)
            continue
        except Exception:
            pass
        # минимальная длина осмысленного названия
        if len(val) < 2:
            continue
        cleaned_subjects.append(val)

    # Если после очистки ничего не осталось, пробуем взять наиболее часто встречающуюся тему занятия
    if not cleaned_subjects:
        lesson_topics = db.session.query(Lesson.topic).filter(
            Lesson.group_id == group_id,
            Lesson.teacher_id == current_user.id,
            Lesson.topic != None,
            Lesson.topic != ''
        ).all()
        from collections import Counter
        counts = Counter([normalize_subject_name(t[0]) for t in lesson_topics if normalize_subject_name(t[0])])
        if counts:
            top_topic, _ = counts.most_common(1)[0]
            cleaned_subjects.append(top_topic)

    # Возвращаем отсортированный список
    return jsonify(sorted(cleaned_subjects))


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

    # Если значение пустое, удаляем запись посещаемости (ячейка остается пустой)
    if not value:
        attendance = Attendance.query.filter_by(student_id=student.id, lesson_id=lesson.id).first()
        if attendance:
            db.session.delete(attendance)
        db.session.commit()
        return jsonify({'status': 'success', 'present': None, 'mark': ''})

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
        attendance.attendance_mark = value

    db.session.commit()

    return jsonify({'status': 'success', 'present': attendance.present, 'mark': attendance.attendance_mark or ''})


@journal_bp.route('/api/lesson/<int:lesson_id>', methods=['GET', 'PUT'])
@login_required
def lesson_detail(lesson_id):
    """Получить или обновить детали занятия по id"""
    lesson = Lesson.query.filter_by(id=lesson_id, teacher_id=current_user.id).first_or_404()

    if request.method == 'PUT':
        data = request.get_json(force=True) or {}
        topic = data.get('topic')
        notes = data.get('notes')

        if topic is not None:
            lesson.topic = topic
        if notes is not None:
            lesson.notes = notes

        db.session.commit()
        return jsonify({'status': 'success'})

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
        db.func.sum(db.case((Attendance.present == True, 1), else_=0)).label('present')
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
    """Экспорт журнала посещаемости в XLSX (поддержка кириллицы).

    Формирует таблицу: строки — студенты, столбцы — даты занятий.
    Значения: '+' присутствовал, 'Н' отсутствовал, '' — нет данных.
    """
    group = Group.query.get_or_404(group_id)

    # Получаем список студентов (по алфавиту), занятий и контрольных точек (по дате)
    students = Student.query.filter_by(group_id=group_id).order_by(Student.name.asc()).all()
    lessons = Lesson.query.filter_by(group_id=group_id).order_by(Lesson.date.asc()).all()
    control_points = ControlPoint.query.filter_by(group_id=group_id).order_by(ControlPoint.date.asc()).all()

    # Собираем данные для экспорта
    data = []
    for student in students:
        row = {'Студент': student.name}
        # Занятия: +/Н/пусто
        for lesson in lessons:
            attendance = Attendance.query.filter_by(
                student_id=student.id,
                lesson_id=lesson.id
            ).first()
            if attendance is None:
                value = ''
            else:
                value = '+' if attendance.present else 'Н'
            row[lesson.date.strftime('%d.%m.%Y')] = value

        # Контрольные точки: баллы
        # Одновременно собираем для расчета Итог (средний процент)
        total_points = 0
        total_max = 0
        for cp in control_points:
            score = ControlPointScore.query.filter_by(
                student_id=student.id,
                control_point_id=cp.id
            ).first()
            points_val = '' if score is None or score.points is None else score.points
            header = f"КТ {cp.date.strftime('%d.%m.%Y')} — {cp.title}"
            row[header] = points_val

            if score is not None and score.points is not None:
                # Накопим для среднего в процентах
                total_points += float(score.points)
                total_max += float(cp.max_points or 100)

        # Итог: средний процент по КТ (округление до 1 знака) или '-' если нет оценок
        if total_max > 0:
            avg_percent = round((total_points / total_max) * 100, 1)
            row['Итог'] = avg_percent
        else:
            row['Итог'] = '-'

        data.append(row)

    # Создаем DataFrame с фиксированным порядком колонок
    # Формируем порядок столбцов: Студент | все занятия | все КТ | Итог
    lesson_cols = [l.date.strftime('%d.%m.%Y') for l in lessons]
    cp_cols = [f"КТ {cp.date.strftime('%d.%m.%Y')} — {cp.title}" for cp in control_points]
    columns = ['Студент'] + lesson_cols + cp_cols + ['Итог']
    df = pd.DataFrame(data)
    if not df.empty:
        # Упорядочим столбцы; отсутствующие добавятся автоматически
        for col in columns:
            if col not in df.columns:
                df[col] = ''
        df = df[columns]

    # Готовим имя файла; оставляем кириллицу — XLSX поддерживает
    safe_group = str(group.name).replace('/', '_').replace('\\', '_').strip()
    filename = f'attendance_{safe_group}_{datetime.now().strftime("%Y%m%d")}.xlsx'
    export_path = f'static/exports/{filename}'

    # Записываем в XLSX через openpyxl (по умолчанию у pandas для xlsx)
    # XLSX — бинарный формат, проблем с кодировкой кириллицы нет
    with pd.ExcelWriter(export_path, engine='openpyxl') as writer:
        sheet_name = 'Журнал'
        df.to_excel(writer, index=False, sheet_name=sheet_name)

        # Немного улучшим форматирование ширины колонок
        ws = writer.sheets[sheet_name]
        for col_cells in ws.columns:
            max_len = 0
            col_letter = col_cells[0].column_letter
            for c in col_cells:
                try:
                    val = c.value if c.value is not None else ''
                    max_len = max(max_len, len(str(val)))
                except Exception:
                    pass
            ws.column_dimensions[col_letter].width = min(max(12, max_len + 2), 40)

    return jsonify({'file': f'/static/exports/{filename}'})


@journal_bp.route('/api/control-point/create', methods=['POST'])
@login_required
def create_control_point():
    """Создает новую контрольную точку"""
    data = request.get_json()
    group_id = data.get('group_id')
    date_str = data.get('date')
    title = data.get('title', 'КТ')
    max_points = data.get('max_points', 100)
    subject = normalize_subject_name(data.get('subject') or '')

    if not group_id or not date_str:
        return jsonify({'error': 'group_id and date are required'}), 400

    # Проверяем, что группа принадлежит преподавателю
    group = Group.query.filter_by(id=group_id, teacher_id=current_user.id).first_or_404()

    try:
        date = datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        return jsonify({'error': 'Invalid date format'}), 400

    # Проверяем, что на эту дату для данной группы еще нет контрольной точки
    existing_control_point = ControlPoint.query.filter_by(
        group_id=group_id,
        date=date
    ).first()
    
    if existing_control_point:
        return jsonify({
            'error': f'На дату {date.strftime("%d.%m.%Y")} уже создана контрольная точка "{existing_control_point.title}"'
        }), 400

    control_point = ControlPoint(
        group_id=group_id,
        teacher_id=current_user.id,
        date=date,
        title=title,
        max_points=max_points,
        # Не записываем предмет по умолчанию из Group.course, чтобы не засорять список дисциплин
        subject=subject or None
    )

    db.session.add(control_point)
    db.session.commit()

    return jsonify({
        'status': 'success',
        'control_point': {
            'id': control_point.id,
            'date': control_point.date.isoformat(),
            'title': control_point.title,
            'max_points': control_point.max_points
        }
    })


@journal_bp.route('/api/control-point/<int:control_point_id>', methods=['PUT', 'DELETE'])
@login_required
def manage_control_point(control_point_id):
    """Обновляет или удаляет контрольную точку"""
    control_point = ControlPoint.query.filter_by(id=control_point_id, teacher_id=current_user.id).first_or_404()

    if request.method == 'PUT':
        data = request.get_json()
        date_str = data.get('date')
        title = data.get('title')
        max_points = data.get('max_points')

        if date_str:
            try:
                new_date = datetime.strptime(date_str, '%Y-%m-%d').date()
                # Проверяем, что новая дата не конфликтует с существующими КТ
                if new_date != control_point.date:
                    existing = ControlPoint.query.filter_by(
                        group_id=control_point.group_id, 
                        date=new_date, 
                        teacher_id=current_user.id
                    ).first()
                    if existing:
                        return jsonify({'error': 'Control point with this date already exists'}), 400
                control_point.date = new_date
            except ValueError:
                return jsonify({'error': 'Invalid date format'}), 400

        if title is not None:
            control_point.title = title
        if max_points is not None:
            control_point.max_points = max_points

        db.session.commit()

        return jsonify({
            'status': 'success',
            'control_point': {
                'id': control_point.id,
                'date': control_point.date.isoformat(),
                'title': control_point.title,
                'max_points': control_point.max_points
            }
        })

    elif request.method == 'DELETE':
        # Удаляем все оценки для этой контрольной точки
        ControlPointScore.query.filter_by(control_point_id=control_point_id).delete()
        db.session.delete(control_point)
        db.session.commit()

        return jsonify({'status': 'success', 'message': 'Control point deleted'})


@journal_bp.route('/api/control-point/score', methods=['POST'])
@login_required
def save_control_point_score():
    """Сохраняет оценку контрольной точки для студента"""
    data = request.get_json()
    control_point_id = data.get('control_point_id')
    student_id = data.get('student_id')
    points = data.get('points')

    if not control_point_id or not student_id:
        return jsonify({'error': 'control_point_id and student_id are required'}), 400

    # Проверяем, что контрольная точка принадлежит преподавателю
    control_point = ControlPoint.query.filter_by(id=control_point_id, teacher_id=current_user.id).first_or_404()
    
    # Проверяем, что студент принадлежит группе
    student = Student.query.filter_by(id=student_id, group_id=control_point.group_id).first_or_404()

    # Валидация баллов
    if points is not None:
        try:
            points = int(points)
            if points < 0 or points > control_point.max_points:
                return jsonify({'error': f'Points must be between 0 and {control_point.max_points}'}), 400
        except (ValueError, TypeError):
            return jsonify({'error': 'Invalid points value'}), 400

    # Находим или создаем запись оценки
    score = ControlPointScore.query.filter_by(
        control_point_id=control_point_id,
        student_id=student_id
    ).first()

    if points is None:
        # Удаляем оценку, если передано None
        if score:
            db.session.delete(score)
    else:
        if score:
            score.points = points
            score.updated_at = datetime.utcnow()
        else:
            score = ControlPointScore(
                control_point_id=control_point_id,
                student_id=student_id,
                points=points
            )
            db.session.add(score)

    db.session.commit()

    return jsonify({
        'status': 'success',
        'points': points
    })