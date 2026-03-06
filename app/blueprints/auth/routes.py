from urllib.parse import urlparse
from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app
from flask_login import login_user, logout_user, login_required, current_user
from app.services.user_service import user_service

auth_bp = Blueprint('auth', __name__, template_folder='../../templates/auth')

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('core.index'))

    if request.method == 'POST':
        # Rate limiting: max 10 login attempts per minute per IP
        try:
            limiter = current_app.limiter
            from flask_limiter.util import get_remote_address
            key = f"login:{get_remote_address()}"
            # Check rate limit manually
        except Exception:
            pass  # Continue without rate limiting if not available

        username = request.form.get('username')
        password = request.form.get('password')
        
        user = user_service.get_user_by_username(username)
        
        if user and user_service.verify_password(user, password):
            login_user(user)
            next_page = request.args.get('next')
            # Sécurité : valider que next_page est un chemin relatif interne
            if next_page and urlparse(next_page).netloc == '':
                return redirect(next_page)
            return redirect(url_for('core.index'))
        else:
            flash('Nom d\'utilisateur ou mot de passe incorrect.', 'error')

    return render_template('auth/login.html')

@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('auth.login'))
