from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for
from flask_login import login_required, current_user
from models import db, Teacher
from datetime import datetime
import bcrypt

admin_bp = Blueprint('admin', __name__)


def is_admin():
    """Проверяет, является ли текущий пользователь администратором"""
    return current_user.is_authenticated and current_user.username == 'admin'


@admin_bp.route('/admin')
@login_required
def admin_panel():
    """Панель администратора"""
    if not is_admin():
        flash('Доступ запрещен', 'error')
        return redirect(url_for('dashboard'))
    
    users = Teacher.query.order_by(Teacher.username.asc()).all()
    return render_template('admin.html', users=users)


@admin_bp.route('/api/admin/users', methods=['GET'])
@login_required
def get_users():
    """Получить список всех пользователей"""
    if not is_admin():
        return jsonify({'error': 'Access denied'}), 403
    
    users = Teacher.query.order_by(Teacher.username.asc()).all()
    return jsonify([{
        'id': user.id,
        'username': user.username,
        'email': user.email,
        'created_at': user.created_at.isoformat() if user.created_at else None,
        'is_admin': user.username == 'admin'
    } for user in users])


@admin_bp.route('/api/admin/users', methods=['POST'])
@login_required
def create_user():
    """Создать нового пользователя"""
    if not is_admin():
        return jsonify({'error': 'Access denied'}), 403
    
    data = request.json
    username = data.get('username', '').strip()
    email = data.get('email', '').strip()
    password = data.get('password', '').strip()
    
    if not username or not email or not password:
        return jsonify({'error': 'Все поля обязательны'}), 400
    
    # Проверяем уникальность логина и email
    if Teacher.query.filter_by(username=username).first():
        return jsonify({'error': 'Пользователь с таким логином уже существует'}), 400
    
    if Teacher.query.filter_by(email=email).first():
        return jsonify({'error': 'Пользователь с таким email уже существует'}), 400
    
    # Создаем нового пользователя
    new_user = Teacher(username=username, email=email)
    new_user.set_password(password)
    
    db.session.add(new_user)
    db.session.commit()
    
    return jsonify({
        'status': 'success',
        'message': 'Пользователь успешно создан',
        'user': {
            'id': new_user.id,
            'username': new_user.username,
            'email': new_user.email,
            'created_at': new_user.created_at.isoformat()
        }
    })


@admin_bp.route('/api/admin/users/<int:user_id>/password', methods=['PUT'])
@login_required
def change_password(user_id):
    """Изменить пароль пользователя"""
    if not is_admin():
        return jsonify({'error': 'Access denied'}), 403
    
    data = request.json
    new_password = data.get('password', '').strip()
    
    if not new_password:
        return jsonify({'error': 'Пароль не может быть пустым'}), 400
    
    user = Teacher.query.get_or_404(user_id)
    
    # Не позволяем изменить пароль администратора через интерфейс
    if user.username == 'admin':
        return jsonify({'error': 'Пароль администратора нельзя изменить через интерфейс'}), 400
    
    user.set_password(new_password)
    db.session.commit()
    
    return jsonify({
        'status': 'success',
        'message': 'Пароль успешно изменен'
    })


@admin_bp.route('/api/admin/users/<int:user_id>', methods=['DELETE'])
@login_required
def delete_user(user_id):
    """Удалить пользователя"""
    if not is_admin():
        return jsonify({'error': 'Access denied'}), 403
    
    user = Teacher.query.get_or_404(user_id)
    
    # Не позволяем удалить администратора
    if user.username == 'admin':
        return jsonify({'error': 'Нельзя удалить учетную запись администратора'}), 400
    
    # Не позволяем удалить самого себя
    if user.id == current_user.id:
        return jsonify({'error': 'Нельзя удалить собственную учетную запись'}), 400
    
    db.session.delete(user)
    db.session.commit()
    
    return jsonify({
        'status': 'success',
        'message': 'Пользователь успешно удален'
    })



















































