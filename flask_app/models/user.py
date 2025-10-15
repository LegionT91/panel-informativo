"""
Modelo de Usuario
"""
from flask_login import UserMixin

class User(UserMixin):
    """Modelo de usuario para Flask-Login"""
    
    def __init__(self, username):
        self.username = username
        self.id = username

    def get_id(self):
        return self.username

