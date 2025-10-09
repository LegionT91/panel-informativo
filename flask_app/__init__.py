"""
Aplicación Flask modularizada
"""
from flask import Flask
from flask import send_from_directory
from flask_login import LoginManager
from flask_app.controllers import register_routes, require_login_for_panel, handle_needs_login
from flask_app.config.mysqlconnection import connectToMySQL
import os

def create_app():
    """Factory function para crear la aplicación Flask"""
    app = Flask(__name__)
    
    # Configuración básica
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'popipopipopopopipo')
    app.config['UPLOAD_FOLDER'] = os.environ.get('UPLOAD_FOLDER', 'static/uploads')
    
    # Configurar Flask-Login
    login_manager = LoginManager()
    login_manager.login_view = 'login'
    login_manager.login_message = 'Por favor inicie sesión para acceder a esta página'
    login_manager.login_message_category = 'warning'
    login_manager.init_app(app)
    
    # User loader para Flask-Login
    @login_manager.user_loader
    def load_user(user_id):
        try:
            db = connectToMySQL(os.environ.get('DB_NAME', 'panel_informativo'))
            rows = db.query_db('SELECT * FROM usuarios WHERE username = %(username)s', {'username': user_id})
            if rows:
                from flask_app.controllers.panel_controller import User
                return User(user_id)
        except Exception:
            pass
        return None
    
    # Registrar handler de login primero
    handle_needs_login(app)
    
    # Registrar todas las rutas
    register_routes(app)
    
    # Registrar middleware después de que las rutas estén disponibles
    require_login_for_panel(app)
    
    # Crear carpeta de uploads si no existe
    full_upload_path = os.path.join(app.root_path, app.config['UPLOAD_FOLDER'])
    os.makedirs(full_upload_path, exist_ok=True)
    
    # Configurar ruta estática para la carpeta uploads
    @app.route('/uploads/<filename>')
    def uploaded_file(filename):
            # En lugar de usar send_static_file con "static/uploads/..." (que genera
            # rutas tipo /static/static/...), servimos directamente desde el
            # directorio configurado para uploads.
            upload_dir = os.path.join(app.root_path, app.config['UPLOAD_FOLDER'])
            # send_from_directory toma la ruta del directorio y el nombre de archivo;
            # así evitamos prefijos duplicados en la URL.
            return send_from_directory(upload_dir, filename)
    
    return app

