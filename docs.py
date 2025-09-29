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

# Конфигурация для облачного хранилища
CLOUD_FOLDER = 'cloud_docs'
ALLOWED_EXTENSIONS = {
    'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif', 'doc', 'docx', 
    'xls', 'xlsx', 'ppt', 'pptx', 'zip', 'rar', 'mp4', 'mp3',
    'html', 'css', 'js', 'py', 'java', 'cpp', 'c', 'h'
}

# Mail Cloud API конфигурация
MAIL_CLOUD_API_BASE = 'https://cloud.mail.ru/api/v2'

# WebDAV client helper (uses api_url as hostname, client_id as login, client_secret as password, refresh_token as root path)
def _get_webdav_client(settings):
    try:
        from webdav3.client import Client as WebDavClient
    except Exception:
        return None, '/'
    hostname = (settings.api_url or '').rstrip('/')
    login = settings.client_id or ''
    password = settings.client_secret or ''
    # Для WebDAV используем автодетектируемый корень из сессии, по умолчанию '/'
    try:
        root_path = session.get('webdav_root') or '/'
    except Exception:
        root_path = '/'
    options = {
        'webdav_hostname': hostname,
        'webdav_login': login,
        'webdav_password': password,
        'disable_check': True,
    }
    try:
        return WebDavClient(options), (root_path or '/')
    except Exception:
        return None, (root_path or '/')


def _detect_webdav_root(client, login_hint: str = '') -> str:
    """Пытается обнаружить корневой путь WebDAV, возвращает строку с завершающим '/'."""
    candidates = [
        '/', '',
        '/dav', '/webdav', '/WebDAV',
        '/remote.php/dav', '/remote.php/webdav',
        '/remote.php/dav/files', '/remote.php/webdav/files',
        '/Documents', '/Документы',
        '/Shared', '/Общий', '/Общий доступ', '/Публичные',
        '/cloud', '/Cloud', '/drive', '/Drive', '/home', '/Home',
        '.',
    ]
    # Nextcloud/ownCloud user-specific
    if login_hint:
        candidates.insert(0, f"/remote.php/dav/files/{login_hint}")
        candidates.insert(1, f"/remote.php/webdav/{login_hint}")
    for base in candidates:
        b = base or '/'
        if not b.endswith('/'):
            b = b + '/'
        try:
            items = client.list(b)
            if isinstance(items, (list, tuple)) and len(items) > 0:
                return b
        except Exception:
            continue
    return '/'

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

def get_mail_cloud_files(settings, cloud_path):
    """Получение файлов из Mail.ru Cloud"""
    try:
        # Параметры запроса
        params = {
            'path': cloud_path,
            'limit': 1000
        }
        
        # Выполняем запрос с автоматическим обновлением токена
        response = make_mail_cloud_request(settings, 'GET', '/folder', params=params, timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            files = []
            
            if 'body' in data and 'list' in data['body']:
                for item in data['body']['list']:
                    if item.get('type') == 'file':
                        file_info = {
                            'name': item.get('name', ''),
                            'size': item.get('size', 0),
                            'size_formatted': format_file_size(item.get('size', 0)),
                            'modified': item.get('mtime', ''),
                            'icon': get_file_icon(item.get('name', '')),
                            'type': item.get('mime_type', 'application/octet-stream'),
                            'path': item.get('path', ''),
                            'download_url': item.get('download_url', '')
                        }
                        files.append(file_info)
            
            return jsonify({'files': files})
        else:
            return jsonify({
                'error': f'Ошибка API Mail.ru Cloud: {response.status_code}',
                'files': []
            })
            
    except requests.exceptions.RequestException as e:
        return jsonify({
            'error': f'Ошибка подключения к Mail.ru Cloud: {str(e)}',
            'files': []
        })
    except Exception as e:
        return jsonify({
            'error': f'Ошибка обработки ответа: {str(e)}',
            'files': []
        })

def refresh_mail_cloud_token(settings):
    """Обновление токена доступа Mail.ru Cloud"""
    try:
        # Параметры для обновления токена
        data = {
            'grant_type': 'refresh_token',
            'refresh_token': settings.refresh_token,
            'client_id': settings.client_id,
            'client_secret': settings.client_secret
        }
        
        # Запрос на обновление токена
        # Для Mail.ru используем официальный OAuth-хост
        token_endpoint = (
            'https://o2.mail.ru/token' if (settings.cloud_type == 'mail') else f"{settings.api_url.rstrip('/')}/token"
        )
        response = requests.post(token_endpoint, data=data, timeout=30)
        
        if response.status_code == 200:
            token_data = response.json()
            
            # Обновляем токены в базе данных
            settings.access_token = token_data.get('access_token', settings.access_token)
            settings.refresh_token = token_data.get('refresh_token', settings.refresh_token)
            settings.updated_at = datetime.utcnow()
            
            try:
                db.session.commit()
                return True
            except Exception as e:
                db.session.rollback()
                print(f"Ошибка сохранения токенов: {e}")
                return False
        else:
            print(f"Ошибка обновления токена: {response.status_code} {response.text}")
            return False
            
    except Exception as e:
        print(f"Ошибка при обновлении токена: {e}")
        return False

def make_mail_cloud_request(settings, method, endpoint, **kwargs):
    """Выполнение запроса к Mail.ru Cloud API с автоматическим обновлением токена"""
    headers = kwargs.get('headers', {})
    headers.update({
        'Authorization': f'Bearer {settings.access_token}',
        'Content-Type': 'application/json'
    })
    kwargs['headers'] = headers
    
    # Выполняем запрос
    response = requests.request(method, f"{settings.api_url}{endpoint}", **kwargs)
    
    # Если получили 403, пытаемся обновить токен
    if response.status_code == 403:
        print("Получен 403, пытаемся обновить токен...")
        if refresh_mail_cloud_token(settings):
            # Повторяем запрос с новым токеном
            headers['Authorization'] = f'Bearer {settings.access_token}'
            response = requests.request(method, f"{settings.api_url}{endpoint}", **kwargs)
        else:
            print("Не удалось обновить токен")
    
    return response

def create_mail_cloud_folder(settings, folder_name, parent_path):
    """Создание папки в Mail.ru Cloud"""
    try:
        # Формируем полный путь к новой папке
        if parent_path == '/':
            new_path = f'/{folder_name}'
        else:
            new_path = f"{parent_path.rstrip('/')}/{folder_name}"
        
        # Параметры для создания папки
        data = {
            'path': new_path
        }
        
        # Выполняем запрос с автоматическим обновлением токена
        response = make_mail_cloud_request(settings, 'POST', '/folder', json=data, timeout=30)
        
        if response.status_code in [200, 201]:
            return jsonify({
                'success': True,
                'message': f'Папка "{folder_name}" успешно создана в облаке',
                'path': new_path
            })
        else:
            return jsonify({
                'success': False,
                'error': f'Ошибка создания папки: {response.status_code}'
            })
            
    except requests.exceptions.RequestException as e:
        return jsonify({
            'success': False,
            'error': f'Ошибка подключения к Mail.ru Cloud: {str(e)}'
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Ошибка создания папки: {str(e)}'
        })

def get_mail_cloud_folders(settings, path: str = '/'):
    """Получение списка папок из Mail.ru Cloud для указанного пути (по умолчанию корень)."""
    try:
        # Параметры запроса
        params = {
            'path': path or '/',
            'limit': 1000
        }
        
        # Выполняем запрос с автоматическим обновлением токена
        response = make_mail_cloud_request(settings, 'GET', '/folder', params=params, timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            folders = []
            
            if 'body' in data and 'list' in data['body']:
                for item in data['body']['list']:
                    if item.get('type') == 'folder':
                        folder_info = {
                            'path': item.get('path', ''),
                            'name': item.get('name', ''),
                            'size': item.get('size', 0),
                            'modified': item.get('mtime', '')
                        }
                        folders.append(folder_info)
            
            # Добавляем элемент ".." для навигации вверх, если не в корне
            current = (path or '/').rstrip('/')
            if current and current != '/':
                parent = '/'
                trimmed = current.strip('/')
                if '/' in trimmed:
                    parent = '/' + '/'.join(trimmed.split('/')[:-1])
                    if not parent:
                        parent = '/'
                folders.insert(0, {
                    'path': parent,
                    'name': '..',
                    'size': 0,
                    'modified': ''
                })
            else:
                # Добавляем корневую папку как первый элемент для ясности
                folders.insert(0, {
                    'path': '/',
                    'name': 'Корневая папка',
                    'size': 0,
                    'modified': ''
                })
            
            return jsonify({'folders': folders})
        else:
            error_text = response.text
            print(f"Ошибка API Mail.ru Cloud: {response.status_code}")
            print(f"Ответ сервера: {error_text}")
            
            return jsonify({
                'error': f'Ошибка API Mail.ru Cloud: {response.status_code}. Проверьте настройки подключения и токены.',
                'folders': []
            })
            
    except requests.exceptions.RequestException as e:
        return jsonify({
            'error': f'Ошибка подключения к Mail.ru Cloud: {str(e)}',
            'folders': []
        })
    except Exception as e:
        return jsonify({
            'error': f'Ошибка обработки ответа: {str(e)}',
            'folders': []
        })

def upload_to_mail_cloud(settings, cloud_path, file_data, filename):
    """Загрузка файла в Mail.ru Cloud"""
    try:
        # Получаем URL для загрузки
        upload_url = f"{settings.api_url}/file/upload"
        headers = {
            'Authorization': f'Bearer {settings.access_token}'
        }
        
        # Параметры для загрузки
        params = {
            'path': f"{cloud_path}/{filename}",
            'overwrite': 'true'
        }
        
        # Запрос на получение URL для загрузки
        response = requests.get(upload_url, headers=headers, params=params, timeout=30)
        
        if response.status_code == 200:
            upload_data = response.json()
            upload_url = upload_data.get('body', {}).get('upload_url')
            
            if upload_url:
                # Загружаем файл
                files = {'file': (filename, file_data, 'application/octet-stream')}
                upload_response = requests.post(upload_url, files=files, timeout=60)
                
                if upload_response.status_code in [200, 201]:
                    return {
                        'success': True,
                        'message': f'Файл {filename} успешно загружен в облако'
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
            'error': f'Ошибка загрузки в облако: {str(e)}'
        }

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
            # Проверяем валидность токена для Mail.ru Cloud
            if settings.cloud_type == 'mail' and settings.is_active:
                try:
                    # Делаем тестовый запрос для проверки токена
                    test_response = make_mail_cloud_request(settings, 'GET', '/user', timeout=10)
                    if test_response.status_code == 200:
                        token_status = 'valid'
                    else:
                        token_status = 'invalid'
                except:
                    token_status = 'error'
            elif settings.cloud_type == 'webdav' and settings.is_active:
                try:
                    client, root_path = _get_webdav_client(settings)
                    if client:
                        # Автодетект корня и сохранение в сессию
                        detected = _detect_webdav_root(client, (settings.client_id or '').split('@')[0])
                        try:
                            session['webdav_root'] = detected
                        except Exception:
                            pass
                        token_status = 'valid'
                    else:
                        token_status = 'invalid'
                except Exception:
                    token_status = 'invalid'
            else:
                token_status = 'not_checked'
            
            return jsonify({
                'id': settings.id,
                'cloud_type': settings.cloud_type,
                'api_url': settings.api_url,
                'client_id': settings.client_id,
                'client_secret': settings.client_secret,
                'access_token': settings.access_token,
                'refresh_token': settings.refresh_token,
                'is_active': settings.is_active,
                'token_status': token_status,
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


@docs_bp.route('/api/cloud/categories/<int:category_id>', methods=['GET', 'PUT', 'DELETE'])
@login_required
def cloud_category_detail(category_id):
    """Получение, редактирование и удаление категории"""
    category = CloudCategory.query.filter_by(
        id=category_id, 
        teacher_id=current_user.id
    ).first()
    
    if not category:
        return jsonify({'error': 'Категория не найдена'}), 404
    
    if request.method == 'GET':
        return jsonify({
            'id': category.id,
            'name': category.name,
            'cloud_path': category.cloud_path,
            'description': category.description,
            'is_active': category.is_active,
            'created_at': category.created_at.isoformat()
        })
    
    elif request.method == 'PUT':
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
        if settings.cloud_type == 'mail':
            return get_mail_cloud_files(settings, category.cloud_path)
        elif settings.cloud_type == 'webdav':
            client, root_path = _get_webdav_client(settings)
            if not client:
                return jsonify({'error': 'Не удалось инициализировать WebDAV клиент', 'files': []})
            base = (root_path.rstrip('/') + '/' + category.cloud_path.strip('/')).replace('//', '/') if category.cloud_path != '/' else root_path
            items = client.list(base)
            files = []
            for href in items:
                if href == base or href.rstrip('/') == base.rstrip('/'):
                    continue
                if not href.endswith('/'):
                    name = href.rstrip('/').split('/')[-1]
                    files.append({
                        'name': name,
                        'size': 0,
                        'size_formatted': '—',
                        'modified': '',
                        'icon': get_file_icon(name),
                        'type': 'application/octet-stream',
                        # путь для файлов не используется для навигации, можно хранить относительный
                        'path': (category.cloud_path.rstrip('/') + '/' + name) if category.cloud_path != '/' else ('/' + name)
                    })
            return jsonify({'files': files})
        else:
            return jsonify({'files': [], 'message': f'Интеграция с {settings.cloud_type} в разработке'})
    except Exception as e:
        return jsonify({'error': f'Ошибка получения файлов: {str(e)}'}), 500


@docs_bp.route('/api/cloud/test-connection', methods=['POST'])
@login_required
def test_cloud_connection():
    """Тестирование подключения к облачному хранилищу"""
    data = request.json
    
    # Валидация обязательных полей
    required_fields = ['cloud_type', 'api_url', 'client_id', 'access_token']
    for field in required_fields:
        if field not in data or not data[field]:
            return jsonify({'error': f'Поле {field} обязательно для тестирования'}), 400
    
    try:
        if data['cloud_type'] == 'mail':
            # Создаем временный объект настроек для тестирования
            test_settings = type('obj', (object,), {
                'cloud_type': data['cloud_type'],
                'api_url': data['api_url'],
                'client_id': data['client_id'],
                'client_secret': data.get('client_secret', ''),
                'access_token': data['access_token'],
                'refresh_token': data.get('refresh_token', '')
            })
            
            # Тестируем подключение
            response = make_mail_cloud_request(test_settings, 'GET', '/user', timeout=10)
            
            if response.status_code == 200:
                user_data = response.json()
                return jsonify({
                    'success': True,
                    'message': f'Подключение успешно! Пользователь: {user_data.get("body", {}).get("email", "Неизвестно")}'
                })
            else:
                return jsonify({
                    'success': False,
                    'error': f'Ошибка подключения: {response.status_code}. Проверьте токены и настройки.'
                })
        else:
            return jsonify({
                'success': True,
                'message': f'Тестирование {data["cloud_type"]} не реализовано'
            })
            
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Ошибка тестирования: {str(e)}'
        })


@docs_bp.route('/api/cloud/create-folder', methods=['POST'])
@login_required
def create_cloud_folder():
    """Создание папки в облачном хранилище"""
    data = request.json
    
    if not data.get('folder_name') or not data.get('parent_path'):
        return jsonify({'error': 'Название папки и родительский путь обязательны'}), 400
    
    # Получаем настройки облака
    settings = CloudSettings.query.filter_by(
        teacher_id=current_user.id,
        is_active=True
    ).first()
    
    if not settings:
        return jsonify({'error': 'Настройки облака не найдены'}), 400
    
    try:
        if settings.cloud_type == 'mail':
            return create_mail_cloud_folder(settings, data['folder_name'], data['parent_path'])
        else:
            return jsonify({
                'success': True,
                'message': f'Папка {data["folder_name"]} создана (локально)'
            })
    except Exception as e:
        return jsonify({'error': f'Ошибка создания папки: {str(e)}'}), 500


@docs_bp.route('/api/cloud/folders')
@login_required
def get_cloud_folders():
    """Получение списка папок из облачного хранилища"""
    # Необязательный путь для навигации
    cloud_path = request.args.get('path', '/')
    # Получаем настройки облака
    settings = CloudSettings.query.filter_by(
        teacher_id=current_user.id,
        is_active=True
    ).first()
    
    if not settings:
        return jsonify({'error': 'Настройки облака не найдены'}), 400
    
    try:
        if settings.cloud_type == 'mail':
            return get_mail_cloud_folders(settings, cloud_path)
        elif settings.cloud_type == 'webdav':
            client, root_path = _get_webdav_client(settings)
            if not client:
                return jsonify({'error': 'Не удалось инициализировать WebDAV клиент', 'folders': []})
            # Обновляем root_path с автообнаруженным значением
            detected = _detect_webdav_root(client, (settings.client_id or '').split('@')[0])
            try:
                session['webdav_root'] = detected
            except Exception:
                pass
            base_root = detected or root_path
            base = (base_root.rstrip('/') + '/' + cloud_path.strip('/')).replace('//', '/') if cloud_path != '/' else base_root
            # Нормализуем: WebDAV часто ожидает завершающий '/'
            if not base.endswith('/'):
                base = base + '/'
            items = []
            try:
                items = client.list(base)
            except Exception:
                # Попробуем альтернативные варианты
                try:
                    alt_base = base.rstrip('/')
                    items = client.list(alt_base)
                    base = alt_base
                except Exception:
                    pass
            # Если пусто, пробуем автообнаружение корня
            if not items:
                detected = _detect_webdav_root(client, (settings.client_id or '').split('@')[0])
                if detected:
                    try:
                        session['webdav_root'] = detected
                    except Exception:
                        pass
                    base = (detected.rstrip('/') + '/' + cloud_path.strip('/')).replace('//', '/') if cloud_path != '/' else detected
                    if not base.endswith('/'):
                        base = base + '/'
                    try:
                        items = client.list(base)
                    except Exception:
                        items = []
            folders = []
            current = (cloud_path or '/').rstrip('/')
            if current and current != '/':
                trimmed = current.strip('/')
                parent = '/' if '/' not in trimmed else '/' + '/'.join(trimmed.split('/')[:-1])
                folders.append({'path': parent, 'name': '..', 'size': 0, 'modified': ''})
            else:
                folders.append({'path': '/', 'name': 'Корневая папка', 'size': 0, 'modified': ''})
            # WebDAV клиент может возвращать список строк или список словарей с ключом 'href'
            def extract_href(item):
                if isinstance(item, str):
                    return item
                if isinstance(item, dict):
                    return item.get('href') or item.get('path') or ''
                return ''
            for item in items or []:
                href = extract_href(item)
                if not href:
                    continue
                # Нормализуем
                href_norm = href if href.endswith('/') else href + '/'
                base_norm = base if base.endswith('/') else base + '/'
                if href_norm == base_norm:
                    continue
                if href_norm.endswith('/'):
                    name = href_norm.rstrip('/').split('/')[-1]
                    child_path = (cloud_path.rstrip('/') + '/' + name) if cloud_path != '/' else ('/' + name)
                    folders.append({'path': child_path, 'name': name, 'size': 0, 'modified': ''})
            return jsonify({'folders': folders})
        else:
            return jsonify({'folders': [], 'message': f'Интеграция с {settings.cloud_type} в разработке'})
    except Exception as e:
        return jsonify({'error': f'Ошибка получения папок: {str(e)}'}), 500


@docs_bp.route('/api/cloud/files-by-path')
@login_required
def api_cloud_files_by_path():
    """Получение списка файлов по произвольному пути в облаке"""
    cloud_path = request.args.get('path', '/')
    settings = CloudSettings.query.filter_by(
        teacher_id=current_user.id,
        is_active=True
    ).first()

    if not settings:
        return jsonify({'error': 'Настройки облака не найдены'}), 400

    try:
        if settings.cloud_type == 'mail':
            return get_mail_cloud_files(settings, cloud_path)
        elif settings.cloud_type == 'webdav':
            client, root_path = _get_webdav_client(settings)
            if not client:
                return jsonify({'error': 'Не удалось инициализировать WebDAV клиент', 'files': []})
            detected = _detect_webdav_root(client, (settings.client_id or '').split('@')[0])
            try:
                session['webdav_root'] = detected
            except Exception:
                pass
            base_root = detected or root_path
            base = (base_root.rstrip('/') + '/' + cloud_path.strip('/')).replace('//', '/') if cloud_path != '/' else base_root
            if not base.endswith('/'):
                base = base + '/'
            items = []
            try:
                items = client.list(base)
            except Exception:
                try:
                    alt_base = base.rstrip('/')
                    items = client.list(alt_base)
                    base = alt_base
                except Exception:
                    pass
            if not items:
                detected = _detect_webdav_root(client, (settings.client_id or '').split('@')[0])
                if detected:
                    try:
                        session['webdav_root'] = detected
                    except Exception:
                        pass
                    base = (detected.rstrip('/') + '/' + cloud_path.strip('/')).replace('//', '/') if cloud_path != '/' else detected
                    if not base.endswith('/'):
                        base = base + '/'
                    try:
                        items = client.list(base)
                    except Exception:
                        items = []
            files = []
            def extract_href(item):
                if isinstance(item, str):
                    return item
                if isinstance(item, dict):
                    return item.get('href') or item.get('path') or ''
                return ''
            for item in items or []:
                href = extract_href(item)
                if not href:
                    continue
                base_norm = base if base.endswith('/') else base + '/'
                if href == base or href.rstrip('/') == base.rstrip('/'):
                    continue
                is_dir = href.endswith('/')
                if not is_dir:
                    name = href.rstrip('/').split('/')[-1]
                    files.append({
                        'name': name,
                        'size': 0,
                        'size_formatted': '—',
                        'modified': '',
                        'icon': get_file_icon(name),
                        'type': 'application/octet-stream',
                        'path': (cloud_path.rstrip('/') + '/' + name) if cloud_path != '/' else ('/' + name)
                    })
            return jsonify({'files': files})
        else:
            return jsonify({'files': [], 'message': f'Интеграция с {settings.cloud_type} в разработке'})
    except Exception as e:
        return jsonify({'error': f'Ошибка получения файлов: {str(e)}'}), 500


@docs_bp.route('/api/cloud/diagnostics')
@login_required
def cloud_diagnostics():
    """Диагностика подключения и содержимого текущего пути"""
    cloud_path = request.args.get('path', '/')
    settings = CloudSettings.query.filter_by(
        teacher_id=current_user.id,
        is_active=True
    ).first()
    if not settings:
        return jsonify({'error': 'Настройки облака не найдены'}), 400

    result = {
        'cloud_type': settings.cloud_type,
        'path': cloud_path,
    }
    try:
        if settings.cloud_type == 'mail':
            params = {'path': cloud_path or '/', 'limit': 100}
            resp = make_mail_cloud_request(settings, 'GET', '/folder', params=params, timeout=15)
            result['status_code'] = resp.status_code
            try:
                result['raw'] = resp.json()
            except Exception:
                result['raw'] = resp.text
            return jsonify({'success': resp.ok, **result})
        elif settings.cloud_type == 'webdav':
            client, root_path = _get_webdav_client(settings)
            if not client:
                return jsonify({'success': False, 'error': 'WebDAV клиент не инициализирован', **result}), 400
            detected = _detect_webdav_root(client, (settings.client_id or '').split('@')[0])
            try:
                session['webdav_root'] = detected
            except Exception:
                pass
            base_root = detected or root_path
            base = (base_root.rstrip('/') + '/' + (cloud_path or '/').strip('/')).replace('//', '/') if (cloud_path or '/') != '/' else base_root
            if not base.endswith('/'):
                base = base + '/'
            tried = []
            def attempt(p):
                x = p if p.endswith('/') else p + '/'
                tried.append(x)
                return client.list(x)
            try:
                items = attempt(base)
            except Exception:
                # пробуем авто-корни
                detected = _detect_webdav_root(client, (settings.client_id or '').split('@')[0])
                try:
                    session['webdav_root'] = detected
                except Exception:
                    pass
                base = detected
                try:
                    items = attempt(base)
                except Exception:
                    # финальный fallback: hostname + '/'
                    items = []
            # если пусто, но без ошибок — пробуем ещё кандидаты
            if not items:
                detected = _detect_webdav_root(client, (settings.client_id or '').split('@')[0])
                if detected and detected != base:
                    base = detected
                    try:
                        items = attempt(base)
                    except Exception:
                        items = []
            result['base'] = base
            result['items'] = items
            result['tried'] = tried
            return jsonify({'success': True, **result})
        else:
            return jsonify({'success': False, 'error': f'Тип {settings.cloud_type} не поддержан', **result}), 400
    except Exception as e:
        return jsonify({'success': False, 'error': str(e), **result}), 500


# === OAuth-поток для автоматического получения токенов ===

@docs_bp.route('/api/cloud/oauth/start')
@login_required
def cloud_oauth_start():
    """Запуск OAuth авторизации для получения токенов без ручного ввода"""
    settings = CloudSettings.query.filter_by(teacher_id=current_user.id).first()
    if not settings or not settings.client_id or not settings.api_url:
        flash('Сначала заполните Client ID и API URL, затем повторите попытку', 'error')
        return redirect(url_for('docs.index'))

    # Генерируем состояние и сохраняем в сессии
    state = secrets.token_urlsafe(16)
    session['cloud_oauth_state'] = state

    # Redirect URI (должен быть зарегистрирован в приложении облака)
    redirect_uri = url_for('docs.cloud_oauth_callback', _external=True)

    # Адрес авторизации: для Mail.ru используем официальный OAuth-домен
    authorize_url = (
        'https://o2.mail.ru/authorize' if (settings.cloud_type == 'mail') else f"{settings.api_url.rstrip('/')}/authorize"
    )
    params = {
        'response_type': 'code',
        'client_id': settings.client_id,
        'redirect_uri': redirect_uri,
        'state': state,
        # Рекомендуемый scope для Mail.ru Cloud
        'scope': 'cloud'
    }
    return redirect(f"{authorize_url}?{urlencode(params)}")


@docs_bp.route('/api/cloud/oauth/callback')
@login_required
def cloud_oauth_callback():
    """Callback для получения access_token/refresh_token по коду авторизации"""
    code = request.args.get('code')
    state = request.args.get('state')

    expected_state = session.get('cloud_oauth_state')
    if not code or not state or state != expected_state:
        # Диагностика причин: чаще всего различие домена/порта/схемы и, как следствие, потеря cookie сессии
        print('[OAuth] Invalid code/state:', {
            'received_state': state,
            'expected_state': expected_state,
            'has_code': bool(code),
            'request_host': request.host_url,
        })
        flash('Некорректный ответ авторизации (code/state). Перезапускаем авторизацию...', 'error')
        # Пытаемся перезапустить авторизацию автоматически
        return redirect(url_for('docs.cloud_oauth_start'))

    # Очищаем state
    session.pop('cloud_oauth_state', None)

    settings = CloudSettings.query.filter_by(teacher_id=current_user.id).first()
    if not settings or not settings.client_id or not settings.client_secret or not settings.api_url:
        flash('Настройки клиента не найдены. Повторите попытку.', 'error')
        return redirect(url_for('docs.index'))

    token_url = (
        'https://o2.mail.ru/token' if (settings.cloud_type == 'mail') else f"{settings.api_url.rstrip('/')}/token"
    )
    redirect_uri = url_for('docs.cloud_oauth_callback', _external=True)

    data = {
        'grant_type': 'authorization_code',
        'code': code,
        'client_id': settings.client_id,
        'client_secret': settings.client_secret,
        'redirect_uri': redirect_uri,
    }

    try:
        resp = requests.post(token_url, data=data, timeout=30)
        if resp.status_code == 200:
            token_data = resp.json()
            settings.access_token = token_data.get('access_token', settings.access_token)
            settings.refresh_token = token_data.get('refresh_token', settings.refresh_token)
            settings.is_active = True
            settings.updated_at = datetime.utcnow()
            try:
                db.session.commit()
                flash('Токены получены и сохранены автоматически', 'success')
            except Exception as e:
                db.session.rollback()
                flash(f'Ошибка сохранения токенов: {str(e)}', 'error')
        else:
            try:
                err_text = resp.text
            except Exception:
                err_text = ''
            flash(f'Ошибка обмена кода на токен: {resp.status_code}. {err_text}', 'error')
    except Exception as e:
        flash(f'Ошибка запроса токена: {str(e)}', 'error')

    return redirect(url_for('docs.index'))


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
    
    # Получаем настройки облака
    settings = CloudSettings.query.filter_by(
        teacher_id=current_user.id,
        is_active=True
    ).first()
    
    if not settings:
        return jsonify({'error': 'Настройки облака не найдены'}), 400
    
    try:
        if settings.cloud_type == 'mail':
            # Читаем данные файла
            file_data = file.read()
            file.seek(0)  # Возвращаем указатель в начало
            
            result = upload_to_mail_cloud(settings, category.cloud_path, file_data, file.filename)
            
            if result['success']:
                return jsonify({
                    'success': True,
                    'message': result['message'],
                    'file': {
                        'name': file.filename,
                        'size': len(file_data),
                        'size_formatted': format_file_size(len(file_data)),
                        'category': category.name
                    }
                })
            else:
                return jsonify({'error': result['error']}), 500
        else:
            return jsonify({
                'success': True,
                'message': f'Файл {file.filename} загружен в категорию {category.name} (локально)',
                'file': {
                    'name': file.filename,
                    'size': len(file.read()),
                    'category': category.name
                }
            })
    except Exception as e:
        return jsonify({'error': f'Ошибка загрузки: {str(e)}'}), 500
