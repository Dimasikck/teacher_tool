from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from models import db, Teacher
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, BooleanField
from wtforms.validators import DataRequired, Email, Length

auth_bp = Blueprint('auth', __name__)


class LoginForm(FlaskForm):
    username = StringField(
        'Логин',
        validators=[DataRequired(), Length(min=3, max=80)],
        filters=[lambda x: x.strip() if isinstance(x, str) else x]
    )
    password = PasswordField('Пароль', validators=[DataRequired()])
    remember = BooleanField('Запомнить меня')
    submit = SubmitField('Войти')


class RegisterForm(FlaskForm):
    username = StringField('Логин', validators=[DataRequired(), Length(min=3, max=80)])
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Пароль', validators=[DataRequired(), Length(min=6)])
    submit = SubmitField('Регистрация')


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        teacher = Teacher.query.filter_by(username=form.username.data).first()
        if teacher and teacher.check_password(form.password.data):
            # persistent session for PWA installs
            login_user(teacher, remember=bool(form.remember.data))
            next_page = request.args.get('next')
            return redirect(next_page) if next_page else redirect(url_for('dashboard'))
        flash('Неверный логин или пароль', 'danger')
    return render_template('login.html', form=form)


@auth_bp.route('/register', methods=['GET', 'POST'])
@login_required
def register():
    if current_user.id != 1:
        flash('Только администратор может регистрировать пользователей', 'warning')
        return redirect(url_for('dashboard'))

    form = RegisterForm()
    if form.validate_on_submit():
        teacher = Teacher(username=form.username.data, email=form.email.data)
        teacher.set_password(form.password.data)
        db.session.add(teacher)
        db.session.commit()
        flash('Преподаватель зарегистрирован', 'success')
        return redirect(url_for('dashboard'))
    return render_template('register.html', form=form)


@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('auth.login'))