from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from app.services.user_service import user_service

auth_bp = Blueprint('auth', __name__, template_folder='../../templates/auth')

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('core.index'))

    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        user = user_service.get_user_by_username(username)
        
        if user and user_service.verify_password(user, password):
            login_user(user)
            next_page = request.args.get('next')
            return redirect(next_page or url_for('core.index'))
        else:
            flash('Nom d\'utilisateur ou mot de passe incorrect.', 'error')

    return render_template('auth/login.html')

@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('auth.login'))
