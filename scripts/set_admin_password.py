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
    with app.app_context():
        teacher = Teacher.query.filter_by(username=username).first()
        if not teacher:
            # create user if missing
            teacher = Teacher(username=username, email=email_fallback)
            db.session.add(teacher)
        teacher.set_password(new_password)
        db.session.commit()
        print(f"Password updated for '{username}'")


if __name__ == "__main__":
    # Update both common admin usernames
    set_admin_password(username="admin", new_password="Dimasik0505", email_fallback="admin@example.com")
    set_admin_password(username="d.subbotin", new_password="Dimasik0505", email_fallback="dmitriy.aleksandrovich.subbotin@mail.ru")


