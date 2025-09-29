from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from datetime import datetime

app = Flask(__name__)
app.config['SECRET_KEY'] = 'popipopipopopipo'  # Clave super secreta para sesiones

# Lista temporal para almacenar los avisos (en producción usar una base de datos)
avisos = []

# Configuración de Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'


# Cuando un usuario no autorizado intenta acceder a una ruta protegida,
# redirigimos al login y preservamos la ruta solicitada en el parámetro "next".
@login_manager.unauthorized_handler
def handle_needs_login():
    # request might not be importable at top-level here; use redirect con next
    from flask import request
    return redirect(url_for('login', next=request.path))

# Esta clase es un ejemplo simple, deberías usar una base de datos real
class User(UserMixin):
    def __init__(self, id):
        self.id = id

@login_manager.user_loader
def load_user(user_id):
    # Solo cargar el usuario si la sesión indica que se autenticó correctamente.
    from flask import session
    if session.get('authenticated'):
        return User(user_id)
    return None

@app.route('/')
@app.route('/home')
def home():
    # Renderizar la página principal. Pasamos `avisos` por si la plantilla los utiliza.
    return render_template('main_panel/home.html', avisos=avisos)

@app.route('/login', methods=['GET', 'POST'])
def login():
    # obtener el destino al que volver después del login (si existe)
    next_page = None
    if request.method == 'GET':
        next_page = request.args.get('next')

    if request.method == 'POST':
        next_page = request.form.get('next') or request.args.get('next')
        # Aquí deberías verificar las credenciales del usuario
        username = request.form.get('username')
        password = request.form.get('password')

        # Este es un ejemplo simple; usamos una contraseña maestra para acceder al panel
        if username == "admin" and password == "skebedeh":
            user = User(username)
            login_user(user)
            # Marcar en la sesión que el usuario se autenticó correctamente
            session['authenticated'] = True
            # Tras login exitoso ir al panel de administración o a `next` si fue provisto
            if next_page and isinstance(next_page, str) and next_page.startswith('/'):
                return redirect(next_page)
            return redirect(url_for('panel'))
        else:
            flash('Credenciales inválidas')

    return render_template('login_panel/login.html', next=next_page)

@app.route('/register', methods=['GET', 'POST'])
def register():
    # Actualmente no hay una plantilla de registro en el proyecto.
    # Redirigimos a /login y mostramos un mensaje informativo.
    flash('Registro no disponible. Usa las credenciales proporcionadas.')
    return redirect(url_for('login'))

@app.route('/panel/add', methods=['POST'])
@login_required
def add_aviso():
    if not request.is_json:
        return jsonify({"error": "El contenido debe ser JSON"}), 400
    
    data = request.get_json()
    
    if not all(key in data for key in ['title', 'description', 'image_url', 'fecha_inicio', 'fecha_fin']):
        return jsonify({"error": "Faltan campos requeridos"}), 400
    
    try:
        fecha_inicio = datetime.fromisoformat(data['fecha_inicio'])
        fecha_fin = datetime.fromisoformat(data['fecha_fin'])
        if fecha_fin <= fecha_inicio:
            return jsonify({"error": "La fecha de fin debe ser posterior a la fecha de inicio"}), 400
    except ValueError:
        return jsonify({"error": "Formato de fecha inválido. Use formato ISO (YYYY-MM-DDTHH:MM:SS)"}), 400
    
    nuevo_aviso = {
        'id': len(avisos) + 1,
        'title': data['title'],
        'description': data['description'],
        'image_url': data['image_url'],
        'fecha_inicio': data['fecha_inicio'],
        'fecha_fin': data['fecha_fin'],
        'created_at': datetime.now().isoformat(),
    }
    
    avisos.append(nuevo_aviso)
    return jsonify(nuevo_aviso), 201

@app.route('/panel/edit/<int:aviso_id>', methods=['PUT'])
@login_required
def edit_aviso(aviso_id):
    if not request.is_json:
        return jsonify({"error": "El contenido debe ser JSON"}), 400
    
    data = request.get_json()
    aviso = next((aviso for aviso in avisos if aviso['id'] == aviso_id), None)
    
    if not aviso:
        return jsonify({"error": "Aviso no encontrado"}), 404
    
    if aviso['author'] != current_user.id:
        return jsonify({"error": "No autorizado para editar este aviso"}), 403
    
    # Actualizar solo los campos proporcionados
    if 'title' in data:
        aviso['title'] = data['title']
    if 'description' in data:
        aviso['description'] = data['description']
    if 'fecha_inicio' in data or 'fecha_fin' in data:
        try:
            nueva_fecha_inicio = datetime.fromisoformat(data.get('fecha_inicio', aviso['fecha_inicio']))
            nueva_fecha_fin = datetime.fromisoformat(data.get('fecha_fin', aviso['fecha_fin']))
            if nueva_fecha_fin <= nueva_fecha_inicio:
                return jsonify({"error": "La fecha de fin debe ser posterior a la fecha de inicio"}), 400
            aviso['fecha_inicio'] = data.get('fecha_inicio', aviso['fecha_inicio'])
            aviso['fecha_fin'] = data.get('fecha_fin', aviso['fecha_fin'])
        except ValueError:
            return jsonify({"error": "Formato de fecha inválido. Use formato ISO (YYYY-MM-DDTHH:MM:SS)"}), 400
    if 'image_url' in data:
        aviso['image_url'] = data['image_url']
    
    return jsonify(aviso)

@app.route('/panel/delete/<int:aviso_id>', methods=['DELETE'])
@login_required
def delete_aviso(aviso_id):
    aviso_index = next((index for (index, aviso) in enumerate(avisos) if aviso['id'] == aviso_id), None)
    
    if aviso_index is None:
        return jsonify({"error": "Aviso no encontrado"}), 404
    
    if avisos[aviso_index]['author'] != current_user.id:
        return jsonify({"error": "No autorizado para eliminar este aviso"}), 403
    
    aviso_eliminado = avisos.pop(aviso_index)
    return jsonify(aviso_eliminado)

@app.route('/panel/avisos', methods=['GET'])
def get_avisos():
    return jsonify(avisos)

@app.route('/edit_panel')
@login_required
def edit_panel():
    # Protección adicional por si el decorador no actúa (diagnóstico y seguridad)
    if not current_user.is_authenticated or not session.get('authenticated'):
        return redirect(url_for('login', next=request.path))
    # Mostrar el panel de administración (plantilla existente)
    return render_template('admin_panel/panel.html', avisos=avisos)


# Página del panel (administración)
@app.route('/panel')
@login_required
def panel():
    if not current_user.is_authenticated or not session.get('authenticated'):
        return redirect(url_for('login', next=request.path))
    return render_template('admin_panel/panel.html', avisos=avisos)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    # Limpiar la bandera de autenticación de la sesión
    session.pop('authenticated', None)
    return redirect(url_for('home'))

if __name__ == '__main__':
    app.run(debug=True)
