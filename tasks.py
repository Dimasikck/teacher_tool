from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required, current_user
from models import db, TaskList, Task


tasks_bp = Blueprint('tasks', __name__, url_prefix='/tasks')


@tasks_bp.route('/')
@login_required
def board():
    lists = TaskList.query.filter_by(teacher_id=current_user.id).order_by(TaskList.position.asc()).all()
    # Build JSON-serializable structure for the template
    data = []
    for lst in lists:
        tasks = Task.query.filter_by(teacher_id=current_user.id, list_id=lst.id).order_by(Task.position.asc()).all()
        data.append({
            'list': {
                'id': lst.id,
                'name': lst.name,
                'position': lst.position,
            },
            'tasks': [
                {
                    'id': t.id,
                    'title': t.title,
                    'description': t.description,
                    'status': t.status,
                    'priority': t.priority,
                    'due_date': t.due_date.isoformat() if t.due_date else None,
                    'position': t.position,
                    'list_id': t.list_id,
                }
                for t in tasks
            ],
        })
    return render_template('tasks.html', lists=data)

# API endpoint for board data
@tasks_bp.route('/api/board')
@login_required
def api_board():
    lists = TaskList.query.filter_by(teacher_id=current_user.id).order_by(TaskList.position.asc()).all()
    data = []
    for lst in lists:
        tasks = Task.query.filter_by(teacher_id=current_user.id, list_id=lst.id).order_by(Task.position.asc()).all()
        data.append({
            'list': {
                'id': lst.id,
                'name': lst.name,
                'position': lst.position,
            },
            'tasks': [
                {
                    'id': t.id,
                    'title': t.title,
                    'description': t.description,
                    'status': t.status,
                    'priority': t.priority,
                    'due_date': t.due_date.isoformat() if t.due_date else None,
                    'position': t.position,
                    'list_id': t.list_id,
                }
                for t in tasks
            ],
        })
    return jsonify(data)


# API: create list
@tasks_bp.route('/api/lists', methods=['POST'])
@login_required
def create_list():
    payload = request.get_json(force=True)
    name = (payload.get('name') or '').strip() or 'Новый список'
    max_pos = db.session.query(db.func.coalesce(db.func.max(TaskList.position), 0)).filter_by(teacher_id=current_user.id).scalar()
    lst = TaskList(name=name, position=(max_pos + 1), teacher_id=current_user.id)
    db.session.add(lst)
    db.session.commit()
    return jsonify({'id': lst.id, 'name': lst.name, 'position': lst.position})


# API: rename list
@tasks_bp.route('/api/lists/<int:list_id>', methods=['PUT'])
@login_required
def rename_list(list_id):
    lst = TaskList.query.filter_by(id=list_id, teacher_id=current_user.id).first_or_404()
    payload = request.get_json(force=True)
    lst.name = (payload.get('name') or lst.name).strip()
    db.session.commit()
    return jsonify({'ok': True})


# API: delete list
@tasks_bp.route('/api/lists/<int:list_id>', methods=['DELETE'])
@login_required
def delete_list(list_id):
    lst = TaskList.query.filter_by(id=list_id, teacher_id=current_user.id).first_or_404()
    db.session.delete(lst)
    db.session.commit()
    return jsonify({'ok': True})


# API: reorder lists
@tasks_bp.route('/api/lists/reorder', methods=['POST'])
@login_required
def reorder_lists():
    order = request.get_json(force=True).get('order', [])
    for idx, list_id in enumerate(order):
        TaskList.query.filter_by(id=list_id, teacher_id=current_user.id).update({'position': idx})
    db.session.commit()
    return jsonify({'ok': True})


# API: create task
@tasks_bp.route('/api/tasks', methods=['POST'])
@login_required
def create_task():
    payload = request.get_json(force=True)
    title = (payload.get('title') or '').strip() or 'Новая задача'
    list_id = int(payload.get('list_id'))
    TaskList.query.filter_by(id=list_id, teacher_id=current_user.id).first_or_404()
    max_pos = db.session.query(db.func.coalesce(db.func.max(Task.position), 0)).filter_by(teacher_id=current_user.id, list_id=list_id).scalar()
    task = Task(
        title=title,
        description=(payload.get('description') or '').strip() or None,
        status=payload.get('status', 'new'),
        priority=payload.get('priority', 'low'),
        list_id=list_id,
        position=(max_pos + 1),
        teacher_id=current_user.id
    )
    db.session.add(task)
    db.session.commit()
    return jsonify({'id': task.id, 'title': task.title, 'position': task.position, 'list_id': task.list_id})


# API: get single task
@tasks_bp.route('/api/tasks/<int:task_id>', methods=['GET'])
@login_required
def get_task(task_id):
    task = Task.query.filter_by(id=task_id, teacher_id=current_user.id).first_or_404()
    return jsonify({
        'id': task.id,
        'title': task.title,
        'description': task.description,
        'status': task.status,
        'priority': task.priority,
        'due_date': task.due_date.isoformat() if task.due_date else None,
        'list_id': task.list_id,
        'position': task.position
    })

# API: update task
@tasks_bp.route('/api/tasks/<int:task_id>', methods=['PUT'])
@login_required
def update_task(task_id):
    task = Task.query.filter_by(id=task_id, teacher_id=current_user.id).first_or_404()
    payload = request.get_json(force=True)
    if 'title' in payload:
        task.title = (payload.get('title') or '').strip() or task.title
    if 'description' in payload:
        task.description = (payload.get('description') or '').strip() or None
    if 'status' in payload:
        task.status = payload.get('status', task.status)
    if 'priority' in payload:
        task.priority = payload.get('priority', 'low')
    if 'due_date' in payload:
        # Expect ISO format or empty
        from datetime import datetime
        value = (payload.get('due_date') or '').strip()
        task.due_date = datetime.fromisoformat(value) if value else None
    db.session.commit()
    return jsonify({'ok': True})


# API: delete task
@tasks_bp.route('/api/tasks/<int:task_id>', methods=['DELETE'])
@login_required
def delete_task(task_id):
    task = Task.query.filter_by(id=task_id, teacher_id=current_user.id).first_or_404()
    db.session.delete(task)
    db.session.commit()
    return jsonify({'ok': True})


# API: move task (drag and drop)
@tasks_bp.route('/api/tasks/<int:task_id>/move', methods=['POST'])
@login_required
def move_task(task_id):
    task = Task.query.filter_by(id=task_id, teacher_id=current_user.id).first_or_404()
    payload = request.get_json(force=True)
    new_list_id = int(payload.get('list_id'))
    new_position = int(payload.get('position', 0))

    # Ensure destination list exists and belongs to user
    TaskList.query.filter_by(id=new_list_id, teacher_id=current_user.id).first_or_404()

    # Shift positions in destination list for this user
    db.session.execute(
        db.text(
            """
            UPDATE task SET position = position + 1
            WHERE list_id = :list_id AND teacher_id = :teacher_id AND position >= :pos
            """
        ),
        {"list_id": new_list_id, "teacher_id": current_user.id, "pos": new_position}
    )

    # Move task
    task.list_id = new_list_id
    task.position = new_position
    db.session.commit()
    return jsonify({'ok': True})




