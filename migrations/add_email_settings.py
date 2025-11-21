"""
Миграция для создания таблицы email_settings
"""
import sqlite3
import os


def upgrade():
    """Создать таблицу email_settings"""
    db_path = os.path.join('instance', 'database.db')
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS email_settings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                teacher_id INTEGER NOT NULL,
                email VARCHAR(200) NOT NULL,
                username VARCHAR(200) NOT NULL,
                password TEXT NOT NULL,
                imap_host VARCHAR(200) NOT NULL,
                imap_port INTEGER DEFAULT 993,
                imap_ssl BOOLEAN DEFAULT 1,
                smtp_host VARCHAR(200) NOT NULL,
                smtp_port INTEGER DEFAULT 465,
                smtp_ssl BOOLEAN DEFAULT 1,
                is_active BOOLEAN DEFAULT 0,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (teacher_id) REFERENCES teacher (id)
            )
            """
        )

        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_email_settings_teacher_id ON email_settings (teacher_id)"
        )

        conn.commit()
        print("SUCCESS: Table email_settings created successfully")
    except Exception as e:
        print(f"ERROR: Failed to create table email_settings: {e}")
        conn.rollback()
    finally:
        conn.close()


def downgrade():
    """Удалить таблицу email_settings"""
    db_path = os.path.join('instance', 'database.db')
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        cursor.execute("DROP TABLE IF EXISTS email_settings")
        conn.commit()
        print("SUCCESS: Table email_settings deleted")
    except Exception as e:
        print(f"ERROR: Failed to delete table email_settings: {e}")
        conn.rollback()
    finally:
        conn.close()


if __name__ == "__main__":
    upgrade()


