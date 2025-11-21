"""
Миграция для создания таблиц conference_settings и conference
"""
import sqlite3
import os

def upgrade():
    """Создать таблицы conference_settings и conference"""
    db_path = os.path.join('instance', 'database.db')
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Таблица настроек видеоконференций
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS conference_settings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                teacher_id INTEGER NOT NULL,
                service_type VARCHAR(50) NOT NULL,
                organization_id VARCHAR(200),
                api_key TEXT,
                api_secret TEXT,
                account_id VARCHAR(200),
                client_id VARCHAR(200),
                client_secret VARCHAR(200),
                access_token TEXT,
                refresh_token TEXT,
                is_active BOOLEAN DEFAULT 0,
                last_sync DATETIME,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (teacher_id) REFERENCES teacher (id)
            )
        ''')
        
        # Таблица конференций
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS conference (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                teacher_id INTEGER NOT NULL,
                service_type VARCHAR(50) NOT NULL,
                title VARCHAR(200) NOT NULL,
                scheduled_time DATETIME,
                conference_url VARCHAR(500),
                conference_id VARCHAR(200),
                participants_count INTEGER DEFAULT 0,
                recording_url VARCHAR(500),
                status VARCHAR(50) DEFAULT 'scheduled',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (teacher_id) REFERENCES teacher (id)
            )
        ''')
        
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_conference_settings_teacher_id ON conference_settings (teacher_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_conference_settings_service ON conference_settings (service_type)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_conference_teacher_id ON conference (teacher_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_conference_service ON conference (service_type)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_conference_status ON conference (status)')
        
        conn.commit()
        print("SUCCESS: Tables conference_settings and conference created successfully")
        
    except Exception as e:
        print(f"ERROR: Failed to create tables: {e}")
        conn.rollback()
    finally:
        conn.close()

def downgrade():
    """Удалить таблицы"""
    db_path = os.path.join('instance', 'database.db')
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        cursor.execute('DROP TABLE IF EXISTS conference')
        cursor.execute('DROP TABLE IF EXISTS conference_settings')
        conn.commit()
        print("SUCCESS: Tables deleted")
    except Exception as e:
        print(f"ERROR: Failed to delete tables: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == '__main__':
    upgrade()

