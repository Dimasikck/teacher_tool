from flask import Blueprint, render_template, request, jsonify, send_file, abort
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from models import db, Assignment, Student, Group
from cloud_utils import CloudStorage
from ai_utils import AIAnalyzer
from datetime import datetime
import os

assignments_bp = Blueprint('assignments', __name__)
cloud = CloudStorage()
ai = AIAnalyzer()


@assignments_bp.route('/assignments')
@login_required
def assignments():
    groups = Group.query.filter_by(teacher_id=current_user.id).all()
    assignments = Assignment.query.filter_by(teacher_id=current_user.id).all()
    # Список папок из облака по группам (Mail.ru WebDAV / локальный fallback)
    cloud_folders = {}
    # Если WebDAV доступен — покажем корневые папки тоже
    try:
        root_items = cloud.list_root_folders()
    except Exception:
        root_items = []
    cloud_folders['/'] = root_items
    for g in groups:
        cloud_folders[g.name] = cloud.list_group_folders(g.name)

    return render_template('assignments.html', groups=groups, assignments=assignments, cloud_folders=cloud_folders)


@assignments_bp.route('/assignments/<int:assignment_id>')
@login_required
def assignment_detail(assignment_id):
    assignment = Assignment.query.get_or_404(assignment_id)
    if assignment.teacher_id != current_user.id:
        abort(403)
    student = Student.query.get(assignment.student_id)
    group = Group.query.get(student.group_id) if student else None
    return render_template('assignment_detail.html', assignment=assignment, student=student, group=group)


# Удалён API загрузки заданий: страница теперь управляет облачными папками


@assignments_bp.route('/api/assignments/check/<int:assignment_id>', methods=['POST'])
@login_required
def check_assignment(assignment_id):
    assignment = Assignment.query.get_or_404(assignment_id)
    data = request.json

    if data.get('use_ai'):
        submission_text = data.get('submission_text', '')
        requirements = data.get('requirements', '')

        ai_result = ai.analyze_text_assignment(submission_text, requirements)
        plagiarism = ai.check_plagiarism(submission_text)

        assignment.ai_analysis = f"""
        AI Оценка: {ai_result['score']}/100
        Обратная связь: {ai_result['feedback']}
        Уникальность: {plagiarism['uniqueness_score']}%
        Рекомендации: {', '.join(ai_result.get('suggestions', []))}
        """
        assignment.score = ai_result['score']
    else:
        assignment.score = data.get('score', 0)
        assignment.ai_analysis = data.get('comments', '')

    assignment.checked_at = datetime.utcnow()
    db.session.commit()

    return jsonify({
        'status': 'success',
        'score': assignment.score,
        'analysis': assignment.ai_analysis
    })


@assignments_bp.route('/api/assignments/submissions/<int:student_id>')
@login_required
def get_submissions(student_id):
    student = Student.query.get_or_404(student_id)
    group = Group.query.get(student.group_id)

    submissions = cloud.list_submissions(student.name, group.name)

    return jsonify({
        'student': student.name,
        'submissions': [{'name': s.name, 'path': s.path} for s in submissions]
    })


@assignments_bp.route('/api/assignments/batch-check', methods=['POST'])
@login_required
def batch_check():
    data = request.json
    assignment_ids = data.get('assignment_ids', [])
    use_ai = data.get('use_ai', False)

    results = []

    for aid in assignment_ids:
        assignment = Assignment.query.get(aid)
        if assignment and assignment.teacher_id == current_user.id:
            if use_ai and assignment.file_path:
                with open(assignment.file_path, 'r') as f:
                    content = f.read()

                if assignment.title.lower().endswith('.py'):
                    analysis = ai.analyze_code(content)
                else:
                    analysis = ai.analyze_text_assignment(content, "Стандартные требования")

                assignment.ai_analysis = str(analysis)
                assignment.score = analysis.get('score', 0) if isinstance(analysis, dict) else 70
                assignment.checked_at = datetime.utcnow()

                results.append({
                    'id': aid,
                    'score': assignment.score,
                    'status': 'checked'
                })

    db.session.commit()
    return jsonify({'results': results})


@assignments_bp.route('/api/assignments/stats')
@login_required
def assignment_stats():
    # Статистика по облачным папкам больше не отображается
    return jsonify([])


# WebDAV API: list / mkdir / rename / delete
@assignments_bp.route('/api/cloud/list')
@login_required
def api_cloud_list():
    group = request.args.get('group')
    subpath = request.args.get('path', '').strip('/')
    if not group:
        return jsonify({'error': 'group required'}), 400
    base = group
    if subpath:
        base = f"{group}/{subpath}"
    items = cloud.list_group_folders(base)
    return jsonify({'path': base, 'items': items})


@assignments_bp.route('/api/cloud/mkdir', methods=['POST'])
@login_required
def api_cloud_mkdir():
    data = request.json
    group = data.get('group')
    name = data.get('name')
    subpath = data.get('path', '').strip('/')
    if not group or not name:
        return jsonify({'error': 'group and name required'}), 400
    target = f"{group}/{subpath}/{name}" if subpath else f"{group}/{name}"
    try:
        cloud.mkdir(target)
    except Exception as e:
        print('mkdir error', e)
        return jsonify({'status': 'error'}), 500
    return jsonify({'status': 'ok'})


@assignments_bp.route('/api/cloud/rename', methods=['POST'])
@login_required
def api_cloud_rename():
    data = request.json
    src = data.get('src')  # relative from group root
    dst = data.get('dst')
    if not src or not dst:
        return jsonify({'error': 'src and dst required'}), 400
    ok = False
    if getattr(cloud, 'webdav', None):
        try:
            s = (Config.WEBDAV_ROOT_PATH.rstrip('/') + '/' + src).replace('//', '/')
            d = (Config.WEBDAV_ROOT_PATH.rstrip('/') + '/' + dst).replace('//', '/')
            cloud.webdav.move(s, d)
            ok = True
        except Exception as e:
            print('rename webdav error', e)
    if not ok:
        try:
            os.rename(os.path.join('uploads', src), os.path.join('uploads', dst))
            ok = True
        except Exception as e:
            print('rename local error', e)
    return jsonify({'status': 'ok' if ok else 'error'})


@assignments_bp.route('/api/cloud/delete', methods=['POST'])
@login_required
def api_cloud_delete():
    data = request.json
    target = data.get('target')
    if not target:
        return jsonify({'error': 'target required'}), 400
    ok = False
    if getattr(cloud, 'webdav', None):
        try:
            t = (Config.WEBDAV_ROOT_PATH.rstrip('/') + '/' + target).replace('//', '/')
            cloud.webdav.clean(t)
            ok = True
        except Exception as e:
            print('delete webdav error', e)
    if not ok:
        import shutil
        try:
            path = os.path.join('uploads', target)
            if os.path.isdir(path):
                shutil.rmtree(path)
            elif os.path.exists(path):
                os.remove(path)
            ok = True
        except Exception as e:
            print('delete local error', e)
    return jsonify({'status': 'ok' if ok else 'error'})


@assignments_bp.route('/api/cloud/upload', methods=['POST'])
@login_required
def api_cloud_upload():
    group = request.form.get('group')
    path = request.form.get('path', '').strip('/')
    file = request.files.get('file')
    if not group or not file:
        return jsonify({'error': 'group and file required'}), 400
    rel = f"{group}/{path}/{file.filename}" if path else f"{group}/{file.filename}"
    try:
        cloud.upload(rel, file)
        return jsonify({'status': 'ok'})
    except Exception as e:
        print('upload error', e)
        return jsonify({'status': 'error'}), 500


@assignments_bp.route('/api/cloud/download')
@login_required
def api_cloud_download():
    rel = request.args.get('target')
    if not rel:
        return jsonify({'error': 'target required'}), 400
    # Скачиваем во временный файл и отдаем
    tmp_dir = os.path.join('uploads', '__tmp_dl__')
    os.makedirs(tmp_dir, exist_ok=True)
    filename = rel.split('/')[-1]
    local_path = os.path.join(tmp_dir, filename)
    try:
        cloud.download(rel, local_path)
        return send_file(local_path, as_attachment=True, download_name=filename)
    except Exception as e:
        print('download error', e)
        return jsonify({'status': 'error'}), 500