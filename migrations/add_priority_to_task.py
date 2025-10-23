#!/usr/bin/env python3
"""
Миграция для добавления поля priority в таблицу task
"""

import sqlite3
import os
import sys

def migrate_database():
    """Добавляет поле priority в таблицу task"""
    
    # Путь к базе данных
    db_path = os.path.join(os.path.dirname(__file__), '..', 'instance', 'database.db')
    
    if not os.path.exists(db_path):
        print("База данных не найдена!")
        return False
    
    try:
        # Подключаемся к базе данных
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Проверяем, существует ли уже поле priority
        cursor.execute("PRAGMA table_info(task)")
        columns = [column[1] for column in cursor.fetchall()]
        
        if 'priority' not in columns:
            print("Добавляем поле priority в таблицу task...")
            cursor.execute("ALTER TABLE task ADD COLUMN priority VARCHAR(10) DEFAULT 'low'")
            conn.commit()
            print("Поле priority успешно добавлено!")
        else:
            print("Поле priority уже существует в таблице task")
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"Ошибка при выполнении миграции: {e}")
        return False

if __name__ == "__main__":
    success = migrate_database()
    if success:
        print("Миграция выполнена успешно!")
    else:
        print("Ошибка выполнения миграции!")
        sys.exit(1)




























