from flask import Blueprint, render_template, request, jsonify, send_file, redirect, url_for, flash, session
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
import os
import mimetypes
from datetime import datetime
import secrets
from urllib.parse import urlencode
import json
import requests
from models import db, CloudSettings, CloudCategory

docs_bp = Blueprint('docs', __name__, url_prefix='/docs')

# Yandex Disk API конфигурация
YANDEX_API_BASE = 'https://cloud-api.yandex.net/v1/disk'
YANDEX_OAUTH_BASE = 'https://oauth.yandex.ru'

def allowed_file(filename):
    """Проверяет, разрешен ли тип файла"""
    ALLOWED_EXTENSIONS = {
        'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif', 'doc', 'docx', 
        'xls', 'xlsx', 'ppt', 'pptx', 'zip', 'rar', 'mp4', 'mp3',
        'html', 'css', 'js', 'py', 'java', 'cpp', 'c', 'h', 'md'
    }
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
        'md': 'bi-file-earmark-text',
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

def make_yandex_request(settings, method, endpoint, **kwargs):
    """Выполнение запроса к Yandex Disk API"""
    headers = kwargs.get('headers', {})
    headers.update({
        'Authorization': f'OAuth {settings.access_token}',
        'Accept': 'application/json'
    })
    kwargs['headers'] = headers
    
    url = f"{YANDEX_API_BASE}{endpoint}"
    response = requests.request(method, url, **kwargs)
    
    return response

def get_yandex_files(settings, path='/'):
    """Получение списка файлов из Yandex Disk"""
    try:
        params = {
            'path': path,
            'limit': 1000
        }
        
        response = make_yandex_request(settings, 'GET', '/resources', params=params)
        
        if response.status_code == 200:
            data = response.json()
            files = []
            
            if '_embedded' in data and 'items' in data['_embedded']:
                for item in data['_embedded']['items']:
                    file_info = {
                        'name': item.get('name', ''),
                        'path': item.get('path', ''),
                        'type': 'dir' if item.get('type') == 'dir' else 'file',
                        'size': item.get('size', 0),
                        'size_formatted': format_file_size(item.get('size', 0)) if item.get('type') != 'dir' else '',
                        'modified': item.get('modified', ''),
                        'icon': get_file_icon(item.get('name', '')) if item.get('type') != 'dir' else 'bi-folder-fill',
                        'mime_type': item.get('mime_type', 'application/octet-stream')
                    }
                    files.append(file_info)
            
            return jsonify({'files': files})
        else:
            return jsonify({
                'error': f'Ошибка API Yandex Disk: {response.status_code}',
                'files': []
            })
            
    except requests.exceptions.RequestException as e:
        return jsonify({
            'error': f'Ошибка подключения к Yandex Disk: {str(e)}',
            'files': []
        })
    except Exception as e:
        return jsonify({
            'error': f'Ошибка обработки ответа: {str(e)}',
            'files': []
        })

def upload_to_yandex(settings, file_data, filename, path):
    """Загрузка файла в Yandex Disk"""
    try:
        # Получаем URL для загрузки
        upload_params = {
            'path': f"{path.rstrip('/')}/{filename}",
            'overwrite': 'true'
        }
        
        response = make_yandex_request(settings, 'GET', '/resources/upload', params=upload_params)
        
        if response.status_code == 200:
            upload_data = response.json()
            upload_url = upload_data.get('href')
            
            if upload_url:
                # Загружаем файл
                upload_response = requests.put(upload_url, data=file_data, timeout=60)
                
                if upload_response.status_code in [200, 201]:
                    return {
                        'success': True,
                        'message': f'Файл {filename} успешно загружен в Yandex Disk'
                    }
                else:
                    return {
                        'success': False,
                        'error': f'Ошибка загрузки файла: {upload_response.status_code}'
                    }
            else:
                return {
                    'success': False,
                    'error': 'Не удалось получить URL для загрузки'
                }
        else:
            return {
                'success': False,
                'error': f'Ошибка получения URL загрузки: {response.status_code}'
            }
            
    except Exception as e:
        return {
            'success': False,
            'error': f'Ошибка загрузки в Yandex Disk: {str(e)}'
        }

def download_from_yandex(settings, path):
    """Получение ссылки для скачивания файла из Yandex Disk"""
    try:
        params = {
            'path': path
        }
        
        response = make_yandex_request(settings, 'GET', '/resources/download', params=params)
        
        if response.status_code == 200:
            data = response.json()
            download_url = data.get('href')
            
            if download_url:
                # Получаем файл по ссылке
                file_response = requests.get(download_url, timeout=60)
                
                if file_response.status_code == 200:
                    return {
                        'success': True,
                        'content': file_response.content,
                        'content_type': file_response.headers.get('content-type', 'application/octet-stream')
                    }
                else:
                    return {
                        'success': False,
                        'error': f'Ошибка скачивания файла: {file_response.status_code}'
                    }
            else:
                return {
                    'success': False,
                    'error': 'Не удалось получить ссылку для скачивания'
                }
        else:
            return {
                'success': False,
                'error': f'Ошибка получения ссылки скачивания: {response.status_code}'
            }
            
    except Exception as e:
        return {
            'success': False,
            'error': f'Ошибка скачивания из Yandex Disk: {str(e)}'
        }

def delete_from_yandex(settings, path):
    """Удаление файла из Yandex Disk"""
    try:
        params = {
            'path': path,
            'permanently': 'true'
        }
        
        response = make_yandex_request(settings, 'DELETE', '/resources', params=params)
        
        if response.status_code in [200, 202, 204]:
            return {
                'success': True,
                'message': 'Файл успешно удален из Yandex Disk'
            }
        else:
            return {
                'success': False,
                'error': f'Ошибка удаления файла: {response.status_code}'
            }
            
    except Exception as e:
        return {
            'success': False,
            'error': f'Ошибка удаления из Yandex Disk: {str(e)}'
        }

@docs_bp.route('/')
@login_required
def index():
    """Главная страница документации"""
    return render_template('docs.html')

# === API ДЛЯ YANDEX DISK ===

@docs_bp.route('/api/yandex/settings', methods=['GET', 'POST'])
@login_required
def yandex_settings():
    """Управление настройками Yandex Disk"""
    if request.method == 'GET':
        settings = CloudSettings.query.filter_by(teacher_id=current_user.id).first()
        if settings:
            return jsonify({
                'id': settings.id,
                'client_id': settings.client_id,
                'client_secret': settings.client_secret,
                'access_token': settings.access_token,
                'is_active': settings.is_active,
                'created_at': settings.created_at.isoformat()
            })
        return jsonify({'error': 'Настройки не найдены'}), 404
    
    elif request.method == 'POST':
        data = request.json
        
        # Валидация обязательных полей
        required_fields = ['client_id', 'client_secret', 'access_token']
        for field in required_fields:
            if field not in data or not data[field]:
                return jsonify({'error': f'Поле {field} обязательно'}), 400
        
        # Ищем существующие настройки
        settings = CloudSettings.query.filter_by(teacher_id=current_user.id).first()
        
        if settings:
            # Обновляем существующие настройки
            settings.cloud_type = 'yandex'
            settings.api_url = YANDEX_API_BASE
            settings.client_id = data['client_id']
            settings.client_secret = data['client_secret']
            settings.access_token = data['access_token']
            settings.is_active = data.get('is_active', False)
            settings.updated_at = datetime.utcnow()
        else:
            # Создаем новые настройки
            settings = CloudSettings(
                teacher_id=current_user.id,
                cloud_type='yandex',
                api_url=YANDEX_API_BASE,
                client_id=data['client_id'],
                client_secret=data['client_secret'],
                access_token=data['access_token'],
                is_active=data.get('is_active', False)
            )
            db.session.add(settings)
        
        try:
            db.session.commit()
            return jsonify({
                'success': True,
                'message': 'Настройки Yandex Disk сохранены',
                'settings': {
                    'id': settings.id,
                    'cloud_type': settings.cloud_type,
                    'is_active': settings.is_active
                }
            })
        except Exception as e:
            db.session.rollback()
            return jsonify({'error': f'Ошибка сохранения: {str(e)}'}), 500

@docs_bp.route('/api/yandex/test-connection', methods=['POST'])
@login_required
def test_yandex_connection():
    """Тестирование подключения к Yandex Disk"""
    data = request.json
    
    # Валидация обязательных полей
    required_fields = ['client_id', 'client_secret', 'access_token']
    for field in required_fields:
        if field not in data or not data[field]:
            return jsonify({'error': f'Поле {field} обязательно для тестирования'}), 400
    
    try:
        access_token = data['access_token']
        
        # Проверяем, является ли введенное значение кодом подтверждения
        # Код подтверждения обычно короче токена доступа
        if len(access_token) < 50:  # Предполагаем, что это код подтверждения
            # Обмениваем код на токен
            token_data = {
                'grant_type': 'authorization_code',
                'code': access_token,
                'client_id': data['client_id'],
                'client_secret': data['client_secret']
            }
            
            try:
                response = requests.post(f'{YANDEX_OAUTH_BASE}/token', data=token_data, timeout=30)
                
                if response.status_code == 200:
                    token_response = response.json()
                    access_token = token_response.get('access_token')
                    
                    if not access_token:
                        return jsonify({
                            'success': False,
                            'error': 'Не удалось получить токен доступа из кода подтверждения'
                        })
                else:
                    return jsonify({
                        'success': False,
                        'error': f'Ошибка обмена кода на токен: {response.status_code}'
                    })
            except Exception as e:
                return jsonify({
                    'success': False,
                    'error': f'Ошибка обмена кода на токен: {str(e)}'
                })
        
        # Создаем временный объект настроек для тестирования
        test_settings = type('obj', (object,), {
            'cloud_type': 'yandex',
            'api_url': YANDEX_API_BASE,
            'client_id': data['client_id'],
            'client_secret': data['client_secret'],
            'access_token': access_token
        })
        
        # Тестируем подключение
        response = make_yandex_request(test_settings, 'GET', '/')
        
        if response.status_code == 200:
            user_data = response.json()
            return jsonify({
                'success': True,
                'message': f'Подключение успешно! Диск: {user_data.get("total_space", "Неизвестно")} байт',
                'access_token': access_token  # Возвращаем токен для сохранения
            })
        else:
            return jsonify({
                'success': False,
                'error': f'Ошибка подключения: {response.status_code}. Проверьте токен.'
            })
            
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Ошибка тестирования: {str(e)}'
        })

@docs_bp.route('/api/yandex/files')
@login_required
def get_yandex_files_api():
    """Получение списка файлов из Yandex Disk"""
    path = request.args.get('path', '/')
    
    # Получаем настройки
    settings = CloudSettings.query.filter_by(
        teacher_id=current_user.id,
        is_active=True
    ).first()
    
    if not settings:
        return jsonify({'error': 'Настройки Yandex Disk не найдены'}), 400
    
    return get_yandex_files(settings, path)

@docs_bp.route('/api/yandex/upload', methods=['POST'])
@login_required
def upload_to_yandex_api():
    """Загрузка файла в Yandex Disk"""
    if 'file' not in request.files:
        return jsonify({'error': 'Файл не выбран'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'Файл не выбран'}), 400
    
    if not allowed_file(file.filename):
        return jsonify({'error': 'Недопустимый тип файла'}), 400
    
    path = request.form.get('path', '/')
    
    # Получаем настройки
    settings = CloudSettings.query.filter_by(
        teacher_id=current_user.id,
        is_active=True
    ).first()
    
    if not settings:
        return jsonify({'error': 'Настройки Yandex Disk не найдены'}), 400
    
    try:
        # Читаем данные файла
        file_data = file.read()
        
        result = upload_to_yandex(settings, file_data, file.filename, path)
        
        if result['success']:
            return jsonify({
                'success': True,
                'message': result['message'],
                'file': {
                    'name': file.filename,
                    'size': len(file_data),
                    'size_formatted': format_file_size(len(file_data)),
                    'path': f"{path.rstrip('/')}/{file.filename}"
                }
            })
        else:
            return jsonify({'error': result['error']}), 500
    except Exception as e:
        return jsonify({'error': f'Ошибка загрузки: {str(e)}'}), 500

@docs_bp.route('/api/yandex/download')
@login_required
def download_from_yandex_api():
    """Скачивание файла из Yandex Disk"""
    path = request.args.get('path')
    
    if not path:
        return jsonify({'error': 'Путь к файлу не указан'}), 400
    
    # Получаем настройки
    settings = CloudSettings.query.filter_by(
        teacher_id=current_user.id,
        is_active=True
    ).first()
    
    if not settings:
        return jsonify({'error': 'Настройки Yandex Disk не найдены'}), 400
    
    try:
        result = download_from_yandex(settings, path)
        
        if result['success']:
            filename = path.split('/')[-1]
            return send_file(
                io.BytesIO(result['content']),
                as_attachment=True,
                download_name=filename,
                mimetype=result['content_type']
            )
        else:
            return jsonify({'error': result['error']}), 500
    except Exception as e:
        return jsonify({'error': f'Ошибка скачивания: {str(e)}'}), 500

@docs_bp.route('/api/yandex/view')
@login_required
def view_yandex_file():
    """Просмотр файла из Yandex Disk"""
    path = request.args.get('path')
    
    if not path:
        return jsonify({'error': 'Путь к файлу не указан'}), 400
    
    # Получаем настройки
    settings = CloudSettings.query.filter_by(
        teacher_id=current_user.id,
        is_active=True
    ).first()
    
    if not settings:
        return jsonify({'error': 'Настройки Yandex Disk не найдены'}), 400
    
    try:
        result = download_from_yandex(settings, path)
        
        if result['success']:
            content_type = result['content_type']
            content = result['content']
            
            # Для текстовых файлов декодируем содержимое
            if content_type.startswith('text/') or path.endswith('.txt') or path.endswith('.md'):
                try:
                    text_content = content.decode('utf-8')
                    return jsonify({
                        'success': True,
                        'content': text_content,
                        'type': content_type
                    })
                except UnicodeDecodeError:
                    return jsonify({
                        'success': True,
                        'content': 'Файл содержит нечитаемые символы',
                        'type': 'text/plain'
                    })
            # Для изображений возвращаем base64
            elif content_type.startswith('image/'):
                import base64
                base64_content = base64.b64encode(content).decode('utf-8')
                return jsonify({
                    'success': True,
                    'content': f"data:{content_type};base64,{base64_content}",
                    'type': content_type
                })
            else:
                return jsonify({
                    'success': False,
                    'error': 'Предварительный просмотр недоступен для данного типа файла'
                })
        else:
            return jsonify({'error': result['error']}), 500
    except Exception as e:
        return jsonify({'error': f'Ошибка просмотра файла: {str(e)}'}), 500

@docs_bp.route('/api/yandex/delete', methods=['POST'])
@login_required
def delete_from_yandex_api():
    """Удаление файла из Yandex Disk"""
    data = request.json
    path = data.get('path')
    
    if not path:
        return jsonify({'error': 'Путь к файлу не указан'}), 400
    
    # Получаем настройки
    settings = CloudSettings.query.filter_by(
        teacher_id=current_user.id,
        is_active=True
    ).first()
    
    if not settings:
        return jsonify({'error': 'Настройки Yandex Disk не найдены'}), 400
    
    try:
        result = delete_from_yandex(settings, path)
        
        if result['success']:
            return jsonify({
                'success': True,
                'message': result['message']
            })
        else:
            return jsonify({'error': result['error']}), 500
    except Exception as e:
        return jsonify({'error': f'Ошибка удаления: {str(e)}'}), 500

# === OAuth для Yandex ===

@docs_bp.route('/api/yandex/oauth/callback')
@login_required
def yandex_oauth_callback():
    """Callback для OAuth авторизации Yandex"""
    code = request.args.get('code')
    error = request.args.get('error')
    
    if error:
        flash(f'Ошибка авторизации: {error}', 'error')
        return redirect(url_for('docs.index'))
    
    if not code:
        flash('Код авторизации не получен', 'error')
        return redirect(url_for('docs.index'))
    
    # Получаем настройки пользователя
    settings = CloudSettings.query.filter_by(teacher_id=current_user.id).first()
    if not settings or not settings.client_id or not settings.client_secret:
        flash('Настройки клиента не найдены', 'error')
        return redirect(url_for('docs.index'))
    
    # Обмениваем код на токен
    token_data = {
        'grant_type': 'authorization_code',
        'code': code,
        'client_id': settings.client_id,
        'client_secret': settings.client_secret
    }
    
    try:
        response = requests.post(f'{YANDEX_OAUTH_BASE}/token', data=token_data, timeout=30)
        
        if response.status_code == 200:
            token_response = response.json()
            access_token = token_response.get('access_token')
            
            if access_token:
                # Обновляем настройки
                settings.access_token = access_token
                settings.is_active = True
                settings.updated_at = datetime.utcnow()
                
                try:
                    db.session.commit()
                    flash('Авторизация успешна! Токен сохранен.', 'success')
                except Exception as e:
                    db.session.rollback()
                    flash(f'Ошибка сохранения токена: {str(e)}', 'error')
            else:
                flash('Токен не получен в ответе', 'error')
        else:
            flash(f'Ошибка получения токена: {response.status_code}', 'error')
            
    except Exception as e:
        flash(f'Ошибка запроса токена: {str(e)}', 'error')
    
    return redirect(url_for('docs.index'))

# Добавляем импорт для BytesIO
import io