#!/usr/bin/env python3
"""
Мониторинг и автоматическая синхронизация между календарем и журналом
"""

from app import app
from models import db, Schedule, Lesson, Group, Teacher
from datetime import datetime

def check_and_sync():
    """Проверяет и синхронизирует занятия между календарем и журналом"""
    
    with app.app_context():
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Запуск проверки синхронизации...")
        
        teachers = Teacher.query.all()
        total_synced = 0
        
        for teacher in teachers:
            if teacher.username == 'admin':  # Пока только для admin
                print(f"Обработка преподавателя: {teacher.username}")
                
                # Получаем все события календаря
                calendar_events = Schedule.query.filter_by(teacher_id=teacher.id).all()
                journal_lessons = Lesson.query.filter_by(teacher_id=teacher.id).all()
                
                print(f"  Событий в календаре: {len(calendar_events)}")
                print(f"  Занятий в журнале: {len(journal_lessons)}")
                
                # Синхронизируем недостающие занятия
                synced_count = 0
                for event in calendar_events:
                    existing_lesson = Lesson.query.filter_by(
                        group_id=event.group_id,
                        teacher_id=teacher.id,
                        topic=event.title,
                        date=event.start_time
                    ).first()
                    
                    if not existing_lesson:
                        lesson = Lesson(
                            date=event.start_time,
                            group_id=event.group_id,
                            topic=event.title,
                            notes=f"Автосинхронизация из календаря. Время: {event.start_time.strftime('%H:%M')} - {event.end_time.strftime('%H:%M')}",
                            classroom=event.classroom,
                            teacher_id=teacher.id
                        )
                        db.session.add(lesson)
                        synced_count += 1
                
                if synced_count > 0:
                    db.session.commit()
                    print(f"  Синхронизировано занятий: {synced_count}")
                    total_synced += synced_count
                else:
                    print(f"  Все занятия уже синхронизированы")
        
        if total_synced > 0:
            print(f"Всего синхронизировано: {total_synced} занятий")
        else:
            print("Синхронизация не требуется")
        
        return total_synced

def get_sync_status():
    """Возвращает статус синхронизации"""
    
    with app.app_context():
        status = {
            'teachers': [],
            'total_calendar_events': 0,
            'total_journal_lessons': 0,
            'missing_lessons': 0
        }
        
        teachers = Teacher.query.all()
        
        for teacher in teachers:
            calendar_events = Schedule.query.filter_by(teacher_id=teacher.id).all()
            journal_lessons = Lesson.query.filter_by(teacher_id=teacher.id).all()
            
            missing_count = 0
            for event in calendar_events:
                existing_lesson = Lesson.query.filter_by(
                    group_id=event.group_id,
                    teacher_id=teacher.id,
                    topic=event.title,
                    date=event.start_time
                ).first()
                if not existing_lesson:
                    missing_count += 1
            
            teacher_status = {
                'id': teacher.id,
                'username': teacher.username,
                'calendar_events': len(calendar_events),
                'journal_lessons': len(journal_lessons),
                'missing_lessons': missing_count
            }
            
            status['teachers'].append(teacher_status)
            status['total_calendar_events'] += len(calendar_events)
            status['total_journal_lessons'] += len(journal_lessons)
            status['missing_lessons'] += missing_count
        
        return status

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == '--status':
        status = get_sync_status()
        print("=== СТАТУС СИНХРОНИЗАЦИИ ===")
        print(f"Всего событий в календаре: {status['total_calendar_events']}")
        print(f"Всего занятий в журнале: {status['total_journal_lessons']}")
        print(f"Недостающих занятий: {status['missing_lessons']}")
        
        for teacher in status['teachers']:
            if teacher['calendar_events'] > 0 or teacher['journal_lessons'] > 0:
                print(f"\nПреподаватель {teacher['username']}:")
                print(f"  Календарь: {teacher['calendar_events']}")
                print(f"  Журнал: {teacher['journal_lessons']}")
                print(f"  Недостает: {teacher['missing_lessons']}")
    else:
        synced = check_and_sync()
        if synced > 0:
            print(f"Синхронизация завершена. Создано {synced} занятий.")
        else:
            print("Синхронизация не требуется.")

