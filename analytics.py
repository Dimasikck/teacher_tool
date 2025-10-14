from flask import Blueprint, render_template, request, jsonify, send_file
from flask_login import login_required, current_user
from sqlalchemy import func, and_, or_, desc, asc
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
from io import BytesIO
import json

from models import db, Teacher, Student, Group, Assignment, Task, Attendance, Lesson

analytics_bp = Blueprint('analytics', __name__)

def calculate_attendance_percentage(student_id, group_id, start_date=None, end_date=None):
    """Вычисляет процент посещаемости студента"""
    if not start_date:
        start_date = datetime.now() - timedelta(days=30)
    if not end_date:
        end_date = datetime.now()
    
    # Получаем все занятия группы за период
    total_classes = Lesson.query.filter(
        Lesson.group_id == group_id,
        Lesson.date >= start_date,
        Lesson.date <= end_date
    ).count()
    
    if total_classes == 0:
        return 0
    
    # Получаем количество посещений студента
    attended_classes = db.session.query(Attendance).join(Lesson).filter(
        Lesson.group_id == group_id,
        Attendance.student_id == student_id,
        Lesson.date >= start_date,
        Lesson.date <= end_date,
        Attendance.present == True
    ).count()
    
    return round((attended_classes / total_classes) * 100, 2)

def calculate_average_grade(student_id, group_id, start_date=None, end_date=None):
    """Вычисляет средний балл студента"""
    if not start_date:
        start_date = datetime.now() - timedelta(days=30)
    if not end_date:
        end_date = datetime.now()
    
    # Получаем все оценки студента за период из Attendance
    grades = db.session.query(Attendance).join(Lesson).filter(
        Lesson.group_id == group_id,
        Attendance.student_id == student_id,
        Lesson.date >= start_date,
        Lesson.date <= end_date,
        Attendance.attendance_mark.isnot(None)
    ).all()
    
    if not grades:
        return 0
    
    # Преобразуем текстовые оценки в числовые
    numeric_grades = []
    for grade in grades:
        try:
            # Пытаемся преобразовать в число
            numeric_grade = float(grade.attendance_mark)
            numeric_grades.append(numeric_grade)
        except (ValueError, TypeError):
            # Если не число, пропускаем
            continue
    
    if not numeric_grades:
        return 0
    
    return round(sum(numeric_grades) / len(numeric_grades), 2)

def calculate_assignment_completion(student_id, group_id, start_date=None, end_date=None):
    """Вычисляет процент выполнения заданий студентом"""
    if not start_date:
        start_date = datetime.now() - timedelta(days=30)
    if not end_date:
        end_date = datetime.now()
    
    # Получаем все задания студента за период
    assignments = Assignment.query.filter(
        Assignment.student_id == student_id,
        Assignment.submitted_at >= start_date,
        Assignment.submitted_at <= end_date
    ).all()
    
    if not assignments:
        return 0
    
    # Считаем выполненные задания (те, у которых есть оценка или файл)
    completed = 0
    for assignment in assignments:
        if assignment.score is not None or assignment.file_path or assignment.cloud_url:
            completed += 1
    
    return round((completed / len(assignments)) * 100, 2)

def get_student_analytics(student_id, group_id, start_date=None, end_date=None):
    """Получает полную аналитику по студенту"""
    if not start_date:
        start_date = datetime.now() - timedelta(days=30)
    if not end_date:
        end_date = datetime.now()
    
    student = Student.query.get(student_id)
    if not student:
        return None
    
    attendance = calculate_attendance_percentage(student_id, group_id, start_date, end_date)
    avg_grade = calculate_average_grade(student_id, group_id, start_date, end_date)
    completion = calculate_assignment_completion(student_id, group_id, start_date, end_date)
    
    # Определяем категорию студента
    category = "Отличник"
    if attendance < 70 or avg_grade < 60 or completion < 50:
        category = "Отстающий"
    elif attendance < 85 or avg_grade < 75 or completion < 70:
        category = "Средний уровень"
    
    return {
        'student': student,
        'attendance': attendance,
        'avg_grade': avg_grade,
        'completion': completion,
        'category': category
    }

def get_group_analytics(group_id, start_date=None, end_date=None):
    """Получает аналитику по группе"""
    if not start_date:
        start_date = datetime.now() - timedelta(days=30)
    if not end_date:
        end_date = datetime.now()
    
    group = Group.query.get(group_id)
    if not group:
        return None
    
    # Получаем всех студентов группы
    students = Student.query.filter(Student.group_id == group_id).all()
    
    analytics = []
    total_attendance = 0
    total_grades = 0
    total_completion = 0
    grade_count = 0
    
    for student in students:
        student_analytics = get_student_analytics(student.id, group_id, start_date, end_date)
        if student_analytics:
            analytics.append(student_analytics)
            total_attendance += student_analytics['attendance']
            total_completion += student_analytics['completion']
            if student_analytics['avg_grade'] > 0:
                total_grades += student_analytics['avg_grade']
                grade_count += 1
    
    # Вычисляем средние показатели группы
    avg_attendance = round(total_attendance / len(analytics), 2) if analytics else 0
    avg_grade = round(total_grades / grade_count, 2) if grade_count > 0 else 0
    avg_completion = round(total_completion / len(analytics), 2) if analytics else 0
    
    return {
        'group': group,
        'students': analytics,
        'avg_attendance': avg_attendance,
        'avg_grade': avg_grade,
        'avg_completion': avg_completion,
        'total_students': len(analytics)
    }

def get_problematic_students(group_id, start_date=None, end_date=None):
    """Выявляет проблемных студентов"""
    if not start_date:
        start_date = datetime.now() - timedelta(days=30)
    if not end_date:
        end_date = datetime.now()
    
    group_analytics = get_group_analytics(group_id, start_date, end_date)
    if not group_analytics:
        return []
    
    problematic = []
    for student_data in group_analytics['students']:
        issues = []
        priority = 0
        
        if student_data['attendance'] < 70:
            issues.append(f"Низкая посещаемость: {student_data['attendance']}%")
            priority += 3
        
        if student_data['avg_grade'] < 60:
            issues.append(f"Низкие оценки: {student_data['avg_grade']}")
            priority += 3
        
        if student_data['completion'] < 50:
            issues.append(f"Низкое выполнение заданий: {student_data['completion']}%")
            priority += 2
        
        if issues:
            problematic.append({
                'student': student_data['student'],
                'issues': issues,
                'priority': priority,
                'attendance': student_data['attendance'],
                'avg_grade': student_data['avg_grade'],
                'completion': student_data['completion']
            })
    
    # Сортируем по приоритету
    problematic.sort(key=lambda x: x['priority'], reverse=True)
    return problematic

def get_top_students(group_id, start_date=None, end_date=None):
    """Выявляет лучших студентов"""
    if not start_date:
        start_date = datetime.now() - timedelta(days=30)
    if not end_date:
        end_date = datetime.now()
    
    group_analytics = get_group_analytics(group_id, start_date, end_date)
    if not group_analytics:
        return []
    
    top_students = []
    for student_data in group_analytics['students']:
        if (student_data['attendance'] >= 95 and 
            student_data['avg_grade'] >= 90 and 
            student_data['completion'] >= 90):
            top_students.append(student_data)
    
    # Сортируем по среднему баллу
    top_students.sort(key=lambda x: x['avg_grade'], reverse=True)
    return top_students

def generate_attendance_report(group_id, start_date=None, end_date=None):
    """Генерирует отчет по посещаемости"""
    group_analytics = get_group_analytics(group_id, start_date, end_date)
    if not group_analytics:
        return None
    
    report_data = []
    for student_data in group_analytics['students']:
        report_data.append({
            'Студент': student_data['student'].full_name,
            'Посещаемость (%)': student_data['attendance'],
            'Средний балл': student_data['avg_grade'],
            'Выполнение заданий (%)': student_data['completion'],
            'Категория': student_data['category']
        })
    
    return pd.DataFrame(report_data)

def generate_grade_distribution(group_id, start_date=None, end_date=None):
    """Генерирует распределение оценок"""
    if not start_date:
        start_date = datetime.now() - timedelta(days=30)
    if not end_date:
        end_date = datetime.now()
    
    # Получаем все оценки группы за период
    grades = db.session.query(Attendance).join(Lesson).filter(
        Lesson.group_id == group_id,
        Lesson.date >= start_date,
        Lesson.date <= end_date,
        Attendance.attendance_mark.isnot(None)
    ).all()
    
    if not grades:
        return {}
    
    # Преобразуем текстовые оценки в числовые
    grade_values = []
    for grade in grades:
        try:
            numeric_grade = float(grade.attendance_mark)
            grade_values.append(numeric_grade)
        except (ValueError, TypeError):
            continue
    
    if not grade_values:
        return {}
    
    # Создаем распределение по диапазонам
    distribution = {
        'Отлично (90-100)': len([g for g in grade_values if g >= 90]),
        'Хорошо (75-89)': len([g for g in grade_values if 75 <= g < 90]),
        'Удовлетворительно (60-74)': len([g for g in grade_values if 60 <= g < 75]),
        'Неудовлетворительно (0-59)': len([g for g in grade_values if g < 60])
    }
    
    return distribution

def calculate_correlation(group_id, start_date=None, end_date=None):
    """Вычисляет корреляцию между посещаемостью и успеваемостью"""
    if not start_date:
        start_date = datetime.now() - timedelta(days=30)
    if not end_date:
        end_date = datetime.now()
    
    group_analytics = get_group_analytics(group_id, start_date, end_date)
    if not group_analytics or len(group_analytics['students']) < 2:
        return 0
    
    attendance_values = [s['attendance'] for s in group_analytics['students']]
    grade_values = [s['avg_grade'] for s in group_analytics['students'] if s['avg_grade'] > 0]
    
    if len(attendance_values) != len(grade_values) or len(attendance_values) < 2:
        return 0
    
    # Вычисляем коэффициент корреляции Пирсона
    correlation = np.corrcoef(attendance_values, grade_values)[0, 1]
    return round(correlation, 3) if not np.isnan(correlation) else 0

@analytics_bp.route('/analytics')
@login_required
def analytics_dashboard():
    """Главная страница аналитики"""
    # Получаем группы преподавателя
    groups = Group.query.filter(Group.teacher_id == current_user.id).all()
    
    return render_template('analytics.html', groups=groups)

@analytics_bp.route('/analytics/group/<int:group_id>')
@login_required
def group_analytics(group_id):
    """Аналитика по конкретной группе"""
    group = Group.query.get_or_404(group_id)
    
    # Проверяем права доступа - только преподаватель группы может видеть аналитику
    if group.teacher_id != current_user.id:
        return "Доступ запрещен", 403
    
    # Получаем параметры фильтрации
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    
    if start_date:
        start_date = datetime.strptime(start_date, '%Y-%m-%d')
    else:
        start_date = datetime.now() - timedelta(days=30)
    
    if end_date:
        end_date = datetime.strptime(end_date, '%Y-%m-%d')
    else:
        end_date = datetime.now()
    
    # Получаем аналитику
    analytics = get_group_analytics(group_id, start_date, end_date)
    problematic = get_problematic_students(group_id, start_date, end_date)
    top_students = get_top_students(group_id, start_date, end_date)
    grade_distribution = generate_grade_distribution(group_id, start_date, end_date)
    correlation = calculate_correlation(group_id, start_date, end_date)
    
    return render_template('group_analytics.html',
                         group=group,
                         analytics=analytics,
                         problematic=problematic,
                         top_students=top_students,
                         grade_distribution=grade_distribution,
                         correlation=correlation,
                         start_date=start_date.strftime('%Y-%m-%d'),
                         end_date=end_date.strftime('%Y-%m-%d'))

@analytics_bp.route('/analytics/student/<int:student_id>')
@login_required
def student_analytics(student_id):
    """Индивидуальная аналитика студента"""
    student = Student.query.get_or_404(student_id)
    
    # Проверяем права доступа - только преподаватель группы студента может видеть аналитику
    group = Group.query.get(student.group_id)
    if not group or group.teacher_id != current_user.id:
        return "Доступ запрещен", 403
    
    # Получаем группы студента
    student_groups = Group.query.filter(Group.id == student.group_id).all()
    
    # Получаем параметры фильтрации
    group_id = request.args.get('group_id', type=int)
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    
    if start_date:
        start_date = datetime.strptime(start_date, '%Y-%m-%d')
    else:
        start_date = datetime.now() - timedelta(days=30)
    
    if end_date:
        end_date = datetime.strptime(end_date, '%Y-%m-%d')
    else:
        end_date = datetime.now()
    
    analytics_data = {}
    if group_id:
        analytics_data = get_student_analytics(student_id, group_id, start_date, end_date)
    
    return render_template('student_analytics.html',
                         student=student,
                         student_groups=student_groups,
                         analytics=analytics_data,
                         selected_group_id=group_id,
                         start_date=start_date.strftime('%Y-%m-%d'),
                         end_date=end_date.strftime('%Y-%m-%d'))

@analytics_bp.route('/analytics/export/<int:group_id>')
@login_required
def export_analytics(group_id):
    """Экспорт аналитики в XLSX"""
    group = Group.query.get_or_404(group_id)
    
    # Проверяем права доступа - только преподаватель группы может экспортировать аналитику
    if group.teacher_id != current_user.id:
        return "Доступ запрещен", 403
    
    # Получаем параметры фильтрации
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    report_type = request.args.get('type', 'attendance')
    
    if start_date:
        start_date = datetime.strptime(start_date, '%Y-%m-%d')
    else:
        start_date = datetime.now() - timedelta(days=30)
    
    if end_date:
        end_date = datetime.strptime(end_date, '%Y-%m-%d')
    else:
        end_date = datetime.now()
    
    # Генерируем отчет
    if report_type == 'attendance':
        df = generate_attendance_report(group_id, start_date, end_date)
        filename = f'attendance_report_{group.name}_{start_date.strftime("%Y%m%d")}_{end_date.strftime("%Y%m%d")}.xlsx'
    else:
        return "Неверный тип отчета", 400
    
    if df is None or df.empty:
        return "Нет данных для экспорта", 400
    
    # Создаем Excel файл
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, sheet_name='Отчет', index=False)
    
    output.seek(0)
    
    return send_file(output,
                    as_attachment=True,
                    download_name=filename,
                    mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

@analytics_bp.route('/analytics/api/chart-data/<int:group_id>')
@login_required
def chart_data(group_id):
    """API для получения данных для графиков"""
    group = Group.query.get_or_404(group_id)
    
    # Проверяем права доступа - только преподаватель группы может получать данные
    if group.teacher_id != current_user.id:
        return "Доступ запрещен", 403
    
    # Получаем параметры фильтрации
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    chart_type = request.args.get('type', 'attendance')
    
    if start_date:
        start_date = datetime.strptime(start_date, '%Y-%m-%d')
    else:
        start_date = datetime.now() - timedelta(days=30)
    
    if end_date:
        end_date = datetime.strptime(end_date, '%Y-%m-%d')
    else:
        end_date = datetime.now()
    
    if chart_type == 'attendance':
        analytics = get_group_analytics(group_id, start_date, end_date)
        if not analytics:
            return jsonify({'error': 'Нет данных'})
        
        data = {
            'labels': [s['student'].full_name for s in analytics['students']],
            'datasets': [{
                'label': 'Посещаемость (%)',
                'data': [s['attendance'] for s in analytics['students']],
                'backgroundColor': 'rgba(54, 162, 235, 0.2)',
                'borderColor': 'rgba(54, 162, 235, 1)',
                'borderWidth': 1
            }]
        }
    
    elif chart_type == 'grades':
        grade_distribution = generate_grade_distribution(group_id, start_date, end_date)
        data = {
            'labels': list(grade_distribution.keys()),
            'datasets': [{
                'label': 'Количество студентов',
                'data': list(grade_distribution.values()),
                'backgroundColor': [
                    'rgba(75, 192, 192, 0.2)',
                    'rgba(255, 205, 86, 0.2)',
                    'rgba(255, 99, 132, 0.2)',
                    'rgba(255, 159, 64, 0.2)'
                ],
                'borderColor': [
                    'rgba(75, 192, 192, 1)',
                    'rgba(255, 205, 86, 1)',
                    'rgba(255, 99, 132, 1)',
                    'rgba(255, 159, 64, 1)'
                ],
                'borderWidth': 1
            }]
        }
    
    elif chart_type == 'correlation':
        analytics = get_group_analytics(group_id, start_date, end_date)
        if not analytics:
            return jsonify({'error': 'Нет данных'})
        
        data = {
            'labels': [s['student'].full_name for s in analytics['students']],
            'datasets': [{
                'label': 'Посещаемость (%)',
                'data': [s['attendance'] for s in analytics['students']],
                'yAxisID': 'y'
            }, {
                'label': 'Средний балл',
                'data': [s['avg_grade'] for s in analytics['students']],
                'yAxisID': 'y1'
            }]
        }
    
    else:
        return jsonify({'error': 'Неверный тип графика'})
    
    return jsonify(data)
