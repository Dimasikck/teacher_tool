#!/usr/bin/env python3
"""Set or rotate admin password without hardcoded credentials."""

import argparse
import os
import secrets
import sys

# Ensure project root is on PYTHONPATH
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(CURRENT_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from app import app, db
from models import Teacher


def set_admin_password(username: str, new_password: str, email_fallback: str = 'admin@example.com') -> None:
    with app.app_context():
        teacher = Teacher.query.filter_by(username=username).first()
        if not teacher:
            teacher = Teacher(username=username, email=email_fallback)
            db.session.add(teacher)
            print(f"Created user: {username}")
        else:
            print(f"Updating password for user: {username}")

        teacher.set_password(new_password)
        db.session.commit()

        if teacher.check_password(new_password):
            print(f"Password updated successfully for '{username}'")
        else:
            print(f"Password verification failed for '{username}'")
            raise SystemExit(1)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Set or rotate admin password')
    parser.add_argument('--username', default=os.environ.get('ADMIN_USERNAME', 'admin'), help='Username')
    parser.add_argument('--email', default=os.environ.get('ADMIN_EMAIL', 'admin@example.com'), help='Email for new account')
    parser.add_argument('--password', default=os.environ.get('ADMIN_PASSWORD', ''), help='New password')
    parser.add_argument(
        '--generate',
        action='store_true',
        help='Generate a strong password automatically if --password is not provided',
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    password = args.password.strip()
    if not password:
        if args.generate:
            password = secrets.token_urlsafe(16)
            print('Generated password:')
            print(password)
        else:
            print('Password is required. Provide --password or ADMIN_PASSWORD, or use --generate.')
            raise SystemExit(2)

    set_admin_password(username=args.username, new_password=password, email_fallback=args.email)


if __name__ == '__main__':
    main()
