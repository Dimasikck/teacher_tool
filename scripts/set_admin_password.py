#!/usr/bin/env python3
"""
Скрипт для установки пароля администратора с хешированием
Пароль хранится в зашифрованном виде с использованием bcrypt
"""

import os
import sys

# Ensure project root is on PYTHONPATH
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(CURRENT_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from app import app, db
from models import Teacher


def set_admin_password(username: str, new_password: str, email_fallback: str = "admin@example.com") -> None:
    """
    Устанавливает пароль для администратора с хешированием
    
    Args:
        username: Имя пользователя
        new_password: Новый пароль (будет захеширован)
        email_fallback: Email для создания пользователя, если не существует
    """
    with app.app_context():
        teacher = Teacher.query.filter_by(username=username).first()
        if not teacher:
            # Создаем пользователя, если не существует
            teacher = Teacher(username=username, email=email_fallback)
            db.session.add(teacher)
            print(f"✅ Создан новый пользователь: {username}")
        else:
            print(f"🔄 Обновление пароля для существующего пользователя: {username}")
        
        # Устанавливаем пароль (автоматически хешируется в модели)
        teacher.set_password(new_password)
        db.session.commit()
        
        # Проверяем, что пароль работает
        if teacher.check_password(new_password):
            print(f"✅ Пароль успешно установлен и проверен для '{username}'")
            print(f"🔐 Хеш пароля: {teacher.password_hash[:20]}...")
        else:
            print(f"❌ Ошибка: пароль не работает для '{username}'")


if __name__ == "__main__":
    print("🔧 Установка паролей администратора")
    print("=" * 50)
    
    # Устанавливаем пароль для основных административных аккаунтов
    set_admin_password(
        username="admin", 
        new_password="Dimasik0505", 
        email_fallback="admin@example.com"
    )
    
    set_admin_password(
        username="d.subbotin", 
        new_password="Dimasik0505", 
        email_fallback="dmitriy.aleksandrovich.subbotin@mail.ru"
    )
    
    print("=" * 50)
    print("✅ Все пароли установлены успешно!")
    print("🔒 Пароли хранятся в зашифрованном виде с использованием bcrypt")
    print("🌐 Теперь можно войти в систему по адресу: http://localhost:8080/login")


