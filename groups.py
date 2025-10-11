from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from models import db, Group, Student, Attendance, Lesson
from datetime import datetime

groups_bp = Blueprint('groups', __name__, url_prefix='/groups')


@groups_bp.route('/')
@login_required
def groups():
    """Список всех групп преподавателя с сортировкой и фильтрацией"""
    # Получаем параметры фильтрации и сортировки
    course_filter = request.args.get('course', '')
    education_form_filter = request.args.get('education_form', '')
    sort_by = request.args.get('sort', 'name')  # name, course, education_form, students_count
    sort_order = request.args.get('order', 'asc')  # asc, desc
    
    # Базовый запрос
    query = Group.query.filter_by(teacher_id=current_user.id)
    
    # Применяем фильтры
    if course_filter:
        query = query.filter(Group.course.ilike(f'%{course_filter}%'))
    if education_form_filter:
        query = query.filter(Group.education_form.ilike(f'%{education_form_filter}%'))
    
    # Применяем сортировку
    if sort_by == 'name':
        if sort_order == 'desc':
            query = query.order_by(Group.name.desc())
        else:
            query = query.order_by(Group.name.asc())
    elif sort_by == 'course':
        if sort_order == 'desc':
            query = query.order_by(Group.course.desc())
        else:
            query = query.order_by(Group.course.asc())
    elif sort_by == 'education_form':
        if sort_order == 'desc':
            query = query.order_by(Group.education_form.desc())
        else:
            query = query.order_by(Group.education_form.asc())
    elif sort_by == 'students_count':
        # Для сортировки по количеству студентов нужен подзапрос
        from sqlalchemy import func
        if sort_order == 'desc':
            query = query.outerjoin(Student).group_by(Group.id).order_by(func.count(Student.id).desc())
        else:
            query = query.outerjoin(Student).group_by(Group.id).order_by(func.count(Student.id).asc())
    else:
        query = query.order_by(Group.name.asc())
    
    groups = query.all()
    
    # Получаем уникальные значения для фильтров
    all_courses = db.session.query(Group.course).filter_by(teacher_id=current_user.id).distinct().all()
    all_education_forms = db.session.query(Group.education_form).filter_by(teacher_id=current_user.id).distinct().all()
    
    return render_template('groups.html', 
                         groups=groups,
                         all_courses=[course[0] for course in all_courses if course[0]],
                         all_education_forms=[form[0] for form in all_education_forms if form[0]],
                         current_course=course_filter,
                         current_education_form=education_form_filter,
                         current_sort=sort_by,
                         current_order=sort_order)


@groups_bp.route('/create', methods=['GET', 'POST'])
@login_required
def create_group():
    """Создание новой группы"""
    if request.method == 'POST':
        name = request.form['name']
        course = request.form['course']
        education_form = request.form['education_form']
        color = request.form.get('color', '#007bff')
        
        # Проверяем, что группа с таким именем не существует
        existing_group = Group.query.filter_by(
            name=name, 
            teacher_id=current_user.id
        ).first()
        
        if existing_group:
            flash('Группа с таким названием уже существует', 'error')
            return render_template('create_group.html')
        
        new_group = Group(
            name=name,
            course=course,
            education_form=education_form,
            color=color,
            teacher_id=current_user.id
        )
        
        db.session.add(new_group)
        db.session.commit()
        
        flash('Группа успешно создана', 'success')
        return redirect(url_for('groups.groups'))
    
    return render_template('create_group.html')


@groups_bp.route('/<int:group_id>')
@login_required
def group_detail(group_id):
    """Детальная страница группы со списком студентов"""
    group = Group.query.filter_by(
        id=group_id, 
        teacher_id=current_user.id
    ).first_or_404()
    
    # Сортируем студентов по алфавиту
    students = Student.query.filter_by(group_id=group_id).order_by(Student.name.asc()).all()

    # Собираем статистику по пропускам и среднему баллу из журнала
    # Загружаем все Attendance для данной группы разом
    attendance_rows = db.session.query(Attendance).join(Lesson, Attendance.lesson_id == Lesson.id).join(Student, Attendance.student_id == Student.id).filter(
        Lesson.group_id == group_id,
        Lesson.teacher_id == current_user.id,
        Student.group_id == group_id
    ).all()

    stats = {}
    for student in students:
        stats[student.id] = {"absences": 0, "average": None}

    for a in attendance_rows:
        # Подсчет пропусков: отметка "Н" или present == False
        is_absent = (a.attendance_mark or '').strip().upper() == 'Н' or (a.present is False)
        if is_absent:
            if a.student_id in stats:
                stats[a.student_id]["absences"] += 1

        # Подсчет среднего: учитываем только числовые оценки
        mark_str = (a.attendance_mark or '').strip().replace(',', '.')
        try:
            mark_val = float(mark_str)
        except Exception:
            mark_val = None
        if mark_val is not None:
            entry = stats.get(a.student_id)
            if entry is not None:
                # временно накапливаем сумму и количество в скрытых ключах
                entry["_sum"] = entry.get("_sum", 0.0) + mark_val
                entry["_cnt"] = entry.get("_cnt", 0) + 1

    # Финализируем среднее
    for sid, entry in stats.items():
        cnt = entry.get("_cnt", 0)
        if cnt > 0:
            entry["average"] = round(entry.get("_sum", 0.0) / cnt, 2)
        # Удаляем временные ключи
        entry.pop("_sum", None)
        entry.pop("_cnt", None)

    return render_template('group_detail.html', group=group, students=students, stats=stats)


@groups_bp.route('/<int:group_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_group(group_id):
    """Редактирование группы"""
    group = Group.query.filter_by(
        id=group_id, 
        teacher_id=current_user.id
    ).first_or_404()
    
    if request.method == 'POST':
        group.name = request.form['name']
        group.course = request.form['course']
        group.education_form = request.form['education_form']
        group.color = request.form.get('color', group.color)
        
        db.session.commit()
        flash('Группа успешно обновлена', 'success')
        return redirect(url_for('groups.group_detail', group_id=group_id))
    
    return render_template('edit_group.html', group=group)


@groups_bp.route('/<int:group_id>/delete', methods=['POST'])
@login_required
def delete_group(group_id):
    """Удаление группы"""
    group = Group.query.filter_by(
        id=group_id, 
        teacher_id=current_user.id
    ).first_or_404()
    
    # Удаляем всех студентов группы
    students = Student.query.filter_by(group_id=group_id).all()
    for student in students:
        db.session.delete(student)
    
    # Удаляем группу
    db.session.delete(group)
    db.session.commit()
    
    flash('Группа и все студенты успешно удалены', 'success')
    return redirect(url_for('groups.groups'))


# API маршруты для студентов
@groups_bp.route('/<int:group_id>/students', methods=['GET', 'POST'])
@login_required
def add_student(group_id):
    """Получение списка студентов (GET) или добавление студента (POST)"""
    group = Group.query.filter_by(
        id=group_id, 
        teacher_id=current_user.id
    ).first_or_404()
    if request.method == 'GET':
        students = Student.query.filter_by(group_id=group_id).order_by(Student.name.asc()).all()

        # Статистика для API: аналогично как на детальной странице
        attendance_rows = db.session.query(Attendance).join(Lesson, Attendance.lesson_id == Lesson.id).join(Student, Attendance.student_id == Student.id).filter(
            Lesson.group_id == group_id,
            Lesson.teacher_id == current_user.id,
            Student.group_id == group_id
        ).all()

        api_stats = {s.id: {"absences": 0, "average": None} for s in students}
        for a in attendance_rows:
            is_absent = (a.attendance_mark or '').strip().upper() == 'Н' or (a.present is False)
            if is_absent and a.student_id in api_stats:
                api_stats[a.student_id]["absences"] += 1

            mark_str = (a.attendance_mark or '').strip().replace(',', '.')
            try:
                mark_val = float(mark_str)
            except Exception:
                mark_val = None
            if mark_val is not None and a.student_id in api_stats:
                api_stats[a.student_id]["_sum"] = api_stats[a.student_id].get("_sum", 0.0) + mark_val
                api_stats[a.student_id]["_cnt"] = api_stats[a.student_id].get("_cnt", 0) + 1

        for sid, st in api_stats.items():
            cnt = st.get("_cnt", 0)
            if cnt > 0:
                st["average"] = round(st.get("_sum", 0.0) / cnt, 2)
            st.pop("_sum", None)
            st.pop("_cnt", None)

        return jsonify({
            'success': True,
            'students': [
                {'id': s.id, 'name': s.name, 'email': s.email,
                 'absences': api_stats.get(s.id, {}).get('absences', 0),
                 'average': api_stats.get(s.id, {}).get('average', None)}
                for s in students
            ]
        })

    data = request.get_json()
    name = data.get('name')
    email = data.get('email', '')
    
    if not name:
        return jsonify({'error': 'Имя студента обязательно'}), 400
    
    # Проверяем, что студент с таким именем не существует в группе
    existing_student = Student.query.filter_by(
        name=name, 
        group_id=group_id
    ).first()
    
    if existing_student:
        return jsonify({'error': 'Студент с таким именем уже существует в группе'}), 400
    
    new_student = Student(
        name=name,
        email=email,
        group_id=group_id
    )
    
    db.session.add(new_student)
    db.session.commit()
    
    return jsonify({
        'success': True,
        'student': {
            'id': new_student.id,
            'name': new_student.name,
            'email': new_student.email
        }
    })


@groups_bp.route('/<int:group_id>/students/batch', methods=['POST'])
@login_required
def add_students_batch(group_id):
    """Массовое добавление студентов в группу"""
    group = Group.query.filter_by(
        id=group_id, 
        teacher_id=current_user.id
    ).first_or_404()
    
    data = request.get_json()
    students_text = data.get('students_text', '')
    
    if not students_text.strip():
        return jsonify({'error': 'Список студентов не может быть пустым'}), 400
    
    # Парсим список студентов
    students_lines = [line.strip() for line in students_text.split('\n') if line.strip()]
    
    if not students_lines:
        return jsonify({'error': 'Не найдено ни одного студента для добавления'}), 400
    
    added_students = []
    errors = []
    students_to_add = []  # Список объектов Student для добавления
    
    for i, line in enumerate(students_lines, 1):
        # Поддерживаем формат "Имя Фамилия" или "Имя Фамилия, email@example.com"
        if ',' in line:
            name, email = line.split(',', 1)
            name = name.strip()
            email = email.strip()
        else:
            name = line.strip()
            email = ''
        
        if not name:
            errors.append(f'Строка {i}: имя студента не может быть пустым')
            continue
        
        # Проверяем, что студент с таким именем не существует в группе
        existing_student = Student.query.filter_by(
            name=name, 
            group_id=group_id
        ).first()
        
        if existing_student:
            errors.append(f'Строка {i}: студент "{name}" уже существует в группе')
            continue
        
        new_student = Student(
            name=name,
            email=email,
            group_id=group_id
        )
        
        students_to_add.append(new_student)
    
    if students_to_add:
        # Добавляем всех студентов в сессию
        for student in students_to_add:
            db.session.add(student)
        
        # Коммитим все изменения
        db.session.commit()
        
        print(f"Successfully added {len(students_to_add)} students to group {group_id}")
        
        # Теперь у всех студентов есть ID, формируем список для ответа
        for student in students_to_add:
            added_students.append({
                'id': student.id,
                'name': student.name,
                'email': student.email
            })
    else:
        print(f"No students were added to group {group_id}")
    
    if errors:
        print(f"Errors during batch add: {errors}")
    
    return jsonify({
        'success': len(added_students) > 0,
        'added_count': len(added_students),
        'students': added_students,
        'errors': errors,
        'total_processed': len(students_lines)
    })


@groups_bp.route('/<int:group_id>/students/<int:student_id>', methods=['PUT'])
@login_required
def edit_student(group_id, student_id):
    """Редактирование студента"""
    group = Group.query.filter_by(
        id=group_id, 
        teacher_id=current_user.id
    ).first_or_404()
    
    student = Student.query.filter_by(
        id=student_id, 
        group_id=group_id
    ).first_or_404()
    
    data = request.get_json()
    student.name = data.get('name', student.name)
    student.email = data.get('email', student.email)
    
    db.session.commit()
    
    return jsonify({
        'success': True,
        'student': {
            'id': student.id,
            'name': student.name,
            'email': student.email
        }
    })


@groups_bp.route('/<int:group_id>/students/<int:student_id>', methods=['DELETE'])
@login_required
def delete_student(group_id, student_id):
    """Удаление студента из группы"""
    group = Group.query.filter_by(
        id=group_id, 
        teacher_id=current_user.id
    ).first_or_404()
    
    student = Student.query.filter_by(
        id=student_id, 
        group_id=group_id
    ).first_or_404()
    
    db.session.delete(student)
    db.session.commit()
    
    return jsonify({'success': True})
