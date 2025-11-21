from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required, current_user
from models import db, EmailSettings, Teacher
import imaplib
import smtplib
import email
from email.header import decode_header
from email.utils import parsedate_to_datetime, formataddr
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

mail_bp = Blueprint('mail', __name__, url_prefix='/mail')


def _get_email_settings():
    return EmailSettings.query.filter_by(teacher_id=current_user.id).first()


def _imap_connect(settings):
    if settings.imap_ssl:
        client = imaplib.IMAP4_SSL(settings.imap_host, settings.imap_port)
    else:
        client = imaplib.IMAP4(settings.imap_host, settings.imap_port)
    client.login(settings.username, settings.password)
    return client


def _smtp_send(settings, to_email, subject, body):
    msg = MIMEMultipart()
    msg["From"] = formataddr((current_user.username, settings.email))
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain", "utf-8"))

    if settings.smtp_ssl:
        server = smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port)
    else:
        server = smtplib.SMTP(settings.smtp_host, settings.smtp_port)
        server.starttls()

    server.login(settings.username, settings.password)
    server.send_message(msg)
    server.quit()


def _decode_header_value(value):
    if not value:
        return ""
    parts = decode_header(value)
    decoded = []
    for text, enc in parts:
        if isinstance(text, bytes):
            decoded.append(text.decode(enc or "utf-8", errors="ignore"))
        else:
            decoded.append(text)
    return "".join(decoded)


@mail_bp.route('/')
@login_required
def index():
    settings = _get_email_settings()
    teacher: Teacher = Teacher.query.get(current_user.id)

    if settings and settings.is_active:
        account_status = {
            'connected': True,
            'provider': settings.imap_host,
            'email': settings.email,
            'last_sync': 'Подключено',
            'quota': ''
        }
    else:
        account_status = {
            'connected': False,
            'provider': 'Не настроено',
            'email': teacher.email if teacher else '',
            'last_sync': 'Нет подключения',
            'quota': ''
        }

    return render_template('mail.html', account_status=account_status)


@mail_bp.route('/api/settings', methods=['GET', 'POST'])
@login_required
def mail_settings():
    if request.method == 'GET':
        settings = _get_email_settings()
        if not settings:
            teacher: Teacher = Teacher.query.get(current_user.id)
            return jsonify({
                'email': teacher.email if teacher else '',
                'username': teacher.email if teacher else '',
                'imap_host': 'imap.yandex.ru',
                'imap_port': 993,
                'imap_ssl': True,
                'smtp_host': 'smtp.yandex.ru',
                'smtp_port': 465,
                'smtp_ssl': True,
                'is_active': False
            })

        return jsonify({
            'email': settings.email,
            'username': settings.username,
            'imap_host': settings.imap_host,
            'imap_port': settings.imap_port,
            'imap_ssl': settings.imap_ssl,
            'smtp_host': settings.smtp_host,
            'smtp_port': settings.smtp_port,
            'smtp_ssl': settings.smtp_ssl,
            'is_active': settings.is_active
        })

    data = request.json or {}
    required = ['email', 'username', 'password', 'imap_host', 'smtp_host']
    for field in required:
        if not data.get(field):
            return jsonify({'error': f'Поле {field} обязательно'}), 400

    settings = _get_email_settings()
    if not settings:
        settings = EmailSettings(teacher_id=current_user.id)
        db.session.add(settings)

    settings.email = data['email']
    settings.username = data['username']
    settings.password = data['password']
    settings.imap_host = data.get('imap_host', 'imap.yandex.ru')
    settings.imap_port = int(data.get('imap_port', 993) or 993)
    settings.imap_ssl = bool(data.get('imap_ssl', True))
    settings.smtp_host = data.get('smtp_host', 'smtp.yandex.ru')
    settings.smtp_port = int(data.get('smtp_port', 465) or 465)
    settings.smtp_ssl = bool(data.get('smtp_ssl', True))
    settings.is_active = bool(data.get('is_active', True))

    try:
        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Ошибка сохранения настроек: {e}'}), 500


@mail_bp.route('/api/messages')
@login_required
def list_messages():
    settings = _get_email_settings()
    if not settings or not settings.is_active:
        return jsonify({'error': 'Почта не настроена'}), 400

    mailbox = request.args.get('mailbox', 'INBOX')
    limit = int(request.args.get('limit', 20))

    try:
        client = _imap_connect(settings)
        client.select(mailbox)
        typ, data = client.search(None, 'ALL')
        if typ != 'OK':
            client.logout()
            return jsonify({'error': 'Не удалось получить список писем'}), 500

        ids = data[0].split()
        ids = ids[-limit:]
        ids.reverse()

        messages = []
        for msg_id in ids:
            typ, msg_data = client.fetch(msg_id, '(RFC822)')
            if typ != 'OK':
                continue
            msg = email.message_from_bytes(msg_data[0][1])
            subject = _decode_header_value(msg.get('Subject'))
            sender = _decode_header_value(msg.get('From'))
            date = msg.get('Date')
            try:
                dt = parsedate_to_datetime(date) if date else None
                time_str = dt.strftime('%d.%m %H:%M') if dt else ''
            except Exception:
                time_str = date or ''

            snippet = ''
            if msg.is_multipart():
                for part in msg.walk():
                    if part.get_content_type() == 'text/plain':
                        try:
                            snippet = part.get_payload(decode=True).decode(
                                part.get_content_charset() or 'utf-8', errors='ignore'
                            )
                        except Exception:
                            snippet = ''
                        break
            else:
                try:
                    snippet = msg.get_payload(decode=True).decode(
                        msg.get_content_charset() or 'utf-8', errors='ignore'
                    )
                except Exception:
                    snippet = ''

            snippet = (snippet or '').replace('\r', ' ').replace('\n', ' ')
            if len(snippet) > 140:
                snippet = snippet[:137] + '...'

            messages.append({
                'id': msg_id.decode(),
                'subject': subject or '(без темы)',
                'sender': sender,
                'snippet': snippet,
                'time': time_str
            })

        client.logout()
        return jsonify({'messages': messages})
    except Exception as e:
        return jsonify({'error': f'Ошибка получения писем: {e}'}), 500


@mail_bp.route('/api/send', methods=['POST'])
@login_required
def send_message():
    settings = _get_email_settings()
    if not settings or not settings.is_active:
        return jsonify({'error': 'Почта не настроена'}), 400

    data = request.json or {}
    to_email = data.get('to')
    subject = data.get('subject', '')
    body = data.get('body', '')

    if not to_email:
        return jsonify({'error': 'Укажите получателя'}), 400

    try:
        _smtp_send(settings, to_email, subject, body)
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': f'Ошибка отправки письма: {e}'}), 500
