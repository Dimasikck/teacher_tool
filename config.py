import os

# Опциональная загрузка .env файла
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    # dotenv не установлен, используем переменные окружения напрямую
    pass

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'sqlite:///database.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY') or 'jwt-secret-key'
    # Optional integrations. Provide via environment variables when available.
    YANDEX_TOKEN = os.environ.get('YANDEX_TOKEN') or ''
    OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY') or ''
    UPLOAD_FOLDER = 'uploads'
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024
    # WebDAV (Mail.ru Cloud) settings
    WEBDAV_URL = os.environ.get('WEBDAV_URL') or 'https://webdav.cloud.mail.ru'
    WEBDAV_LOGIN = os.environ.get('WEBDAV_LOGIN') or 'dmitriy.aleksandrovich.subbotin@mail.ru'
    WEBDAV_PASSWORD = os.environ.get('WEBDAV_PASSWORD') or 'UDfLpjHfnl9kkcfx3jdh'
    WEBDAV_ROOT_PATH = os.environ.get('WEBDAV_ROOT_PATH') or '/'

    # GitHub webhook / deployment settings (for PythonAnywhere)
    GITHUB_WEBHOOK_SECRET = os.environ.get('GITHUB_WEBHOOK_SECRET') or ''
    REPO_PATH = os.environ.get('REPO_PATH') or os.path.abspath('.')
    # Option 1: path to WSGI file to touch for reload
    WSGI_FILE_PATH = os.environ.get('WSGI_FILE_PATH') or ''
    # Option 2: explicit reload command (e.g., 'pa_reload_webapp.py <username>.pythonanywhere.com')
    RELOAD_CMD = os.environ.get('RELOAD_CMD') or ''