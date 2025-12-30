from flask import Blueprint, render_template, redirect, url_for, flash, request, abort
from flask_login import login_required, current_user
from app.services.user_service import user_service
from functools import wraps

admin_bp = Blueprint('admin', __name__, template_folder='../../templates/admin')

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            abort(403)
        return f(*args, **kwargs)
    return decorated_function

@admin_bp.route('/users')
@login_required
@admin_required
def users_list():
    users = user_service.get_all_users()
    return render_template('admin/users.html', users=users)

@admin_bp.route('/partials/users')
@login_required
@admin_required
def users_partial():
    """Partial pour la navigation SPA"""
    users = user_service.get_all_users()
    return render_template('admin/partials/users.html', users=users)


@admin_bp.route('/users/create', methods=['POST'])
@login_required
@admin_required
def create_user():
    username = request.form.get('username')
    password = request.form.get('password')
    is_admin = request.form.get('is_admin') == 'on'
    
    try:
        user_service.create_user(username, password, is_admin)
        flash('Utilisateur créé avec succès.', 'success')
    except ValueError as e:
        flash(str(e), 'error')
        
    return redirect(url_for('admin.users_list'))

@admin_bp.route('/users/<user_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_user(user_id):
    if user_id == current_user.id:
        flash('Vous ne pouvez pas supprimer votre propre compte.', 'error')
    else:
        if user_service.delete_user(user_id):
            flash('Utilisateur supprimé.', 'success')
        else:
            flash('Utilisateur introuvable.', 'error')
            
    return redirect(url_for('admin.users_list'))

@admin_bp.route('/users/<user_id>/password', methods=['POST'])
@login_required
@admin_required
def update_password(user_id):
    new_password = request.form.get('password')
    if user_service.update_password(user_id, new_password):
        flash('Mot de passe mis à jour.', 'success')
    else:
        flash('Erreur lors de la mise à jour du mot de passe.', 'error')
    return redirect(url_for('admin.users_list'))

# Allow admin to change their own password
@admin_bp.route('/my-account', methods=['GET', 'POST'])
@login_required
def my_account():
    if request.method == 'POST':
        password = request.form.get('password')
        if password:
            user_service.update_password(current_user.id, password)
            flash('Votre mot de passe a été mis à jour.', 'success')
    return render_template('admin/my_account.html')
