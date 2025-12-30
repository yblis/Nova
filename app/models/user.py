from flask_login import UserMixin

class User(UserMixin):
    def __init__(self, id, username, password_hash, is_admin=False):
        self.id = id
        self.username = username
        self.password_hash = password_hash
        self.is_admin = is_admin

    def to_dict(self):
        return {
            "id": self.id,
            "username": self.username,
            "password_hash": self.password_hash,
            "is_admin": self.is_admin
        }
