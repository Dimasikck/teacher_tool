from flask import Flask, render_template, redirect, url_for, jsonify, request, abort
from flask_login import LoginManager, login_required, current_user
from config import Config
from models import db, Teacher
from auth import auth_bp
from journal import journal_bp
from assignments import assignments_bp
from calendar_module import calendar_bp
from groups import groups_bp
import os
import hmac
import hashlib
import subprocess

app = Flask(__name__)
app.config.from_object(Config)

db.init_app(app)
login_manager = LoginManager(app)

login_manager.login_view = 'auth.login'
login_manager.login_message = 'Пожалуйста, войдите в систему'


@login_manager.user_loader
def load_user(user_id):
    return Teacher.query.get(int(user_id))


app.register_blueprint(auth_bp)
app.register_blueprint(journal_bp)
app.register_blueprint(assignments_bp)
app.register_blueprint(calendar_bp)
app.register_blueprint(groups_bp)


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
    from datetime import datetime, timedelta

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
            
            # Миграция таблицы lesson
            try:
                result = db.session.execute(text("PRAGMA table_info('lesson')")).all()
                column_names = {row[1] for row in result}
                
                if 'classroom' not in column_names:
                    db.session.execute(text("ALTER TABLE 'lesson' ADD COLUMN classroom VARCHAR(50)"))
            except Exception:
                pass  # Таблица может не существовать
            
            db.session.commit()
        except Exception:
            pass


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