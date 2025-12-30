import json
import os
import uuid
from werkzeug.security import generate_password_hash, check_password_hash
from app.models.user import User
from flask import current_app

DATA_FILE = "data/users.json"

class UserService:
    def __init__(self):
        self._ensure_data_file()
        self._bootstrap_admin()

    def _ensure_data_file(self):
        if not os.path.exists(DATA_FILE):
             os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
             with open(DATA_FILE, 'w') as f:
                 json.dump({}, f)

    def _load_data(self):
        if not os.path.exists(DATA_FILE):
            return {}
        try:
            with open(DATA_FILE, 'r') as f:
                return json.load(f)
        except Exception:
            return {}

    def _save_data(self, data):
        with open(DATA_FILE, 'w') as f:
            json.dump(data, f, indent=4)

    def _bootstrap_admin(self):
        # We need the app context to access config, but this service might be instantiated outside?
        # Typically services are instantiated or used within request context or properly configured.
        # Let's rely on current_app being available when methods are called, or pass config.
        # But for __init__, we need to be careful.
        # Best pattern: Lazy load or check on first access.
        pass
    
    def ensure_admin_exists(self):
        """
        Ensure admin user exists with correct password from .env.
        Called on each app startup to sync admin credentials.
        """
        users = self._load_data()
        
        admin_username = current_app.config.get('ADMIN_USERNAME')
        admin_password = current_app.config.get('ADMIN_PASSWORD')
        
        # If no admin credentials in .env, skip bootstrap
        if not admin_username or not admin_password:
            return
        
        # Check if admin user already exists
        existing_admin = None
        existing_admin_id = None
        for uid, data in users.items():
            if data.get('username') == admin_username:
                existing_admin = data
                existing_admin_id = uid
                break
        
        if existing_admin:
            # Admin exists - check if password matches .env
            # Only update if password doesn't match (to avoid unnecessary writes)
            if not check_password_hash(existing_admin['password_hash'], admin_password):
                new_hash = generate_password_hash(admin_password)
                users[existing_admin_id]['password_hash'] = new_hash
                self._save_data(users)
                print(f"Admin user '{admin_username}' password synced from environment.")
        else:
            # No admin exists - create one
            user_id = str(uuid.uuid4())
            password_hash = generate_password_hash(admin_password)
            users[user_id] = {
                "id": user_id,
                "username": admin_username,
                "password_hash": password_hash,
                "is_admin": True
            }
            self._save_data(users)
            print(f"Initial admin user '{admin_username}' created from environment configuration.")

    def get_user(self, user_id):
        users = self._load_data()
        data = users.get(user_id)
        if data:
            return User(data['id'], data['username'], data['password_hash'], data.get('is_admin', False))
        return None

    def get_user_by_username(self, username):
        users = self._load_data()
        for uid, data in users.items():
            if data['username'] == username:
                return User(data['id'], data['username'], data['password_hash'], data.get('is_admin', False))
        return None
    
    def get_all_users(self):
        users = self._load_data()
        return [User(d['id'], d['username'], d['password_hash'], d.get('is_admin', False)) for d in users.values()]

    def create_user(self, username, password, is_admin=False):
        if self.get_user_by_username(username):
            raise ValueError("Username already exists")
        
        users = self._load_data()
        user_id = str(uuid.uuid4())
        users[user_id] = {
            "id": user_id,
            "username": username,
            "password_hash": generate_password_hash(password),
            "is_admin": is_admin
        }
        self._save_data(users)
        return self.get_user(user_id)

    def update_password(self, user_id, new_password):
        users = self._load_data()
        if user_id in users:
            users[user_id]['password_hash'] = generate_password_hash(new_password)
            self._save_data(users)
            return True
        return False
        
    def delete_user(self, user_id):
        users = self._load_data()
        if user_id in users:
            del users[user_id]
            self._save_data(users)
            return True
        return False

    def verify_password(self, user, password):
        return check_password_hash(user.password_hash, password)

user_service = UserService()
