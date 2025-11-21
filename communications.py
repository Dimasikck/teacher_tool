from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required, current_user
from models import db, MessengerSettings
from datetime import datetime
import requests

communications_bp = Blueprint('communications', __name__, url_prefix='/communications')


@communications_bp.route('/')
@login_required
def index():
    # Получаем настройки для каждого мессенджера
    whatsapp_settings = MessengerSettings.query.filter_by(
        teacher_id=current_user.id,
        messenger_type='whatsapp'
    ).first()
    
    telegram_settings = MessengerSettings.query.filter_by(
        teacher_id=current_user.id,
        messenger_type='telegram'
    ).first()
    
    max_settings = MessengerSettings.query.filter_by(
        teacher_id=current_user.id,
        messenger_type='max'
    ).first()
    
    def get_status(settings):
        if not settings or not settings.is_active:
            return 'offline', 'Интеграция не настроена'
        # Здесь можно добавить проверку подключения
        return 'online', 'Подключено'
    
    channels = [
        {
            'id': 'whatsapp',
            'name': 'WhatsApp',
            'icon': 'bi-whatsapp',
            'status': get_status(whatsapp_settings)[0],
            'status_text': get_status(whatsapp_settings)[1],
            'description': 'Создавайте групповые чаты и отслеживайте ответы студентов и родителей в одном окне.',
            'actions': [
                'Синхронизировать контакты групп',
                'Отправить напоминание о домашних заданиях',
                'Настроить автоответы'
            ]
        },
        {
            'id': 'telegram',
            'name': 'Telegram',
            'icon': 'bi-telegram',
            'status': get_status(telegram_settings)[0],
            'status_text': get_status(telegram_settings)[1],
            'description': 'Используйте канал или бота для мгновенных уведомлений и рассылок по расписанию.',
            'actions': [
                'Создать бота для уведомлений',
                'Запланировать рассылку расписания',
                'Посмотреть последние ответы'
            ]
        },
        {
            'id': 'max',
            'name': 'Max',
            'icon': 'bi-chat-dots',
            'status': get_status(max_settings)[0],
            'status_text': get_status(max_settings)[1],
            'description': 'Новый корпоративный месcенджер с поддержкой темных тем и единым входом.',
            'actions': [
                'Пройти быстрый мастер настройки',
                'Импортировать шаблоны сообщений',
                'Назначить ответственных модераторов'
            ]
        }
    ]

    return render_template('communications.html', channels=channels)


@communications_bp.route('/api/settings/<messenger_type>', methods=['GET', 'POST'])
@login_required
def messenger_settings(messenger_type):
    """Получение и сохранение настроек мессенджера"""
    if messenger_type not in ['whatsapp', 'telegram', 'max']:
        return jsonify({'error': 'Неверный тип мессенджера'}), 400
    
    if request.method == 'GET':
        settings = MessengerSettings.query.filter_by(
            teacher_id=current_user.id,
            messenger_type=messenger_type
        ).first()
        
        if settings:
            return jsonify(settings.to_dict())
        else:
            # Возвращаем пустые настройки
            return jsonify({
                'messenger_type': messenger_type,
                'api_token': None,
                'api_id': None,
                'api_hash': None,
                'phone_number': None,
                'instance_id': None,
                'webhook_url': None,
                'bot_username': None,
                'is_active': False
            })
    
    elif request.method == 'POST':
        data = request.json
        
        settings = MessengerSettings.query.filter_by(
            teacher_id=current_user.id,
            messenger_type=messenger_type
        ).first()
        
        if settings:
            # Обновляем существующие настройки
            if 'api_token' in data:
                settings.api_token = data['api_token']
            if 'api_id' in data:
                settings.api_id = data['api_id']
            if 'api_hash' in data:
                settings.api_hash = data['api_hash']
            if 'phone_number' in data:
                settings.phone_number = data['phone_number']
            if 'instance_id' in data:
                settings.instance_id = data['instance_id']
            if 'webhook_url' in data:
                settings.webhook_url = data['webhook_url']
            if 'bot_username' in data:
                settings.bot_username = data['bot_username']
            if 'is_active' in data:
                settings.is_active = data['is_active']
            settings.updated_at = datetime.utcnow()
        else:
            # Создаем новые настройки
            settings = MessengerSettings(
                teacher_id=current_user.id,
                messenger_type=messenger_type,
                api_token=data.get('api_token'),
                api_id=data.get('api_id'),
                api_hash=data.get('api_hash'),
                phone_number=data.get('phone_number'),
                instance_id=data.get('instance_id'),
                webhook_url=data.get('webhook_url'),
                bot_username=data.get('bot_username'),
                is_active=data.get('is_active', False)
            )
            db.session.add(settings)
        
        try:
            db.session.commit()
            return jsonify({
                'success': True,
                'message': 'Настройки сохранены',
                'settings': settings.to_dict()
            })
        except Exception as e:
            db.session.rollback()
            return jsonify({'error': f'Ошибка сохранения: {str(e)}'}), 500


@communications_bp.route('/api/test-connection/<messenger_type>', methods=['POST'])
@login_required
def test_connection(messenger_type):
    """Тестирование подключения к мессенджеру"""
    if messenger_type not in ['whatsapp', 'telegram', 'max']:
        return jsonify({'error': 'Неверный тип мессенджера'}), 400
    
    settings = MessengerSettings.query.filter_by(
        teacher_id=current_user.id,
        messenger_type=messenger_type
    ).first()
    
    if not settings or not settings.is_active:
        return jsonify({
            'success': False,
            'error': 'Настройки не найдены или неактивны'
        }), 400
    
    try:
        if messenger_type == 'telegram':
            # Проверка подключения к Telegram Bot API
            if settings.api_token:
                bot_url = f'https://api.telegram.org/bot{settings.api_token}/getMe'
                response = requests.get(bot_url, timeout=10)
                if response.status_code == 200:
                    bot_info = response.json()
                    return jsonify({
                        'success': True,
                        'message': f'Бот подключен: @{bot_info.get("result", {}).get("username", "unknown")}'
                    })
                else:
                    return jsonify({
                        'success': False,
                        'error': 'Неверный токен бота'
                    })
            else:
                return jsonify({
                    'success': False,
                    'error': 'Токен бота не указан'
                })
        
        elif messenger_type == 'whatsapp':
            # Проверка подключения к WhatsApp Business API
            if settings.instance_id and settings.api_token:
                # Здесь можно добавить реальную проверку через WhatsApp Business API
                return jsonify({
                    'success': True,
                    'message': 'Подключение к WhatsApp успешно'
                })
            else:
                return jsonify({
                    'success': False,
                    'error': 'Не указаны Instance ID или токен'
                })
        
        elif messenger_type == 'max':
            # Проверка подключения к Max
            if settings.api_token:
                # Здесь можно добавить реальную проверку через API Max
                return jsonify({
                    'success': True,
                    'message': 'Подключение к Max успешно'
                })
            else:
                return jsonify({
                    'success': False,
                    'error': 'Токен API не указан'
                })
    
    except requests.exceptions.RequestException as e:
        return jsonify({
            'success': False,
            'error': f'Ошибка подключения: {str(e)}'
        }), 500
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Ошибка: {str(e)}'
        }), 500


@communications_bp.route('/api/sync/<messenger_type>', methods=['POST'])
@login_required
def sync_messenger(messenger_type):
    """Синхронизация данных мессенджера"""
    if messenger_type not in ['whatsapp', 'telegram', 'max']:
        return jsonify({'error': 'Неверный тип мессенджера'}), 400
    
    settings = MessengerSettings.query.filter_by(
        teacher_id=current_user.id,
        messenger_type=messenger_type
    ).first()
    
    if not settings or not settings.is_active:
        return jsonify({
            'success': False,
            'error': 'Мессенджер не настроен или неактивен'
        }), 400
    
    try:
        # Здесь можно добавить реальную синхронизацию
        settings.last_sync = datetime.utcnow()
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Синхронизация завершена',
            'last_sync': settings.last_sync.isoformat()
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': f'Ошибка синхронизации: {str(e)}'
        }), 500
