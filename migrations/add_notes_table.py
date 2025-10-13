"""
Миграция для создания таблицы notes
"""
import sqlite3
import os

def upgrade():
    """Создать таблицу notes"""
    # Подключаемся к базе данных
    db_path = os.path.join('instance', 'database.db')
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Создаем таблицу notes
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS note (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                teacher_id INTEGER NOT NULL,
                title VARCHAR(200) NOT NULL,
                content TEXT NOT NULL,
                color VARCHAR(7) DEFAULT '#ffffff',
                is_pinned BOOLEAN DEFAULT 0,
                is_archived BOOLEAN DEFAULT 0,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (teacher_id) REFERENCES teacher (id)
            )
        ''')
        
        # Создаем индексы для оптимизации
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_note_teacher_id ON note (teacher_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_note_pinned ON note (is_pinned)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_note_archived ON note (is_archived)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_note_updated_at ON note (updated_at)')
        
        conn.commit()
        print("SUCCESS: Table notes created successfully")
        
    except Exception as e:
        print(f"ERROR: Failed to create table notes: {e}")
        conn.rollback()
    finally:
        conn.close()

def downgrade():
    """Удалить таблицу notes"""
    db_path = os.path.join('instance', 'database.db')
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        cursor.execute('DROP TABLE IF EXISTS note')
        conn.commit()
        print("SUCCESS: Table notes deleted")
    except Exception as e:
        print(f"ERROR: Failed to delete table notes: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == '__main__':
    upgrade()
