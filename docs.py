from flask import Blueprint, render_template, request, jsonify, send_file, redirect, url_for, flash
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
import os
import mimetypes
from datetime import datetime
import json
import requests
from models import db, CloudSettings, CloudCategory

docs_bp = Blueprint('docs', __name__, url_prefix='/docs')

# Конфигурация для облачного хранилища
CLOUD_FOLDER = 'cloud_docs'
ALLOWED_EXTENSIONS = {
    'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif', 'doc', 'docx', 
    'xls', 'xlsx', 'ppt', 'pptx', 'zip', 'rar', 'mp4', 'mp3',
    'html', 'css', 'js', 'py', 'java', 'cpp', 'c', 'h'
}

# Mail Cloud API конфигурация
MAIL_CLOUD_API_BASE = 'https://cloud.mail.ru/api/v2'

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_file_icon(filename):
    """Возвращает иконку Bootstrap для типа файла"""
    ext = filename.rsplit('.', 1)[1].lower() if '.' in filename else ''
    icon_map = {
        'pdf': 'bi-file-earmark-pdf',
        'doc': 'bi-file-earmark-word',
        'docx': 'bi-file-earmark-word',
        'xls': 'bi-file-earmark-excel',
        'xlsx': 'bi-file-earmark-excel',
        'ppt': 'bi-file-earmark-ppt',
        'pptx': 'bi-file-earmark-ppt',
        'txt': 'bi-file-earmark-text',
        'jpg': 'bi-file-earmark-image',
        'jpeg': 'bi-file-earmark-image',
        'png': 'bi-file-earmark-image',
        'gif': 'bi-file-earmark-image',
        'mp4': 'bi-file-earmark-play',
        'mp3': 'bi-file-earmark-music',
        'zip': 'bi-file-earmark-zip',
        'rar': 'bi-file-earmark-zip',
        'html': 'bi-file-earmark-code',
        'css': 'bi-file-earmark-code',
        'js': 'bi-file-earmark-code',
        'py': 'bi-file-earmark-code',
        'java': 'bi-file-earmark-code',
        'cpp': 'bi-file-earmark-code',
        'c': 'bi-file-earmark-code',
        'h': 'bi-file-earmark-code'
    }
    return icon_map.get(ext, 'bi-file-earmark')

def format_file_size(size_bytes):
    """Форматирует размер файла в читаемый вид"""
    if size_bytes == 0:
        return "0 B"
    size_names = ["B", "KB", "MB", "GB"]
    i = 0
    while size_bytes >= 1024 and i < len(size_names) - 1:
        size_bytes /= 1024.0
        i += 1
    return f"{size_bytes:.1f} {size_names[i]}"

def get_file_info(filepath):
    """Получает информацию о файле"""
    if not os.path.exists(filepath):
        return None
    
    stat = os.stat(filepath)
    return {
        'name': os.path.basename(filepath),
        'size': stat.st_size,
        'size_formatted': format_file_size(stat.st_size),
        'modified': datetime.fromtimestamp(stat.st_mtime),
        'icon': get_file_icon(os.path.basename(filepath)),
        'type': mimetypes.guess_type(filepath)[0] or 'application/octet-stream'
    }

@docs_bp.route('/')
@login_required
def index():
    """Главная страница документации"""
    # Получаем настройки облака для текущего пользователя
    cloud_settings = CloudSettings.query.filter_by(teacher_id=current_user.id).first()
    categories = CloudCategory.query.filter_by(teacher_id=current_user.id, is_active=True).all()
    
    return render_template('docs.html', 
                         cloud_settings=cloud_settings, 
                         categories=categories)

@docs_bp.route('/upload', methods=['POST'])
@login_required
def upload_file():
    """Загрузка файла"""
    if 'file' not in request.files:
        return jsonify({'error': 'Файл не выбран'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'Файл не выбран'}), 400
    
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        
        # Создаем папку если не существует
        if not os.path.exists(CLOUD_FOLDER):
            os.makedirs(CLOUD_FOLDER)
        
        filepath = os.path.join(CLOUD_FOLDER, filename)
        
        # Если файл с таким именем уже существует, добавляем номер
        counter = 1
        original_filename = filename
        while os.path.exists(filepath):
            name, ext = os.path.splitext(original_filename)
            filename = f"{name}_{counter}{ext}"
            filepath = os.path.join(CLOUD_FOLDER, filename)
            counter += 1
        
        try:
            file.save(filepath)
            file_info = get_file_info(filepath)
            return jsonify({
                'success': True,
                'message': f'Файл "{filename}" успешно загружен',
                'file': file_info
            })
        except Exception as e:
            return jsonify({'error': f'Ошибка при сохранении файла: {str(e)}'}), 500
    else:
        return jsonify({'error': 'Недопустимый тип файла'}), 400

@docs_bp.route('/download/<filename>')
@login_required
def download_file(filename):
    """Скачивание файла"""
    filename = secure_filename(filename)
    filepath = os.path.join(CLOUD_FOLDER, filename)
    
    if not os.path.exists(filepath):
        flash('Файл не найден', 'error')
        return redirect(url_for('docs.index'))
    
    return send_file(filepath, as_attachment=True, download_name=filename)

@docs_bp.route('/view/<filename>')
@login_required
def view_file(filename):
    """Просмотр файла"""
    filename = secure_filename(filename)
    filepath = os.path.join(CLOUD_FOLDER, filename)
    
    if not os.path.exists(filepath):
        flash('Файл не найден', 'error')
        return redirect(url_for('docs.index'))
    
    mime_type, _ = mimetypes.guess_type(filepath)
    
    # Для текстовых файлов и изображений показываем в браузере
    if mime_type and (mime_type.startswith('text/') or mime_type.startswith('image/')):
        return send_file(filepath, mimetype=mime_type)
    
    # Для остальных файлов предлагаем скачать
    return send_file(filepath, as_attachment=True, download_name=filename)

@docs_bp.route('/delete/<filename>', methods=['POST'])
@login_required
def delete_file(filename):
    """Удаление файла"""
    filename = secure_filename(filename)
    filepath = os.path.join(CLOUD_FOLDER, filename)
    
    if not os.path.exists(filepath):
        return jsonify({'error': 'Файл не найден'}), 404
    
    try:
        os.remove(filepath)
        return jsonify({'success': True, 'message': f'Файл "{filename}" удален'})
    except Exception as e:
        return jsonify({'error': f'Ошибка при удалении файла: {str(e)}'}), 500

@docs_bp.route('/api/files')
@login_required
def api_files():
    """API для получения списка файлов"""
    files = []
    try:
        if os.path.exists(CLOUD_FOLDER):
            for filename in os.listdir(CLOUD_FOLDER):
                filepath = os.path.join(CLOUD_FOLDER, filename)
                if os.path.isfile(filepath):
                    file_info = get_file_info(filepath)
                    if file_info:
                        files.append(file_info)
        
        files.sort(key=lambda x: x['modified'], reverse=True)
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    
    return jsonify({'files': files})


# === НОВЫЕ API ДЛЯ ОБЛАЧНОГО ХРАНИЛИЩА ===

@docs_bp.route('/api/cloud/settings', methods=['GET', 'POST', 'PUT'])
@login_required
def cloud_settings():
    """Управление настройками облачного хранилища"""
    if request.method == 'GET':
        settings = CloudSettings.query.filter_by(teacher_id=current_user.id).first()
        if settings:
            return jsonify({
                'id': settings.id,
                'cloud_type': settings.cloud_type,
                'api_url': settings.api_url,
                'client_id': settings.client_id,
                'is_active': settings.is_active,
                'created_at': settings.created_at.isoformat()
            })
        return jsonify({'error': 'Настройки не найдены'}), 404
    
    elif request.method in ['POST', 'PUT']:
        data = request.json
        
        # Валидация обязательных полей
        required_fields = ['cloud_type', 'api_url', 'client_id', 'client_secret']
        for field in required_fields:
            if field not in data or not data[field]:
                return jsonify({'error': f'Поле {field} обязательно'}), 400
        
        # Ищем существующие настройки
        settings = CloudSettings.query.filter_by(teacher_id=current_user.id).first()
        
        if settings:
            # Обновляем существующие настройки
            settings.cloud_type = data['cloud_type']
            settings.api_url = data['api_url']
            settings.client_id = data['client_id']
            settings.client_secret = data['client_secret']
            settings.access_token = data.get('access_token', '')
            settings.refresh_token = data.get('refresh_token', '')
            settings.is_active = data.get('is_active', False)
            settings.updated_at = datetime.utcnow()
        else:
            # Создаем новые настройки
            settings = CloudSettings(
                teacher_id=current_user.id,
                cloud_type=data['cloud_type'],
                api_url=data['api_url'],
                client_id=data['client_id'],
                client_secret=data['client_secret'],
                access_token=data.get('access_token', ''),
                refresh_token=data.get('refresh_token', ''),
                is_active=data.get('is_active', False)
            )
            db.session.add(settings)
        
        try:
            db.session.commit()
            return jsonify({
                'success': True,
                'message': 'Настройки облака сохранены',
                'settings': {
                    'id': settings.id,
                    'cloud_type': settings.cloud_type,
                    'is_active': settings.is_active
                }
            })
        except Exception as e:
            db.session.rollback()
            return jsonify({'error': f'Ошибка сохранения: {str(e)}'}), 500


@docs_bp.route('/api/cloud/categories', methods=['GET', 'POST'])
@login_required
def cloud_categories():
    """Управление категориями облачного хранилища"""
    if request.method == 'GET':
        categories = CloudCategory.query.filter_by(teacher_id=current_user.id, is_active=True).all()
        return jsonify({
            'categories': [{
                'id': cat.id,
                'name': cat.name,
                'cloud_path': cat.cloud_path,
                'description': cat.description,
                'created_at': cat.created_at.isoformat()
            } for cat in categories]
        })
    
    elif request.method == 'POST':
        data = request.json
        
        # Валидация
        if not data.get('name') or not data.get('cloud_path'):
            return jsonify({'error': 'Название и путь к папке обязательны'}), 400
        
        # Проверяем, что категория с таким именем не существует
        existing = CloudCategory.query.filter_by(
            teacher_id=current_user.id, 
            name=data['name']
        ).first()
        
        if existing:
            return jsonify({'error': 'Категория с таким именем уже существует'}), 400
        
        # Создаем новую категорию
        category = CloudCategory(
            teacher_id=current_user.id,
            name=data['name'],
            cloud_path=data['cloud_path'],
            description=data.get('description', ''),
            is_active=True
        )
        
        try:
            db.session.add(category)
            db.session.commit()
            return jsonify({
                'success': True,
                'message': 'Категория создана',
                'category': {
                    'id': category.id,
                    'name': category.name,
                    'cloud_path': category.cloud_path
                }
            })
        except Exception as e:
            db.session.rollback()
            return jsonify({'error': f'Ошибка создания категории: {str(e)}'}), 500


@docs_bp.route('/api/cloud/categories/<int:category_id>', methods=['PUT', 'DELETE'])
@login_required
def cloud_category_detail(category_id):
    """Редактирование и удаление категории"""
    category = CloudCategory.query.filter_by(
        id=category_id, 
        teacher_id=current_user.id
    ).first()
    
    if not category:
        return jsonify({'error': 'Категория не найдена'}), 404
    
    if request.method == 'PUT':
        data = request.json
        
        if 'name' in data:
            category.name = data['name']
        if 'cloud_path' in data:
            category.cloud_path = data['cloud_path']
        if 'description' in data:
            category.description = data['description']
        
        try:
            db.session.commit()
            return jsonify({
                'success': True,
                'message': 'Категория обновлена'
            })
        except Exception as e:
            db.session.rollback()
            return jsonify({'error': f'Ошибка обновления: {str(e)}'}), 500
    
    elif request.method == 'DELETE':
        try:
            category.is_active = False
            db.session.commit()
            return jsonify({
                'success': True,
                'message': 'Категория удалена'
            })
        except Exception as e:
            db.session.rollback()
            return jsonify({'error': f'Ошибка удаления: {str(e)}'}), 500


@docs_bp.route('/api/cloud/files/<int:category_id>')
@login_required
def get_cloud_files(category_id):
    """Получение файлов из облачной папки"""
    category = CloudCategory.query.filter_by(
        id=category_id, 
        teacher_id=current_user.id,
        is_active=True
    ).first()
    
    if not category:
        return jsonify({'error': 'Категория не найдена'}), 404
    
    # Получаем настройки облака
    settings = CloudSettings.query.filter_by(
        teacher_id=current_user.id,
        is_active=True
    ).first()
    
    if not settings:
        return jsonify({'error': 'Настройки облака не найдены'}), 400
    
    try:
        # Здесь будет интеграция с Mail Cloud API
        # Пока возвращаем заглушку
        return jsonify({
            'files': [],
            'message': 'Интеграция с Mail Cloud API в разработке'
        })
    except Exception as e:
        return jsonify({'error': f'Ошибка получения файлов: {str(e)}'}), 500


@docs_bp.route('/api/cloud/upload/<int:category_id>', methods=['POST'])
@login_required
def upload_to_cloud(category_id):
    """Загрузка файла в облачную папку"""
    category = CloudCategory.query.filter_by(
        id=category_id, 
        teacher_id=current_user.id,
        is_active=True
    ).first()
    
    if not category:
        return jsonify({'error': 'Категория не найдена'}), 404
    
    if 'file' not in request.files:
        return jsonify({'error': 'Файл не выбран'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'Файл не выбран'}), 400
    
    if not allowed_file(file.filename):
        return jsonify({'error': 'Недопустимый тип файла'}), 400
    
    try:
        # Здесь будет загрузка в Mail Cloud
        # Пока возвращаем заглушку
        return jsonify({
            'success': True,
            'message': f'Файл {file.filename} загружен в категорию {category.name}',
            'file': {
                'name': file.filename,
                'size': len(file.read()),
                'category': category.name
            }
        })
    except Exception as e:
        return jsonify({'error': f'Ошибка загрузки: {str(e)}'}), 500
