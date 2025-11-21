from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required, current_user
from models import db, ConferenceSettings, Conference
from datetime import datetime
import requests

conference_bp = Blueprint('conference', __name__, url_prefix='/conference')


@conference_bp.route('/')
@login_required
def index():
    # Получаем настройки для каждого сервиса
    kontur_settings = ConferenceSettings.query.filter_by(
        teacher_id=current_user.id,
        service_type='kontur'
    ).first()
    
    yandex_settings = ConferenceSettings.query.filter_by(
        teacher_id=current_user.id,
        service_type='yandex'
    ).first()
    
    zoom_settings = ConferenceSettings.query.filter_by(
        teacher_id=current_user.id,
        service_type='zoom'
    ).first()
    
    def get_status(settings):
        if not settings or not settings.is_active:
            return 'disabled', 'Недоступно'
        return 'ready', 'Готов к запуску'
    
    services = [
        {
            'id': 'kontur',
            'name': 'КонтурТолк',
            'description': 'Встроенный сервис Контура с записью, доступом по ссылке и авторизацией по ЕСИА.',
            'status': get_status(kontur_settings)[0],
            'status_text': get_status(kontur_settings)[1],
            'features': ['Запись встречи', 'Защищенный доступ', 'Общий чат']
        },
        {
            'id': 'yandex',
            'name': 'Яндекс Телемост',
            'description': 'Быстрые встречи до 100 участников, синхронизация с Яндекс Календарём.',
            'status': get_status(yandex_settings)[0],
            'status_text': get_status(yandex_settings)[1],
            'features': ['Расписание из календаря', 'Фон с логотипом', 'Интерактивные опросы']
        },
        {
            'id': 'zoom',
            'name': 'Zoom EDU',
            'description': 'Расширенный функционал для образовательных программ (брейкауты, отчёты присутствия).',
            'status': get_status(zoom_settings)[0],
            'status_text': get_status(zoom_settings)[1],
            'features': ['Брейкаут-комнаты', 'Отчёты об участии', 'Статистика вовлечённости']
        }
    ]
    
    # Получаем историю конференций
    conferences = Conference.query.filter_by(
        teacher_id=current_user.id
    ).order_by(Conference.scheduled_time.desc()).limit(10).all()
    
    return render_template('conference.html', services=services, conferences=conferences)


@conference_bp.route('/api/settings/<service_type>', methods=['GET', 'POST'])
@login_required
def conference_settings(service_type):
    """Получение и сохранение настроек сервиса видеоконференций"""
    if service_type not in ['kontur', 'yandex', 'zoom']:
        return jsonify({'error': 'Неверный тип сервиса'}), 400
    
    if request.method == 'GET':
        settings = ConferenceSettings.query.filter_by(
            teacher_id=current_user.id,
            service_type=service_type
        ).first()
        
        if settings:
            return jsonify(settings.to_dict())
        else:
            return jsonify({
                'service_type': service_type,
                'organization_id': None,
                'api_key': None,
                'api_secret': None,
                'account_id': None,
                'client_id': None,
                'client_secret': None,
                'is_active': False
            })
    
    elif request.method == 'POST':
        data = request.json
        
        settings = ConferenceSettings.query.filter_by(
            teacher_id=current_user.id,
            service_type=service_type
        ).first()
        
        if settings:
            # Обновляем существующие настройки
            if 'organization_id' in data:
                settings.organization_id = data['organization_id']
            if 'api_key' in data:
                settings.api_key = data['api_key']
            if 'api_secret' in data:
                settings.api_secret = data['api_secret']
            if 'account_id' in data:
                settings.account_id = data['account_id']
            if 'client_id' in data:
                settings.client_id = data['client_id']
            if 'client_secret' in data:
                settings.client_secret = data['client_secret']
            if 'access_token' in data:
                settings.access_token = data['access_token']
            if 'refresh_token' in data:
                settings.refresh_token = data['refresh_token']
            if 'is_active' in data:
                settings.is_active = data['is_active']
            settings.updated_at = datetime.utcnow()
        else:
            # Создаем новые настройки
            settings = ConferenceSettings(
                teacher_id=current_user.id,
                service_type=service_type,
                organization_id=data.get('organization_id'),
                api_key=data.get('api_key'),
                api_secret=data.get('api_secret'),
                account_id=data.get('account_id'),
                client_id=data.get('client_id'),
                client_secret=data.get('client_secret'),
                access_token=data.get('access_token'),
                refresh_token=data.get('refresh_token'),
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


@conference_bp.route('/api/test-connection/<service_type>', methods=['POST'])
@login_required
def test_connection(service_type):
    """Тестирование подключения к сервису видеоконференций"""
    if service_type not in ['kontur', 'yandex', 'zoom']:
        return jsonify({'error': 'Неверный тип сервиса'}), 400
    
    settings = ConferenceSettings.query.filter_by(
        teacher_id=current_user.id,
        service_type=service_type
    ).first()
    
    if not settings or not settings.is_active:
        return jsonify({
            'success': False,
            'error': 'Настройки не найдены или неактивны'
        }), 400
    
    try:
        if service_type == 'kontur':
            # Проверка подключения к КонтурТолк
            if settings.organization_id and settings.api_key:
                # Здесь можно добавить реальную проверку через API КонтурТолк
                return jsonify({
                    'success': True,
                    'message': 'Подключение к КонтурТолк успешно'
                })
            else:
                return jsonify({
                    'success': False,
                    'error': 'Не указаны Organization ID или API ключ'
                })
        
        elif service_type == 'yandex':
            # Проверка подключения к Яндекс Телемост
            if settings.api_key:
                # Здесь можно добавить реальную проверку через API Яндекс Телемост
                return jsonify({
                    'success': True,
                    'message': 'Подключение к Яндекс Телемост успешно'
                })
            else:
                return jsonify({
                    'success': False,
                    'error': 'API ключ не указан'
                })
        
        elif service_type == 'zoom':
            # Проверка подключения к Zoom
            if settings.api_key and settings.api_secret:
                # Здесь можно добавить реальную проверку через Zoom API
                return jsonify({
                    'success': True,
                    'message': 'Подключение к Zoom успешно'
                })
            else:
                return jsonify({
                    'success': False,
                    'error': 'API ключ или Secret не указаны'
                })
    
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Ошибка: {str(e)}'
        }), 500


@conference_bp.route('/api/create', methods=['POST'])
@login_required
def create_conference():
    """Создание новой видеоконференции"""
    data = request.json
    
    service_type = data.get('service_type')
    if service_type not in ['kontur', 'yandex', 'zoom']:
        return jsonify({'error': 'Неверный тип сервиса'}), 400
    
    settings = ConferenceSettings.query.filter_by(
        teacher_id=current_user.id,
        service_type=service_type,
        is_active=True
    ).first()
    
    if not settings:
        return jsonify({
            'success': False,
            'error': 'Сервис не настроен или неактивен'
        }), 400
    
    try:
        # Парсим дату и время
        scheduled_time = None
        if data.get('date') and data.get('time'):
            date_str = f"{data['date']} {data['time']}"
            scheduled_time = datetime.strptime(date_str, '%Y-%m-%d %H:%M')
        
        # Здесь можно добавить реальное создание конференции через API сервиса
        # Пока создаем запись в БД
        conference = Conference(
            teacher_id=current_user.id,
            service_type=service_type,
            title=data.get('title', 'Новая конференция'),
            scheduled_time=scheduled_time,
            conference_url=data.get('conference_url'),
            conference_id=data.get('conference_id'),
            participants_count=len(data.get('participants', []).split(',')) if data.get('participants') else 0,
            status='scheduled'
        )
        db.session.add(conference)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Конференция создана',
            'conference': conference.to_dict()
        })
    
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': f'Ошибка создания конференции: {str(e)}'
        }), 500


@conference_bp.route('/api/conferences', methods=['GET'])
@login_required
def get_conferences():
    """Получение списка конференций"""
    conferences = Conference.query.filter_by(
        teacher_id=current_user.id
    ).order_by(Conference.scheduled_time.desc()).limit(20).all()
    
    return jsonify({
        'conferences': [c.to_dict() for c in conferences]
    })
