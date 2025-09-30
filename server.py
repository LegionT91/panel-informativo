from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from datetime import datetime
import os

# Usar el helper mysqlconnection.py (pymysql)
from mysqlconnection import connectToMySQL

# Password hashing
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config['SECRET_KEY'] = 'popipopipopopopipo'  # Clave super secreta para sesiones

# Carpeta para subir imágenes (relativa a la carpeta raíz de la app)
app.config['UPLOAD_FOLDER'] = os.environ.get('UPLOAD_FOLDER', 'static/uploads')
# Extensiones permitidas (opcional, se puede ampliar)
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

# Clave maestra requerida para crear usuarios desde el formulario de registro.
# Se puede sobreescribir con la variable de entorno MASTER_KEY si se desea.
MASTER_KEY = os.environ.get('MASTER_KEY', 'complejoprincipedegalescuenta25')

# Lista temporal para almacenar los avisos (en producción usar una base de datos)
avisos = []

# Configuración de Flask-Login
login_manager = LoginManager()
login_manager.login_view = 'login'
login_manager.init_app(app)

@login_manager.unauthorized_handler
def handle_needs_login():
    from flask import request
    return redirect(url_for('login', next=request.url))

class User(UserMixin):
    def __init__(self, username):
        self.username = username
        self.id = username

    def get_id(self):
        return self.username

@login_manager.user_loader
def load_user(user_id):
    try:
        db = connectToMySQL(os.environ.get('DB_NAME', 'panel_informativo'))
        rows = db.query_db('SELECT * FROM usuarios WHERE username = %(username)s', {'username': user_id})
        if rows:
            return User(user_id)
    except Exception:
        pass
    return None

@app.route('/')
@app.route('/home')
def home():
    # NUEVO: Obtener las tres últimas noticias desde la base de datos y mostrarlas en home
    try:
        db = connectToMySQL(os.environ.get('DB_NAME', 'panel_informativo'))
        rows = db.query_db('SELECT * FROM notice ORDER BY idnotice DESC LIMIT 3')
        eventos = []
        for r in rows:
            def fmt_field(dt):
                if not dt:
                    return ""
                if hasattr(dt, 'strftime'):
                    return dt.strftime('%d/%m/%Y')
                return str(dt)
            eventos.append({
                'titulo': r.get('name_notice', ''),
                'fecha_inicio': fmt_field(r.get('start_date')),
                'fecha_fin': fmt_field(r.get('end_date')),
                'imagen_url': r.get('image_url', ''),
            })
    except Exception as e:
        eventos = []
    return render_template('main_panel/home.html', eventos=eventos)

@app.route('/login', methods=['GET', 'POST'])
def login():
    next_page = None
    if request.method == 'GET':
        next_page = request.args.get('next')

    if request.method == 'POST':
        next_page = request.form.get('next') or request.args.get('next')
        username = request.form.get('username')
        password = request.form.get('password')

        try:
            db = connectToMySQL(os.environ.get('DB_NAME', 'panel_informativo'))
            rows = db.query_db('SELECT * FROM usuarios WHERE username = %(username)s', {'username': username})
            row = rows[0] if rows else None

            if row and check_password_hash(row['password'], password):
                user = User(row['username'])
                login_user(user)
                session.permanent = False
                if next_page and isinstance(next_page, str) and next_page.startswith('/'):
                    return redirect(next_page)
                return redirect(url_for('panel'))
            else:
                flash('Credenciales inválidas')
        except Exception as e:
            flash(f'Error al conectar con la base de datos: {e}')

    return render_template('login_panel/login.html', next=next_page)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        master_key = request.form.get('master_key')
        email = request.form.get('email')

        if not username or not password:
            flash('Debe proporcionar usuario y contraseña')
            return redirect(url_for('register'))

        if master_key != MASTER_KEY:
            flash('Clave maestra incorrecta')
            return redirect(url_for('register'))

        hashed = generate_password_hash(password)

        try:
            db = connectToMySQL(os.environ.get('DB_NAME', 'panel_informativo'))
            existing = db.query_db('SELECT id FROM usuarios WHERE username = %(username)s', {'username': username})
            if existing:
                flash('El nombre de usuario ya existe')
                return redirect(url_for('register'))

            db.query_db('INSERT INTO usuarios (username, password, email, created_at, updated_at) VALUES (%(username)s, %(password)s, %(email)s, NOW(), NOW())',
                        {'username': username, 'password': hashed, 'email': email})
            flash('Registro exitoso. Ya puedes ingresar.')
            return redirect(url_for('login'))
        except Exception as e:
            flash(f'Error al conectar con la base de datos: {e}')
            return redirect(url_for('register'))

    return render_template('registrer_panel/registrer.html')

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
    try:
        db = connectToMySQL(os.environ.get('DB_NAME', 'panel_informativo'))
        rows = db.query_db('SELECT * FROM notice WHERE idnotice = %(id)s', {'id': aviso_id})
        if not rows:
            return jsonify({"error": "Aviso no encontrado"}), 404
        row = rows[0]
        img_field = row.get('image_url') if 'image_url' in row else None
        if img_field:
            filename = os.path.basename(img_field)
            upload_folder = os.path.join(app.root_path, app.config['UPLOAD_FOLDER'])
            file_path = os.path.join(upload_folder, filename)
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
            except Exception:
                pass
        db.query_db('DELETE FROM notice WHERE idnotice = %(id)s', {'id': aviso_id})
    except Exception as e:
        return jsonify({'error': f'Error al eliminar en la base de datos: {e}'}), 500

    aviso_index = next((index for (index, aviso) in enumerate(avisos) if aviso['id'] == aviso_id), None)
    aviso_eliminado = None
    if aviso_index is not None:
        aviso_eliminado = avisos.pop(aviso_index)

    return jsonify({'deleted': aviso_id, 'removed_from_memory': aviso_eliminado is not None})

@app.route('/panel/avisos', methods=['GET'])
def get_avisos():
    try:
        db = connectToMySQL(os.environ.get('DB_NAME', 'panel_informativo'))
        rows = db.query_db('SELECT * FROM notice ORDER BY idnotice DESC')
        mapped = []
        for r in rows:
            def fmt_field(dt):
                if not dt:
                    return None
                try:
                    return dt.isoformat()
                except Exception:
                    return str(dt)

            mapped.append({
                'id': r.get('idnotice'),
                'title': r.get('name_notice'),
                'description': r.get('description') if 'description' in r else '',
                'image_url': r.get('image_url') if 'image_url' in r else '',
                'fecha_inicio': fmt_field(r.get('start_date')),
                'fecha_fin': fmt_field(r.get('end_date')),
            })
        return jsonify(mapped)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/edit_panel')
@login_required
def edit_panel():
    if not current_user.is_authenticated:
        return redirect(url_for('login', next=request.path))
    return render_template('admin_panel/panel.html', avisos=avisos)

@app.route('/panel')
@login_required
def panel():
    if not current_user.is_authenticated:
        return redirect(url_for('login', next=request.path))
    try:
        db = connectToMySQL(os.environ.get('DB_NAME', 'panel_informativo'))
        rows = db.query_db('SELECT * FROM notice ORDER BY idnotice DESC')
        mapped = []
        for r in rows:
            def fmt_field(dt):
                if not dt:
                    return None
                try:
                    return dt.isoformat()
                except Exception:
                    return str(dt)

            mapped.append({
                'id': r.get('idnotice'),
                'title': r.get('name_notice'),
                'description': r.get('description') if 'description' in r else '',
                'image_url': r.get('image_url') if 'image_url' in r else '',
                'fecha_inicio': fmt_field(r.get('start_date')),
                'fecha_fin': fmt_field(r.get('end_date')),
            })
        return render_template('admin_panel/panel.html', avisos=mapped)
    except Exception as e:
        flash(f'Error cargando avisos desde la base de datos: {e}')
        return render_template('admin_panel/panel.html', avisos=avisos)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    session.clear()
    return redirect(url_for('home'))

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/panel/upload', methods=['POST'])
@login_required
def upload_news():
    if 'photo' not in request.files:
        flash('No se ha enviado ninguna imagen')
        return redirect(url_for('panel'))

    file = request.files['photo']
    title = request.form.get('title')
    fecha_inicio = request.form.get('fecha_inicio')
    fecha_fin = request.form.get('fecha_fin')

    if not title or not fecha_inicio or not fecha_fin:
        flash('Debe completar título, fecha de inicio y fecha de fin')
        return redirect(url_for('panel'))

    try:
        inicio = datetime.fromisoformat(fecha_inicio)
        fin = datetime.fromisoformat(fecha_fin)
        if fin <= inicio:
            flash('La fecha de fin debe ser posterior a la fecha de inicio')
            return redirect(url_for('panel'))
    except ValueError:
        flash('Formato de fecha inválido')
        return redirect(url_for('panel'))

    filename = None
    image_url = ''
    if file and file.filename:
        if not allowed_file(file.filename):
            flash('Tipo de archivo no permitido. Usa png/jpg/jpeg/gif')
            return redirect(url_for('panel'))
        filename = secure_filename(file.filename)
        upload_folder = os.path.join(app.root_path, app.config['UPLOAD_FOLDER'])
        os.makedirs(upload_folder, exist_ok=True)
        save_path = os.path.join(upload_folder, filename)
        file.save(save_path)
        image_url = url_for('static', filename=f'uploads/{filename}')

    try:
        db = connectToMySQL(os.environ.get('DB_NAME', 'panel_informativo'))
        def fmt_mysql(dt_str):
            if not dt_str:
                return None
            s = dt_str.replace('T', ' ')
            parts = s.split(' ')
            if len(parts) > 1 and len(parts[1]) == 5:
                s = s + ':00'
            return s

        start_sql = fmt_mysql(fecha_inicio)
        end_sql = fmt_mysql(fecha_fin)
        try:
            if filename:
                image_url_db = f'static/uploads/{filename}'
                db.query_db(
                    'INSERT INTO notice (name_notice, start_date, end_date, image_url) VALUES (%(name)s, %(start)s, %(end)s, %(img)s)',
                    {'name': title, 'start': start_sql, 'end': end_sql, 'img': image_url_db}
                )
            else:
                db.query_db(
                    'INSERT INTO notice (name_notice, start_date, end_date) VALUES (%(name)s, %(start)s, %(end)s)',
                    {'name': title, 'start': start_sql, 'end': end_sql}
                )
        except Exception:
            db.query_db(
                'INSERT INTO notice (name_notice, start_date, end_date) VALUES (%(name)s, %(start)s, %(end)s)',
                {'name': title, 'start': start_sql, 'end': end_sql}
            )

        row = db.query_db('SELECT * FROM notice ORDER BY idnotice DESC LIMIT 1')
        inserted = row[0] if row else None

        nuevo_aviso = {
            'id': inserted['idnotice'] if inserted else (len(avisos) + 1),
            'title': title,
            'description': request.form.get('description', ''),
            'image_url': f'static/uploads/{filename}' if filename else '',
            'fecha_inicio': fecha_inicio,
            'fecha_fin': fecha_fin,
            'created_at': datetime.now().isoformat(),
        }
        avisos.append(nuevo_aviso)
        flash('Noticia añadida correctamente')
        return redirect(url_for('panel'))
    except Exception as e:
        flash(f'Error al guardar en la base de datos: {e}')
        return redirect(url_for('panel'))

if __name__ == '__main__':
    full_upload_path = os.path.join(app.root_path, app.config['UPLOAD_FOLDER'])
    os.makedirs(full_upload_path, exist_ok=True)
    app.run(debug=True)


