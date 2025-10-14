from flask import Blueprint, render_template, request, jsonify, redirect, url_for
from flask_login import login_required, current_user
from models import db, Note
from datetime import datetime
import json

notes_bp = Blueprint('notes', __name__)


@notes_bp.route('/notes/')
@login_required
def notes():
    """Главная страница заметок"""
    return render_template('notes.html')


@notes_bp.route('/api/notes/', methods=['GET'])
@login_required
def get_notes():
    """Получить все заметки пользователя"""
    try:
        # Получаем параметры фильтрации
        show_archived = request.args.get('show_archived', 'false').lower() == 'true'
        search_query = request.args.get('search', '').strip()
        
        # Базовый запрос
        query = Note.query.filter_by(teacher_id=current_user.id)
        
        # Фильтр по архивированным заметкам
        if not show_archived:
            query = query.filter_by(is_archived=False)
        
        # Поиск по заголовку и содержимому
        if search_query:
            query = query.filter(
                db.or_(
                    Note.title.contains(search_query),
                    Note.content.contains(search_query)
                )
            )
        
        # Сортируем: закрепленные сверху, затем по дате обновления
        notes = query.order_by(Note.is_pinned.desc(), Note.updated_at.desc()).all()
        
        return jsonify({
            'success': True,
            'notes': [note.to_dict() for note in notes]
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@notes_bp.route('/api/notes/', methods=['POST'])
@login_required
def create_note():
    """Создать новую заметку"""
    try:
        data = request.get_json()
        
        # Валидация данных
        if not data or not data.get('title') or not data.get('content'):
            return jsonify({
                'success': False,
                'error': 'Заголовок и содержимое обязательны'
            }), 400
        
        # Создаем заметку
        note = Note(
            teacher_id=current_user.id,
            title=data['title'].strip(),
            content=data['content'].strip(),
            color=data.get('color', '#ffffff'),
            is_pinned=data.get('is_pinned', False)
        )
        
        db.session.add(note)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'note': note.to_dict()
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@notes_bp.route('/api/notes/<int:note_id>', methods=['PUT'])
@login_required
def update_note(note_id):
    """Обновить заметку"""
    try:
        note = Note.query.filter_by(id=note_id, teacher_id=current_user.id).first()
        if not note:
            return jsonify({
                'success': False,
                'error': 'Заметка не найдена'
            }), 404
        
        data = request.get_json()
        
        # Обновляем поля
        if 'title' in data:
            note.title = data['title'].strip()
        if 'content' in data:
            note.content = data['content'].strip()
        if 'color' in data:
            note.color = data['color']
        if 'is_pinned' in data:
            note.is_pinned = data['is_pinned']
        if 'is_archived' in data:
            note.is_archived = data['is_archived']
        
        note.updated_at = datetime.utcnow()
        db.session.commit()
        
        return jsonify({
            'success': True,
            'note': note.to_dict()
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@notes_bp.route('/api/notes/<int:note_id>', methods=['DELETE'])
@login_required
def delete_note(note_id):
    """Удалить заметку"""
    try:
        note = Note.query.filter_by(id=note_id, teacher_id=current_user.id).first()
        if not note:
            return jsonify({
                'success': False,
                'error': 'Заметка не найдена'
            }), 404
        
        db.session.delete(note)
        db.session.commit()
        
        return jsonify({
            'success': True
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@notes_bp.route('/api/notes/<int:note_id>/pin', methods=['POST'])
@login_required
def toggle_pin(note_id):
    """Переключить закрепление заметки"""
    try:
        note = Note.query.filter_by(id=note_id, teacher_id=current_user.id).first()
        if not note:
            return jsonify({
                'success': False,
                'error': 'Заметка не найдена'
            }), 404
        
        note.is_pinned = not note.is_pinned
        note.updated_at = datetime.utcnow()
        db.session.commit()
        
        return jsonify({
            'success': True,
            'note': note.to_dict()
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@notes_bp.route('/api/notes/<int:note_id>/archive', methods=['POST'])
@login_required
def toggle_archive(note_id):
    """Переключить архивирование заметки"""
    try:
        note = Note.query.filter_by(id=note_id, teacher_id=current_user.id).first()
        if not note:
            return jsonify({
                'success': False,
                'error': 'Заметка не найдена'
            }), 404
        
        note.is_archived = not note.is_archived
        note.updated_at = datetime.utcnow()
        db.session.commit()
        
        return jsonify({
            'success': True,
            'note': note.to_dict()
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500







