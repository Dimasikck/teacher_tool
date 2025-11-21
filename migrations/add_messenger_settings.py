"""
Миграция для создания таблицы messenger_settings
"""
import sqlite3
import os

def upgrade():
    """Создать таблицу messenger_settings"""
    db_path = os.path.join('instance', 'database.db')
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS messenger_settings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                teacher_id INTEGER NOT NULL,
                messenger_type VARCHAR(50) NOT NULL,
                api_token TEXT,
                api_id VARCHAR(200),
                api_hash VARCHAR(200),
                phone_number VARCHAR(50),
                instance_id VARCHAR(200),
                webhook_url VARCHAR(500),
                bot_username VARCHAR(200),
                is_active BOOLEAN DEFAULT 0,
                last_sync DATETIME,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (teacher_id) REFERENCES teacher (id)
            )
        ''')
        
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_messenger_teacher_id ON messenger_settings (teacher_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_messenger_type ON messenger_settings (messenger_type)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_messenger_active ON messenger_settings (is_active)')
        
        conn.commit()
        print("SUCCESS: Table messenger_settings created successfully")
        
    except Exception as e:
        print(f"ERROR: Failed to create table messenger_settings: {e}")
        conn.rollback()
    finally:
        conn.close()

def downgrade():
    """Удалить таблицу messenger_settings"""
    db_path = os.path.join('instance', 'database.db')
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        cursor.execute('DROP TABLE IF EXISTS messenger_settings')
        conn.commit()
        print("SUCCESS: Table messenger_settings deleted")
    except Exception as e:
        print(f"ERROR: Failed to delete table messenger_settings: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == '__main__':
    upgrade()


