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
app.config['SECRET_KEY'] = 'popipopipopopipo'  # Clave super secreta para sesiones

# Carpeta para subir imágenes (relativa a la carpeta raíz de la app)
app.config['UPLOAD_FOLDER'] = os.environ.get('UPLOAD_FOLDER', 'static/uploads')
# Extensiones permitidas (opcional, se puede ampliar)
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

# Clave maestra requerida para crear usuarios desde el formulario de registro.
# Se puede sobreescribir con la variable de entorno MASTER_KEY si se desea.
MASTER_KEY = os.environ.get('MASTER_KEY', 'complejoprincipedegalescuenta25')

# Lista temporal para almacenar los avisos (en producción usar una base de datos)
avisos = []

# Configuración de Flask-Login
login_manager = LoginManager()
login_manager.login_view = 'login'
login_manager.login_message = 'Por favor inicie sesión para acceder a esta página'
login_manager.login_message_category = 'warning'
login_manager.init_app(app)


# Proteger cualquier ruta que comience con /panel excepto las excepciones públicas
@app.before_request
def require_login_for_panel():
    try:
        path = request.path
    except Exception:
        return None

    # Rutas que dejaremos públicas (por ejemplo, para el front público)
    public_panel_paths = ['/panel/avisos']

    # Si la ruta comienza con /panel y no está en la lista pública, forzar login
    if path.startswith('/panel') and path not in public_panel_paths:
        # Si el usuario no está autenticado, redirigir al login
        if not current_user.is_authenticated:
            return redirect(url_for('login', next=request.url))
        # Evitar bucles al redirigir si ya estamos en la página de login
        if path == url_for('login'):
            return None
        # Si el usuario ya está autenticado no hacemos nada
        if getattr(current_user, 'is_authenticated', False):
            return None
        # Redirigir al login conservando la ruta solicitada en next
        return redirect(url_for('login', next=path))


# Cuando un usuario no autorizado intenta acceder a una ruta protegida,
# redirigimos al login y preservamos la ruta solicitada en el parámetro "next".
@login_manager.unauthorized_handler
def handle_needs_login():
    # request might not be importable at top-level here; use redirect con next
    from flask import request
    # Usar la URL completa como destino "next" para preservar querystring si existe
    return redirect(url_for('login', next=request.url))

# Esta clase es un ejemplo simple, deberías usar una base de datos real
class User(UserMixin):
    def __init__(self, username):
        # Usamos el nombre de usuario como identificador
        self.username = username
        self.id = username

    def get_id(self):
        return self.username

@login_manager.user_loader
def load_user(user_id):
    # Cargar el usuario consultando la tabla `usuarios`.
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
    # Renderizar la página principal. Pasamos `avisos` por si la plantilla los utiliza.
    return render_template('main_panel/home.html', avisos=avisos)

@app.route('/panel')
@login_required
def panel():
    if not current_user.is_authenticated:
        return redirect(url_for('login'))
    return render_template('admin_panel/panel.html')

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

        # Validar contra la tabla `usuarios` en MySQL usando el helper connectToMySQL
        try:
            db = connectToMySQL(os.environ.get('DB_NAME', 'panel_informativo'))
            rows = db.query_db('SELECT * FROM usuarios WHERE username = %(username)s', {'username': username})
            row = rows[0] if rows else None

            if row and check_password_hash(row['password'], password):
                user = User(row['username'])
                login_user(user)
                # No hacer la sesión permanente: que expire al cerrar el navegador
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
    # Registro usando MySQL
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        master_key = request.form.get('master_key')
        email = request.form.get('email')

        if not username or not password:
            flash('Debe proporcionar usuario y contraseña')
            return redirect(url_for('register'))

        # validar clave maestra
        if master_key != MASTER_KEY:
            flash('Clave maestra incorrecta')
            return redirect(url_for('register'))

        hashed = generate_password_hash(password)

        # Conectar a la base de datos
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

    if not all(key in data for key in ['title', 'image_url', 'fecha_inicio', 'fecha_fin']):
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
    # Aceptamos JSON con los campos a actualizar: title, description, fecha_inicio, fecha_fin, image_url
    if not request.is_json:
        return jsonify({"error": "El contenido debe ser JSON"}), 400

    data = request.get_json()

    # Validar fechas si están presentes
    if 'fecha_inicio' in data or 'fecha_fin' in data:
        try:
            nueva_inicio = datetime.fromisoformat(data.get('fecha_inicio')) if data.get('fecha_inicio') else None
            nueva_fin = datetime.fromisoformat(data.get('fecha_fin')) if data.get('fecha_fin') else None
            if nueva_inicio and nueva_fin and nueva_fin <= nueva_inicio:
                return jsonify({"error": "La fecha de fin debe ser posterior a la fecha de inicio"}), 400
        except ValueError:
            return jsonify({"error": "Formato de fecha inválido. Use formato ISO (YYYY-MM-DDTHH:MM:SS)"}), 400

    try:
        db = connectToMySQL(os.environ.get('DB_NAME', 'panel_informativo'))
        rows = db.query_db('SELECT * FROM notice WHERE idnotice = %(id)s', {'id': aviso_id})
        if not rows:
            return jsonify({"error": "Aviso no encontrado"}), 404
        # Construir consulta UPDATE dinámica según los campos que vienen
        set_clauses = []
        params = {'id': aviso_id}

        def fmt_mysql(dt_str):
            if not dt_str:
                return None
            s = dt_str.replace('T', ' ')
            parts = s.split(' ')
            if len(parts) > 1 and len(parts[1]) == 5:
                s = s + ':00'
            return s

        if 'title' in data:
            set_clauses.append('name_notice = %(name)s')
            params['name'] = data.get('title')
        # no manejamos 'description' (campo eliminado)
        if 'fecha_inicio' in data:
            set_clauses.append('start_date = %(start)s')
            params['start'] = fmt_mysql(data.get('fecha_inicio'))
        if 'fecha_fin' in data:
            set_clauses.append('end_date = %(end)s')
            params['end'] = fmt_mysql(data.get('fecha_fin'))
        if 'image_url' in data:
            set_clauses.append('image_url = %(img)s')
            params['img'] = data.get('image_url')

        if set_clauses:
            sql = 'UPDATE notice SET ' + ', '.join(set_clauses) + ' WHERE idnotice = %(id)s'
            try:
                db.query_db(sql, params)
            except Exception:
                # Fallback: intentar actualizar solo columnas básicas si alguna columna no existe
                # Intentamos excluir description/image_url si fallan
                fallback_clauses = [c for c in set_clauses if not c.startswith('description') and not c.startswith('image_url')]
                if fallback_clauses:
                    sql2 = 'UPDATE notice SET ' + ', '.join(fallback_clauses) + ' WHERE idnotice = %(id)s'
                    db.query_db(sql2, params)

        # Leer fila actualizada
        row = db.query_db('SELECT * FROM notice WHERE idnotice = %(id)s', {'id': aviso_id})
        r = row[0] if row else rows[0]

        def fmt_field(dt):
            if not dt:
                return None
            try:
                return dt.isoformat()
            except Exception:
                return str(dt)

        mapped = {
            'id': r.get('idnotice'),
            'title': r.get('name_notice'),
            'description': r.get('description') if 'description' in r else '',
            'image_url': r.get('image_url') if 'image_url' in r else '',
            'fecha_inicio': fmt_field(r.get('start_date')),
            'fecha_fin': fmt_field(r.get('end_date')),
        }

        # Actualizar memoria local si existe
        for aviso in avisos:
            if aviso.get('id') == mapped['id']:
                aviso.update(mapped)
                break

        return jsonify(mapped)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/panel/delete/<int:aviso_id>', methods=['DELETE'])
@login_required
def delete_aviso(aviso_id):
    # Intentar eliminar desde la base de datos y borrar la imagen asociada si existe
    try:
        db = connectToMySQL(os.environ.get('DB_NAME', 'panel_informativo'))
        rows = db.query_db('SELECT * FROM notice WHERE idnotice = %(id)s', {'id': aviso_id})
        if not rows:
            return jsonify({"error": "Aviso no encontrado"}), 404
        row = rows[0]
        # Si existe imagen asociada, borrarla del disco
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
        # Borrar la fila en la BD
        db.query_db('DELETE FROM notice WHERE idnotice = %(id)s', {'id': aviso_id})
    except Exception as e:
        return jsonify({'error': f'Error al eliminar en la base de datos: {e}'}), 500

    # También quitar de la memoria si estaba
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
        # Mapear campos a la estructura esperada
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
    # Protección adicional por si el decorador no actúa (diagnóstico y seguridad)
    if not current_user.is_authenticated:
        return redirect(url_for('login', next=request.path))
    # Mostrar el panel de administración (plantilla existente)
    return render_template('admin_panel/panel.html', avisos=avisos)


# Otras rutas y funciones del panel
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
    # Limpiar la bandera de autenticación de la sesión
    # Borrar toda la sesión para asegurarnos de que no quede información
    session.clear()
    return redirect(url_for('home'))


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@app.route('/panel/upload', methods=['POST'])
@login_required
def upload_news():
    # Obtener archivo (si fue enviado). No requerimos la imagen obligatoriamente.
    file = request.files.get('photo')
    title = request.form.get('title')
    fecha_inicio = request.form.get('fecha_inicio')
    fecha_fin = request.form.get('fecha_fin')

    # Log básico para diagnóstico
    try:
        app.logger.info(f"upload_news called: title={title!r}, fecha_inicio={fecha_inicio!r}, fecha_fin={fecha_fin!r}, file_present={bool(file and getattr(file, 'filename', None))}")
    except Exception:
        pass

    if not title or not fecha_inicio or not fecha_fin:
        flash('Debe completar título, fecha de inicio y fecha de fin')
        return redirect(url_for('panel'))

    

    # Validar fechas
    try:
        inicio = datetime.fromisoformat(fecha_inicio)
        fin = datetime.fromisoformat(fecha_fin)
        if fin <= inicio:
            flash('La fecha de fin debe ser posterior a la fecha de inicio')
            return redirect(url_for('panel'))
    except ValueError:
        flash('Formato de fecha inválido')
        return redirect(url_for('panel'))

    # Manejar archivo y ruta pública
    filename = None
    image_url = ''
    if file and file.filename:
        if not allowed_file(file.filename):
            flash('Tipo de archivo no permitido. Usa png/jpg/jpeg/gif/webp')
            return redirect(url_for('panel'))
        filename = secure_filename(file.filename)
        upload_folder = os.path.join(app.root_path, app.config['UPLOAD_FOLDER'])
        os.makedirs(upload_folder, exist_ok=True)
        save_path = os.path.join(upload_folder, filename)
        try:
            file.save(save_path)
        except Exception as e:
            app.logger.exception('Error guardando archivo')
            flash(f'Error guardando archivo: {e}')
            return redirect(url_for('panel'))
        image_url = url_for('static', filename=f'uploads/{filename}')

    # Guardar en la base de datos
    try:
        db = connectToMySQL(os.environ.get('DB_NAME', 'panel_informativo'))

        # Formatear fechas para MySQL: 'YYYY-MM-DD HH:MM:SS'
        def fmt_mysql(dt_str):
            if not dt_str:
                return None
            s = dt_str.replace('T', ' ')
            # si falta segundos, añadir :00
            parts = s.split(' ')
            if len(parts) > 1 and len(parts[1]) == 5:
                s = s + ':00'
            return s

        start_sql = fmt_mysql(fecha_inicio)
        end_sql = fmt_mysql(fecha_fin)
        # Intentar insertar incluyendo el nombre del archivo en la columna image_url (si existe en la tabla)
        try:
            if filename:
                image_url_db = f'static/uploads/{filename}'
                insert_result = db.query_db(
                    'INSERT INTO notice (name_notice, start_date, end_date, image_url) VALUES (%(name)s, %(start)s, %(end)s, %(img)s)',
                    {'name': title, 'start': start_sql, 'end': end_sql, 'img': image_url_db}
                )
            else:
                insert_result = db.query_db(
                    'INSERT INTO notice (name_notice, start_date, end_date) VALUES (%(name)s, %(start)s, %(end)s)',
                    {'name': title, 'start': start_sql, 'end': end_sql}
                )
            try:
                app.logger.info(f'Insert result: {insert_result!r}')
            except Exception:
                pass
        except Exception as ex:
            # Fallback por si la tabla no tiene columna image_url
            try:
                insert_result = db.query_db(
                    'INSERT INTO notice (name_notice, start_date, end_date) VALUES (%(name)s, %(start)s, %(end)s)',
                    {'name': title, 'start': start_sql, 'end': end_sql}
                )
                try:
                    app.logger.info(f'Fallback insert result: {insert_result!r}')
                except Exception:
                    pass
            except Exception as e:
                # Re-raise to outer except
                raise

        # Obtener la última fila insertada
        row = db.query_db('SELECT * FROM notice ORDER BY idnotice DESC LIMIT 1')
        try:
            app.logger.info(f'SELECT returned rows: {row!r}')
        except Exception:
            pass
        inserted = row[0] if row else None
        try:
            app.logger.info(f'Inserted row (mapped): {inserted!r}')
        except Exception:
            pass

        # Añadir a memoria también para compatibilidad inmediata con endpoints en memoria
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
        # Loguear excepción para diagnóstico y mostrar mensaje al usuario
        try:
            app.logger.exception(e)
        except Exception:
            pass
        flash(f'Error al guardar en la base de datos: {e}')

        return redirect(url_for('panel'))


@app.route('/panel/upload_image/<int:aviso_id>', methods=['POST'])
@login_required
def upload_image_edit(aviso_id):
    # Endpoint para permitir subir/actualizar la imagen de un aviso ya existente desde el modal de edición.
    if 'photo' not in request.files:
        return jsonify({'error': 'No se ha enviado ningún fichero'}), 400

    file = request.files['photo']
    if not file or not file.filename:
        return jsonify({'error': 'Fichero inválido'}), 400

    if not allowed_file(file.filename):
        return jsonify({'error': 'Tipo de archivo no permitido. Usa png/jpg/jpeg/gif/webp'}), 400

    filename = secure_filename(file.filename)
    upload_folder = os.path.join(app.root_path, app.config['UPLOAD_FOLDER'])
    os.makedirs(upload_folder, exist_ok=True)
    save_path = os.path.join(upload_folder, filename)
    try:
        file.save(save_path)
    except Exception as e:
        app.logger.exception('Error guardando archivo al editar')
        return jsonify({'error': str(e)}), 500

    image_url_db = f'static/uploads/{filename}'

    # Opcionalmente actualizar otros campos que vengan en el form (title, fecha_inicio, fecha_fin)
    title = request.form.get('title')
    fecha_inicio = request.form.get('fecha_inicio')
    fecha_fin = request.form.get('fecha_fin')

    try:
        db = connectToMySQL(os.environ.get('DB_NAME', 'panel_informativo'))
        # Construir UPDATE dinámico
        set_clauses = ['image_url = %(img)s']
        params = {'img': image_url_db, 'id': aviso_id}
        def fmt_mysql(dt_str):
            if not dt_str:
                return None
            s = dt_str.replace('T', ' ')
            parts = s.split(' ')
            if len(parts) > 1 and len(parts[1]) == 5:
                s = s + ':00'
            return s

        if title:
            set_clauses.append('name_notice = %(name)s')
            params['name'] = title
        if fecha_inicio:
            set_clauses.append('start_date = %(start)s')
            params['start'] = fmt_mysql(fecha_inicio)
        if fecha_fin:
            set_clauses.append('end_date = %(end)s')
            params['end'] = fmt_mysql(fecha_fin)

        sql = 'UPDATE notice SET ' + ', '.join(set_clauses) + ' WHERE idnotice = %(id)s'
        db.query_db(sql, params)

        # Actualizar memoria
        for aviso in avisos:
            if aviso.get('id') == aviso_id:
                aviso['image_url'] = image_url_db
                if title:
                    aviso['title'] = title
                if fecha_inicio:
                    aviso['fecha_inicio'] = fecha_inicio
                if fecha_fin:
                    aviso['fecha_fin'] = fecha_fin
                break

        return jsonify({'ok': True, 'image_url': image_url_db})
    except Exception as e:
        app.logger.exception('Error actualizando imagen en BD')
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    # Asegurarse de que la carpeta de subidas existe
    full_upload_path = os.path.join(app.root_path, app.config['UPLOAD_FOLDER'])
    os.makedirs(full_upload_path, exist_ok=True)
    app.run(debug=True)





