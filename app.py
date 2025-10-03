from flask import Flask, render_template, redirect, url_for, jsonify, request, abort
from flask_login import LoginManager, login_required, current_user
from config import Config
from models import db, Teacher
from auth import auth_bp
from journal import journal_bp
from assignments import assignments_bp
from calendar_module import calendar_bp
from groups import groups_bp
from tasks import tasks_bp
from docs import docs_bp
import os
import hmac
import hashlib
import subprocess
from datetime import datetime, timedelta
from sqlalchemy import func, case

app = Flask(__name__)
app.config.from_object(Config)

db.init_app(app)
login_manager = LoginManager(app)

login_manager.login_view = 'auth.login'
login_manager.login_message = 'Пожалуйста, войдите в систему'
login_manager.login_message_category = 'info'


@login_manager.user_loader
def load_user(user_id):
    return Teacher.query.get(int(user_id))


app.register_blueprint(auth_bp)
app.register_blueprint(journal_bp)
app.register_blueprint(assignments_bp)
app.register_blueprint(calendar_bp)
app.register_blueprint(groups_bp)
app.register_blueprint(tasks_bp)
app.register_blueprint(docs_bp)


@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return redirect(url_for('auth.login'))


@app.route('/dashboard')
@login_required
def dashboard():
    from models import Group, Student, Assignment, Lesson

    groups_count = Group.query.filter_by(teacher_id=current_user.id).count()
    students_count = db.session.query(Student).join(Group).filter(
        Group.teacher_id == current_user.id
    ).count()
    assignments_count = Assignment.query.filter_by(teacher_id=current_user.id).count()
    lessons_count = Lesson.query.filter_by(teacher_id=current_user.id).count()

    unchecked = Assignment.query.filter_by(
        teacher_id=current_user.id,
        checked_at=None
    ).count()

    return render_template('dashboard.html',
                           groups=groups_count,
                           students=students_count,
                           assignments=assignments_count,
                           lessons=lessons_count,
                           unchecked=unchecked
                           )


@app.route('/api/analytics/overview')
@login_required
def analytics_overview():
    from models import Group, Student, Assignment, Attendance, Lesson

    last_week = datetime.now() - timedelta(days=7)

    attendance_rate = db.session.query(
        db.func.avg(db.case((Attendance.present == True, 100), else_=0))
    ).join(Lesson).filter(
        Lesson.teacher_id == current_user.id,
        Lesson.date >= last_week
    ).scalar() or 0

    avg_score = db.session.query(db.func.avg(Assignment.score)).filter(
        Assignment.teacher_id == current_user.id,
        Assignment.score != None
    ).scalar() or 0

    return jsonify({
        'attendance_rate': round(float(attendance_rate), 2),
        'average_score': round(float(avg_score), 2),
        'period': 'last_7_days'
    })


@app.route('/api/analytics/attendance-monthly')
@login_required
def analytics_attendance_monthly():
    from models import Attendance, Lesson
    # Последние 12 месяцев, включая текущий
    now = datetime.now()
    start_date = (now.replace(day=1) - timedelta(days=365)).replace(day=1)

    # SQLite strftime('%Y-%m', date)
    month_label = func.strftime('%Y-%m', Lesson.date)

    present_count = func.sum(case((Attendance.present == True, 1), else_=0))
    total_count = func.count(Attendance.id)
    absent_count = (total_count - present_count)

    rows = (
        db.session.query(
            month_label.label('month'),
            present_count.label('present'),
            absent_count.label('absent')
        )
        .join(Lesson, Attendance.lesson_id == Lesson.id)
        .filter(Lesson.teacher_id == current_user.id)
        .filter(Lesson.date >= start_date)
        .group_by('month')
        .order_by('month')
        .all()
    )

    # Сформировать последовательность месяцев за период, чтобы заполнить нули
    labels = []
    data_present = []
    data_absent = []

    # helper to iterate months
    def add_month(dt):
        if dt.month == 12:
            return dt.replace(year=dt.year + 1, month=1)
        return dt.replace(month=dt.month + 1)

    # map from month to counts
    data_map = {r.month: {'present': int(r.present or 0), 'absent': int(r.absent or 0)} for r in rows}

    cursor = start_date.replace(day=1)
    end_cursor = now.replace(day=1)
    # include up to and including current month
    while cursor <= end_cursor:
        key = cursor.strftime('%Y-%m')
        labels.append(key)
        counts = data_map.get(key, {'present': 0, 'absent': 0})
        data_present.append(counts['present'])
        data_absent.append(counts['absent'])
        cursor = add_month(cursor)

    return jsonify({
        'labels': labels,
        'present': data_present,
        'absent': data_absent
    })


@app.route('/api/analytics/attendance-monthly/group')
@login_required
def analytics_attendance_monthly_group():
    from models import Attendance, Lesson
    group_id = request.args.get('group_id', type=int)
    if not group_id:
        return jsonify({'error': 'group_id is required'}), 400

    now = datetime.now()
    start_date = (now.replace(day=1) - timedelta(days=365)).replace(day=1)

    month_label = func.strftime('%Y-%m', Lesson.date)
    present_count = func.sum(case((Attendance.present == True, 1), else_=0))
    total_count = func.count(Attendance.id)
    absent_count = (total_count - present_count)

    rows = (
        db.session.query(
            month_label.label('month'),
            present_count.label('present'),
            absent_count.label('absent')
        )
        .join(Lesson, Attendance.lesson_id == Lesson.id)
        .filter(Lesson.teacher_id == current_user.id)
        .filter(Lesson.group_id == group_id)
        .filter(Lesson.date >= start_date)
        .group_by('month')
        .order_by('month')
        .all()
    )

    labels = []
    data_present = []
    data_absent = []

    def add_month(dt):
        if dt.month == 12:
            return dt.replace(year=dt.year + 1, month=1)
        return dt.replace(month=dt.month + 1)

    data_map = {r.month: {'present': int(r.present or 0), 'absent': int(r.absent or 0)} for r in rows}

    cursor = start_date.replace(day=1)
    end_cursor = now.replace(day=1)
    while cursor <= end_cursor:
        key = cursor.strftime('%Y-%m')
        labels.append(key)
        counts = data_map.get(key, {'present': 0, 'absent': 0})
        data_present.append(counts['present'])
        data_absent.append(counts['absent'])
        cursor = add_month(cursor)

    return jsonify({'labels': labels, 'present': data_present, 'absent': data_absent})


@app.route('/api/analytics/scores-monthly/group')
@login_required
def analytics_scores_monthly_group():
    from models import Assignment, Student
    group_id = request.args.get('group_id', type=int)
    if not group_id:
        return jsonify({'error': 'group_id is required'}), 400

    now = datetime.now()
    start_date = (now.replace(day=1) - timedelta(days=365)).replace(day=1)

    # Связываем задания со студентами выбранной группы
    month_label = func.strftime('%Y-%m', Assignment.submitted_at)
    # Бинning по диапазонам (0-59 низкий, 60-74 средний, 75-89 хороший, 90-100 отличный, None — нет оценки)
    excellent = func.sum(case((Assignment.score >= 90, 1), else_=0))
    good = func.sum(case(((Assignment.score >= 75) & (Assignment.score < 90), 1), else_=0))
    average = func.sum(case(((Assignment.score >= 60) & (Assignment.score < 75), 1), else_=0))
    low = func.sum(case(((Assignment.score < 60) & (Assignment.score != None), 1), else_=0))
    no_score = func.sum(case((Assignment.score == None, 1), else_=0))

    rows = (
        db.session.query(
            month_label.label('month'),
            excellent.label('excellent'),
            good.label('good'),
            average.label('average'),
            low.label('low'),
            no_score.label('no_score')
        )
        .join(Student, Assignment.student_id == Student.id)
        .filter(Student.group_id == group_id)
        .filter(Assignment.teacher_id == current_user.id)
        .filter(Assignment.submitted_at >= start_date)
        .group_by('month')
        .order_by('month')
        .all()
    )

    labels = []
    series_excellent = []
    series_good = []
    series_average = []
    series_low = []
    series_no_score = []

    def add_month(dt):
        if dt.month == 12:
            return dt.replace(year=dt.year + 1, month=1)
        return dt.replace(month=dt.month + 1)

    data_map = {
        r.month: {
            'excellent': int(r.excellent or 0),
            'good': int(r.good or 0),
            'average': int(r.average or 0),
            'low': int(r.low or 0),
            'no_score': int(r.no_score or 0)
        } for r in rows
    }

    cursor = start_date.replace(day=1)
    end_cursor = now.replace(day=1)
    while cursor <= end_cursor:
        key = cursor.strftime('%Y-%m')
        labels.append(key)
        entry = data_map.get(key, None)
        series_excellent.append((entry or {}).get('excellent', 0))
        series_good.append((entry or {}).get('good', 0))
        series_average.append((entry or {}).get('average', 0))
        series_low.append((entry or {}).get('low', 0))
        series_no_score.append((entry or {}).get('no_score', 0))
        cursor = add_month(cursor)

    return jsonify({
        'labels': labels,
        'excellent': series_excellent,
        'good': series_good,
        'average': series_average,
        'low': series_low,
        'no_score': series_no_score
    })


@app.route('/api/analytics/scores-monthly')
@login_required
def analytics_scores_monthly_overall():
    from models import Assignment
    now = datetime.now()
    start_date = (now.replace(day=1) - timedelta(days=365)).replace(day=1)

    month_label = func.strftime('%Y-%m', Assignment.submitted_at)
    excellent = func.sum(case((Assignment.score >= 90, 1), else_=0))
    good = func.sum(case(((Assignment.score >= 75) & (Assignment.score < 90), 1), else_=0))
    average = func.sum(case(((Assignment.score >= 60) & (Assignment.score < 75), 1), else_=0))
    low = func.sum(case(((Assignment.score < 60) & (Assignment.score != None), 1), else_=0))
    no_score = func.sum(case((Assignment.score == None, 1), else_=0))

    rows = (
        db.session.query(
            month_label.label('month'),
            excellent.label('excellent'),
            good.label('good'),
            average.label('average'),
            low.label('low'),
            no_score.label('no_score')
        )
        .filter(Assignment.teacher_id == current_user.id)
        .filter(Assignment.submitted_at >= start_date)
        .group_by('month')
        .order_by('month')
        .all()
    )

    labels = []
    series_excellent = []
    series_good = []
    series_average = []
    series_low = []
    series_no_score = []

    def add_month(dt):
        if dt.month == 12:
            return dt.replace(year=dt.year + 1, month=1)
        return dt.replace(month=dt.month + 1)

    data_map = {
        r.month: {
            'excellent': int(r.excellent or 0),
            'good': int(r.good or 0),
            'average': int(r.average or 0),
            'low': int(r.low or 0),
            'no_score': int(r.no_score or 0)
        } for r in rows
    }

    cursor = start_date.replace(day=1)
    end_cursor = now.replace(day=1)
    while cursor <= end_cursor:
        key = cursor.strftime('%Y-%m')
        labels.append(key)
        entry = data_map.get(key, None)
        series_excellent.append((entry or {}).get('excellent', 0))
        series_good.append((entry or {}).get('good', 0))
        series_average.append((entry or {}).get('average', 0))
        series_low.append((entry or {}).get('low', 0))
        series_no_score.append((entry or {}).get('no_score', 0))
        cursor = add_month(cursor)

    return jsonify({
        'labels': labels,
        'excellent': series_excellent,
        'good': series_good,
        'average': series_average,
        'low': series_low,
        'no_score': series_no_score
    })


@app.route('/api/analytics/scores-by-group')
@login_required
def analytics_scores_by_group():
    from models import Assignment, Student, Group
    # Считаем по группам количество оценок, приведённых к 5-балльной шкале:
    # 5: score >= 90, 4: 75-89, 3: 60-74, 2: <60 (только у заданий с оценкой)
    five = func.sum(case((Assignment.score >= 90, 1), else_=0))
    four = func.sum(case(((Assignment.score >= 75) & (Assignment.score < 90), 1), else_=0))
    three = func.sum(case(((Assignment.score >= 60) & (Assignment.score < 75), 1), else_=0))
    two = func.sum(case(((Assignment.score < 60) & (Assignment.score != None), 1), else_=0))

    rows = (
        db.session.query(
            Group.name.label('group_name'),
            five.label('five'),
            four.label('four'),
            three.label('three'),
            two.label('two')
        )
        .join(Student, Student.group_id == Group.id)
        .join(Assignment, Assignment.student_id == Student.id)
        .filter(Assignment.teacher_id == current_user.id)
        .group_by(Group.name)
        .order_by(Group.name)
        .all()
    )

    labels = []
    fives = []
    fours = []
    threes = []
    twos = []

    for r in rows:
        labels.append(r.group_name)
        fives.append(int(r.five or 0))
        fours.append(int(r.four or 0))
        threes.append(int(r.three or 0))
        twos.append(int(r.two or 0))

    return jsonify({'labels': labels, 'five': fives, 'four': fours, 'three': threes, 'two': twos})


@app.route('/api/analytics/control-points/group')
@login_required
def analytics_control_points_group():
    """Возвращает данные контрольных точек для диаграммы успеваемости группы"""
    from models import ControlPoint, ControlPointScore, Student
    
    group_id = request.args.get('group_id', type=int)
    if not group_id:
        return jsonify({'error': 'group_id is required'}), 400

    # Получаем контрольные точки для группы
    control_points = ControlPoint.query.filter_by(
        group_id=group_id, 
        teacher_id=current_user.id
    ).order_by(ControlPoint.date.asc()).all()

    if not control_points:
        return jsonify({'labels': [], 'datasets': []})

    # Получаем все оценки для этих контрольных точек
    control_point_ids = [cp.id for cp in control_points]
    scores = db.session.query(ControlPointScore).join(
        Student, ControlPointScore.student_id == Student.id
    ).filter(
        Student.group_id == group_id,
        ControlPointScore.control_point_id.in_(control_point_ids)
    ).all()

    # Группируем оценки по контрольным точкам
    scores_by_cp = {}
    for score in scores:
        cp_id = score.control_point_id
        if cp_id not in scores_by_cp:
            scores_by_cp[cp_id] = []
        scores_by_cp[cp_id].append(score.points)

    # Формируем данные для линейчатой диаграммы с накоплением
    labels = []  # Названия контрольных точек (ось Y)
    excellent_data = []  # 90-100%
    good_data = []       # 75-89%
    average_data = []    # 60-74%
    low_data = []        # <60%
    no_score_data = []   # Без оценки
    
    for cp in control_points:
        # Название контрольной точки (дата + название)
        date_str = cp.date.strftime('%d.%m.%Y')
        label = f"{date_str} - {cp.title}"
        labels.append(label)
        
        # Получаем оценки для этой контрольной точки
        cp_scores = scores_by_cp.get(cp.id, [])
        
        # Подсчитываем количество студентов в каждой категории
        excellent = 0
        good = 0
        average = 0
        low = 0
        
        for score in cp_scores:
            # Нормализуем балл к шкале 0-100
            normalized_score = (score / cp.max_points) * 100 if cp.max_points > 0 else 0
            
            if normalized_score >= 90:
                excellent += 1
            elif normalized_score >= 75:
                good += 1
            elif normalized_score >= 60:
                average += 1
            else:
                low += 1
        
        # Получаем общее количество студентов в группе
        total_students = db.session.query(Student).filter_by(group_id=group_id).count()
        no_score = max(0, total_students - len(cp_scores))
        
        excellent_data.append(excellent)
        good_data.append(good)
        average_data.append(average)
        low_data.append(low)
        no_score_data.append(no_score)

    return jsonify({
        'labels': labels,
        'excellent': excellent_data,
        'good': good_data,
        'average': average_data,
        'low': low_data,
        'no_score': no_score_data,
        'control_points': [{
            'id': cp.id,
            'title': cp.title,
            'date': cp.date.isoformat(),
            'max_points': cp.max_points,
            'scores': scores_by_cp.get(cp.id, []),
            'total_scores': len(scores_by_cp.get(cp.id, []))
        } for cp in control_points]
    })


def ensure_startup_state():
    with app.app_context():
        db.create_all()

        if not Teacher.query.filter_by(username='admin').first():
            admin = Teacher(username='admin', email='admin@example.com')
            admin.set_password('admin123')
            db.session.add(admin)
            db.session.commit()

        os.makedirs('uploads', exist_ok=True)
        os.makedirs('static/exports', exist_ok=True)

        # Lightweight migration for missing columns in SQLite
        try:
            from sqlalchemy import text
            
            # Миграция таблицы group
            result = db.session.execute(text("PRAGMA table_info('group')")).all()
            column_names = {row[1] for row in result}
            
            # Добавляем недостающие колонки
            if 'color' not in column_names:
                db.session.execute(text("ALTER TABLE 'group' ADD COLUMN color VARCHAR(7)"))
            
            if 'course' not in column_names:
                db.session.execute(text("ALTER TABLE 'group' ADD COLUMN course VARCHAR(100)"))
                # Устанавливаем значение по умолчанию для существующих записей
                db.session.execute(text("UPDATE 'group' SET course = 'Не указан' WHERE course IS NULL"))
            
            if 'education_form' not in column_names:
                db.session.execute(text("ALTER TABLE 'group' ADD COLUMN education_form VARCHAR(50)"))
                # Устанавливаем значение по умолчанию для существующих записей
                db.session.execute(text("UPDATE 'group' SET education_form = 'очная' WHERE education_form IS NULL"))
            
            # Миграция таблицы attendance
            try:
                result = db.session.execute(text("PRAGMA table_info('attendance')")).all()
                column_names = {row[1] for row in result}
                
                if 'attendance_mark' not in column_names:
                    db.session.execute(text("ALTER TABLE 'attendance' ADD COLUMN attendance_mark VARCHAR(10)"))
            except Exception:
                pass  # Таблица может не существовать
            
            # Миграция таблицы assignment
            try:
                result = db.session.execute(text("PRAGMA table_info('assignment')")).all()
                column_names = {row[1] for row in result}
                
<<<<<<< HEAD
                if 'due_date' not in column_names:
                    db.session.execute(text("ALTER TABLE 'assignment' ADD COLUMN due_date DATE"))
                if 'subject' not in column_names:
                    db.session.execute(text("ALTER TABLE 'assignment' ADD COLUMN subject VARCHAR(200)"))
=======
                if 'classroom' not in column_names:
                    db.session.execute(text("ALTER TABLE 'lesson' ADD COLUMN classroom VARCHAR(50)"))
                if 'subject' not in column_names:
                    db.session.execute(text("ALTER TABLE 'lesson' ADD COLUMN subject VARCHAR(200)"))
>>>>>>> fb36d676c09ce68466962837aa881ee40451bc13
            except Exception:
                pass  # Таблица может не существовать
            
            # Миграция таблицы control_point
            try:
                result = db.session.execute(text("PRAGMA table_info('control_point')")).all()
                column_names = {row[1] for row in result}
                if 'subject' not in column_names:
                    db.session.execute(text("ALTER TABLE 'control_point' ADD COLUMN subject VARCHAR(200)"))
            except Exception:
                pass
            
            db.session.commit()
        except Exception:
            pass


@app.route('/api/analytics/lessons-timeline')
@login_required
def analytics_lessons_timeline():
    """Возвращает данные о занятиях для временного графика"""
    from models import Lesson
    
    period = request.args.get('period', 'month')  # day, week, month
    days_back = request.args.get('days', type=int)
    
    # Определяем период для анализа
    if period == 'day':
        days_back = days_back or 30  # последние 30 дней
    elif period == 'week':
        days_back = days_back or 84  # последние 12 недель
    else:  # month
        days_back = days_back or 365  # последние 12 месяцев
    
    start_date = datetime.now() - timedelta(days=days_back)
    
    # Получаем занятия за период
    lessons = Lesson.query.filter(
        Lesson.teacher_id == current_user.id,
        Lesson.date >= start_date
    ).order_by(Lesson.date.asc()).all()
    
    # Группируем по периодам
    period_counts = {}
    
    for lesson in lessons:
        if period == 'day':
            key = lesson.date.strftime('%Y-%m-%d')
        elif period == 'week':
            # Получаем номер недели
            year, week, _ = lesson.date.isocalendar()
            key = f"{year}-W{week:02d}"
        else:  # month
            key = lesson.date.strftime('%Y-%m')
        
        if key not in period_counts:
            period_counts[key] = 0
        period_counts[key] += 1
    
    # Создаем полный список периодов (включая пустые)
    all_periods = []
    current_date = start_date
    end_date = datetime.now()
    
    while current_date <= end_date:
        if period == 'day':
            key = current_date.strftime('%Y-%m-%d')
            label = current_date.strftime('%d.%m.%Y')
            current_date += timedelta(days=1)
        elif period == 'week':
            year, week, _ = current_date.isocalendar()
            key = f"{year}-W{week:02d}"
            # Понедельник этой недели
            monday = current_date - timedelta(days=current_date.weekday())
            # Воскресенье этой недели
            sunday = monday + timedelta(days=6)
            label = f"{monday.strftime('%d.%m.%Y')} - {sunday.strftime('%d.%m.%Y')}"
            current_date += timedelta(weeks=1)
        else:  # month
            key = current_date.strftime('%Y-%m')
            # Получаем название месяца на русском
            month_names = {
                1: 'Январь', 2: 'Февраль', 3: 'Март', 4: 'Апрель',
                5: 'Май', 6: 'Июнь', 7: 'Июль', 8: 'Август',
                9: 'Сентябрь', 10: 'Октябрь', 11: 'Ноябрь', 12: 'Декабрь'
            }
            month_name = month_names[current_date.month]
            label = f"{month_name} {current_date.year}"
            if current_date.month == 12:
                current_date = current_date.replace(year=current_date.year + 1, month=1)
            else:
                current_date = current_date.replace(month=current_date.month + 1)
        
        all_periods.append({
            'key': key,
            'label': label,
            'count': period_counts.get(key, 0)
        })
    
    # Ограничиваем количество точек для читаемости
    if period == 'day' and len(all_periods) > 30:
        all_periods = all_periods[-30:]
    elif period == 'week' and len(all_periods) > 12:
        all_periods = all_periods[-12:]
    elif period == 'month' and len(all_periods) > 12:
        all_periods = all_periods[-12:]
    
    labels = [p['label'] for p in all_periods]
    data = [p['count'] for p in all_periods]
    
    return jsonify({
        'labels': labels,
        'data': data,
        'period': period,
        'total_lessons': sum(data)
    })


@app.route('/github/webhook', methods=['POST'])
def github_webhook():
    secret = app.config.get('GITHUB_WEBHOOK_SECRET')
    if secret:
        signature = request.headers.get('X-Hub-Signature-256', '')
        body = request.get_data()
        mac = hmac.new(secret.encode('utf-8'), msg=body, digestmod=hashlib.sha256)
        expected = 'sha256=' + mac.hexdigest()
        if not hmac.compare_digest(signature, expected):
            return abort(403)

    event = request.headers.get('X-GitHub-Event', '')
    if event not in ('push', 'ping'):
        return jsonify({'status': 'ignored'})

    repo_path = app.config.get('REPO_PATH')
    try:
        subprocess.check_call(['git', '-C', repo_path, 'pull', '--ff-only'])
    except Exception as e:
        return jsonify({'status': 'git pull failed', 'error': str(e)}), 500

    reload_cmd = app.config.get('RELOAD_CMD')
    wsgi_file = app.config.get('WSGI_FILE_PATH')
    try:
        if reload_cmd:
            subprocess.check_call(reload_cmd.split())
        elif wsgi_file:
            os.utime(wsgi_file, None)
    except Exception as e:
        return jsonify({'status': 'reload failed', 'error': str(e)}), 500

    return jsonify({'status': 'ok'})


if __name__ == '__main__':
    ensure_startup_state()
    app.run(host='0.0.0.0', port=8080, debug=True, threaded=True)