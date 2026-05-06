from flask import Blueprint, render_template, request, session, redirect, url_for
from repository import UserRepository
from security import SecurityService
from extensions import csrf, limiter
from helpers import registrar_auditoria
import logging

auth_bp = Blueprint('auth', __name__)

@auth_bp.route("/login", methods=['GET', 'POST'])
@csrf.exempt
@limiter.limit("30/minute", methods=["POST"], error_message="Muitas tentativas. Aguarde 1 minuto.")
def login_web():
    if request.method == 'POST':
        username = request.form.get('username').strip()
        password = request.form.get('password').strip()

        repo = UserRepository()
        user = repo.get_user_by_username(username)
        logging.warning(f"[DEBUG] login_web user: {user}")
        if user:
            logging.warning(f"[DEBUG] login_web user.password_hash: {user.password_hash}")
        if user and SecurityService.verify_password(password, user.password_hash):
            session['user_id'] = user.id
            session['username'] = user.username
            session['role'] = user.role
            session['restaurante_id'] = user.restaurante_id
            registrar_auditoria('login', detalhes={'username': username})
            return redirect(url_for('index'))
        else:
            logging.warning(f"Login falhou para '{username}' de {request.remote_addr}")
            return render_template('login.html', erro='Usuário ou senha inválidos!')

    return render_template('login.html')


@auth_bp.route("/logout")
@limiter.limit("120/minute")
def logout():
    session.clear()
    registrar_auditoria('logout')
    return redirect(url_for('auth.login_web'))
