from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required, current_user
from models import db, Schedule, Group, Lesson
from ai_utils import AIAnalyzer
from datetime import datetime, timedelta
import json

calendar_bp = Blueprint('calendar', __name__)
ai = AIAnalyzer()


@calendar_bp.route('/calendar')
@login_required
def calendar():
    groups = Group.query.filter_by(teacher_id=current_user.id).all()
    return render_template('calendar.html', groups=groups)


@calendar_bp.route('/api/schedule/events')
@login_required
def get_events():
    try:
        start = request.args.get('start')
        end = request.args.get('end')

        print(f"DEBUG: Getting events for teacher {current_user.id}")
        print(f"DEBUG: Start: {start}, End: {end}")

        # Получаем все события для текущего преподавателя
        query = Schedule.query.filter_by(teacher_id=current_user.id)
        
        # Применяем фильтры по дате, если они переданы
        if start:
            try:
                start_date = datetime.fromisoformat(start.replace('Z', '+00:00'))
                query = query.filter(Schedule.start_time >= start_date)
                print(f"DEBUG: Filtered by start date: {start_date}")
            except ValueError as e:
                print(f"DEBUG: Error parsing start date: {e}")
                
        if end:
            try:
                end_date = datetime.fromisoformat(end.replace('Z', '+00:00'))
                query = query.filter(Schedule.end_time <= end_date)
                print(f"DEBUG: Filtered by end date: {end_date}")
            except ValueError as e:
                print(f"DEBUG: Error parsing end date: {e}")

        all_events = query.all()
        print(f"DEBUG: Found {len(all_events)} events in database")

        events = []
        for event in all_events:
            group = Group.query.get(event.group_id)
            
            # Получаем информацию об аудитории из соответствующего занятия
            lesson = Lesson.query.filter_by(
                group_id=event.group_id,
                teacher_id=current_user.id,
                topic=event.title
            ).first()
            
            classroom_info = ""
            if lesson and lesson.classroom:
                classroom_info = f" (Аудитория: {lesson.classroom})"
            
            event_data = {
                'id': event.id,
                'title': f"{event.title} - {group.name if group else 'Неизвестная группа'}{classroom_info}",
                'start': event.start_time.isoformat(),
                'end': event.end_time.isoformat(),
                'color': event.color or '#3788d8',
                'groupId': event.group_id,
                'classroom': lesson.classroom if lesson else ''
            }
            events.append(event_data)
            print(f"DEBUG: Event: {event_data}")

        print(f"DEBUG: Returning {len(events)} events")
        return jsonify(events)
        
    except Exception as e:
        print(f"DEBUG: Error in get_events: {e}")
        return jsonify({'error': str(e)}), 500


@calendar_bp.route('/api/schedule/all-events')
@login_required
def get_all_events():
    """Получить все события преподавателя для отладки"""
    try:
        events = Schedule.query.filter_by(teacher_id=current_user.id).all()
        print(f"DEBUG: Found {len(events)} total events for teacher {current_user.id}")
        
        result = []
        for event in events:
            group = Group.query.get(event.group_id)
            result.append({
                'id': event.id,
                'title': event.title,
                'start': event.start_time.isoformat(),
                'end': event.end_time.isoformat(),
                'color': event.color or '#3788d8',
                'group_id': event.group_id,
                'group_name': group.name if group else 'Неизвестная группа',
                'teacher_id': event.teacher_id
            })
        
        return jsonify({
            'total_events': len(result),
            'events': result
        })
        
    except Exception as e:
        print(f"DEBUG: Error in get_all_events: {e}")
        return jsonify({'error': str(e)}), 500


@calendar_bp.route('/api/schedule/create', methods=['POST'])
@login_required
def create_event():
    try:
        data = request.json
        
        if not data:
            return jsonify({'error': 'No data provided'}), 400
            
        # Валидация обязательных полей
        required_fields = ['title', 'start', 'end', 'group_id']
        for field in required_fields:
            if field not in data or not data[field]:
                return jsonify({'error': f'Field {field} is required'}), 400

        # Создаем событие в расписании
        event = Schedule(
            title=data['title'],
            start_time=datetime.fromisoformat(data['start']),
            end_time=datetime.fromisoformat(data['end']),
            group_id=data['group_id'],
            color=data.get('color', '#3788d8'),
            teacher_id=current_user.id
        )

        db.session.add(event)
        db.session.flush()  # Получаем ID события

        # Создаем соответствующее занятие в журнале
        lesson = Lesson(
            date=event.start_time,
            group_id=event.group_id,
            topic=event.title,
            notes=f"Занятие создано из календаря. Время: {event.start_time.strftime('%H:%M')} - {event.end_time.strftime('%H:%M')}",
            classroom=data.get('classroom', ''),
            teacher_id=current_user.id
        )
        db.session.add(lesson)
        db.session.commit()

        return jsonify({
            'id': event.id, 
            'lesson_id': lesson.id,
            'status': 'success',
            'message': 'Занятие успешно создано'
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@calendar_bp.route('/api/schedule/update/<int:event_id>', methods=['PUT'])
@login_required
def update_event(event_id):
    try:
        event = Schedule.query.get_or_404(event_id)

        if event.teacher_id != current_user.id:
            return jsonify({'error': 'Unauthorized'}), 403

        data = request.json
        
        # Обновляем событие в расписании
        if 'title' in data:
            event.title = data['title']
        if 'start' in data:
            event.start_time = datetime.fromisoformat(data['start'])
        if 'end' in data:
            event.end_time = datetime.fromisoformat(data['end'])
        if 'color' in data:
            event.color = data['color']

        # Обновляем соответствующее занятие в журнале
        lesson = Lesson.query.filter_by(
            group_id=event.group_id,
            teacher_id=current_user.id,
            topic=event.title
        ).first()
        
        if lesson:
            lesson.date = event.start_time
            lesson.topic = event.title
            lesson.notes = f"Занятие обновлено из календаря. Время: {event.start_time.strftime('%H:%M')} - {event.end_time.strftime('%H:%M')}"
            if 'classroom' in data:
                lesson.classroom = data['classroom']

        db.session.commit()
        return jsonify({'status': 'success', 'message': 'Занятие успешно обновлено'})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@calendar_bp.route('/api/schedule/delete/<int:event_id>', methods=['DELETE'])
@login_required
def delete_event(event_id):
    try:
        event = Schedule.query.get_or_404(event_id)

        if event.teacher_id != current_user.id:
            return jsonify({'error': 'Unauthorized'}), 403

        # Находим и удаляем соответствующее занятие в журнале
        lesson = Lesson.query.filter_by(
            group_id=event.group_id,
            teacher_id=current_user.id,
            topic=event.title
        ).first()
        
        if lesson:
            db.session.delete(lesson)

        # Удаляем событие из расписания
        db.session.delete(event)
        db.session.commit()
        
        return jsonify({'status': 'success', 'message': 'Занятие успешно удалено'})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@calendar_bp.route('/api/schedule/suggest-slot', methods=['POST'])
@login_required
def suggest_slot():
    data = request.json
    duration = data.get('duration', 90)
    preferred_days = data.get('preferred_days', ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday'])

    existing_events = Schedule.query.filter_by(teacher_id=current_user.id).all()

    schedule_data = [{
        'day': event.start_time.strftime('%A'),
        'start': event.start_time.strftime('%H:%M'),
        'end': event.end_time.strftime('%H:%M')
    } for event in existing_events]

    suggestion = ai.suggest_schedule_slot(schedule_data, duration)

    return jsonify(suggestion)


@calendar_bp.route('/api/schedule/optimize', methods=['POST'])
@login_required
def optimize_schedule():
    events = Schedule.query.filter_by(teacher_id=current_user.id).all()

    time_slots = []
    for hour in range(8, 20):
        for day in range(5):
            slot_start = datetime.now().replace(hour=hour, minute=0, second=0)
            slot_start += timedelta(days=day - datetime.now().weekday())

            is_free = True
            for event in events:
                if (event.start_time <= slot_start < event.end_time):
                    is_free = False
                    break

            if is_free:
                time_slots.append({
                    'day': slot_start.strftime('%A'),
                    'time': slot_start.strftime('%H:%M'),
                    'date': slot_start.isoformat()
                })

    return jsonify({'free_slots': time_slots[:10]})


@calendar_bp.route('/api/schedule/conflicts')
@login_required
def check_conflicts():
    events = Schedule.query.filter_by(teacher_id=current_user.id).order_by(Schedule.start_time).all()

    conflicts = []
    for i in range(len(events) - 1):
        if events[i].end_time > events[i + 1].start_time:
            conflicts.append({
                'event1': {'id': events[i].id, 'title': events[i].title},
                'event2': {'id': events[i + 1].id, 'title': events[i + 1].title},
                'overlap_minutes': (events[i].end_time - events[i + 1].start_time).seconds // 60
            })

    return jsonify({'conflicts': conflicts})