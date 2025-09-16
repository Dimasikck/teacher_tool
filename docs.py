from flask import Blueprint, render_template, request, jsonify, send_file, redirect, url_for, flash
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
import os
import mimetypes
from datetime import datetime
import json

docs_bp = Blueprint('docs', __name__, url_prefix='/docs')

# Конфигурация для облачного хранилища
CLOUD_FOLDER = 'cloud_docs'
ALLOWED_EXTENSIONS = {
    'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif', 'doc', 'docx', 
    'xls', 'xlsx', 'ppt', 'pptx', 'zip', 'rar', 'mp4', 'mp3',
    'html', 'css', 'js', 'py', 'java', 'cpp', 'c', 'h'
}

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
    # Создаем папку если не существует
    if not os.path.exists(CLOUD_FOLDER):
        os.makedirs(CLOUD_FOLDER)
    
    # Получаем список файлов
    files = []
    try:
        for filename in os.listdir(CLOUD_FOLDER):
            filepath = os.path.join(CLOUD_FOLDER, filename)
            if os.path.isfile(filepath):
                file_info = get_file_info(filepath)
                if file_info:
                    files.append(file_info)
        
        # Сортируем по дате изменения (новые сверху)
        files.sort(key=lambda x: x['modified'], reverse=True)
    except Exception as e:
        flash(f'Ошибка при загрузке файлов: {str(e)}', 'error')
        files = []
    
    return render_template('docs.html', files=files)

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
