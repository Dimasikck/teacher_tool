from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from models import db, Group, Student
from datetime import datetime

groups_bp = Blueprint('groups', __name__, url_prefix='/groups')


@groups_bp.route('/')
@login_required
def groups():
    """Список всех групп преподавателя"""
    groups = Group.query.filter_by(teacher_id=current_user.id).all()
    return render_template('groups.html', groups=groups)


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
    
    students = Student.query.filter_by(group_id=group_id).all()
    return render_template('group_detail.html', group=group, students=students)


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
    
    # Проверяем, есть ли студенты в группе
    students_count = Student.query.filter_by(group_id=group_id).count()
    if students_count > 0:
        flash('Нельзя удалить группу, в которой есть студенты', 'error')
        return redirect(url_for('groups.group_detail', group_id=group_id))
    
    db.session.delete(group)
    db.session.commit()
    
    flash('Группа успешно удалена', 'success')
    return redirect(url_for('groups.groups'))


# API маршруты для студентов
@groups_bp.route('/<int:group_id>/students', methods=['POST'])
@login_required
def add_student(group_id):
    """Добавление студента в группу"""
    group = Group.query.filter_by(
        id=group_id, 
        teacher_id=current_user.id
    ).first_or_404()
    
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
        
        db.session.add(new_student)
        # Добавляем студента в список для отображения (без id пока)
        added_students.append({
            'name': new_student.name,
            'email': new_student.email
        })
    
    if added_students:
        db.session.commit()
        print(f"Successfully added {len(added_students)} students to group {group_id}")
        
        # Получаем ID добавленных студентов после коммита
        for i, student_data in enumerate(added_students):
            student = Student.query.filter_by(
                name=student_data['name'],
                group_id=group_id
            ).first()
            if student:
                added_students[i]['id'] = student.id
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
