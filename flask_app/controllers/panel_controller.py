# -*- coding: utf-8 -*-
"""
Controlador principal del panel informativo.

Este archivo expone tres funciones públicas que el paquete app importa:
- require_login_for_panel(app): middleware que protege rutas del panel
- handle_needs_login(app): registra la ruta /login
- register_routes(app): registra todas las rutas principales (home, APIs, admin)

También centraliza la construcción de URLs públicas para imágenes mediante
la función build_image_url() para evitar prefijos duplicados como
"/static/static/uploads/...".
"""
from datetime import datetime
import hashlib
import os

from flask import (
    render_template,
    request,
    redirect,
    url_for,
    flash,
    jsonify,
    session,
    current_app,
)
from flask_login import UserMixin, login_user, login_required, logout_user, current_user

from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

from flask_app.config.mysqlconnection import connectToMySQL
from flask_app.clima import obtener_clima_nueva_imperial

# Config
UPLOAD_FOLDER = os.environ.get('UPLOAD_FOLDER', 'static/uploads')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
MASTER_KEY = os.environ.get('MASTER_KEY', 'complejoprincipedegalescuenta25')

# Memoria local simple (no persistente) usada por algunas vistas
avisos = []


class User(UserMixin):
    def __init__(self, username):
        self.username = username
        self.id = username

    def get_id(self):
        return self.username


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def fmt_mysql(dt_str):
    """Normaliza una fecha ISO para MySQL (añade segundos si faltan)."""
    if not dt_str:
        return None
    s = dt_str.replace('T', ' ')
    parts = s.split(' ')
    if len(parts) > 1 and len(parts[1]) == 5:
        s = s + ':00'
    return s


def fmt_field(dt):
    if not dt:
        return None
    try:
        return dt.isoformat()
    except Exception:
        return str(dt)


def fmt_field_display(dt):
    if not dt:
        return ''
    if hasattr(dt, 'strftime'):
        return dt.strftime('%d/%m/%Y')
    return str(dt)


def humanize_main_date(start_dt):
    if not start_dt:
        return ''
    try:
        if isinstance(start_dt, str):
            start_dt = datetime.fromisoformat(start_dt.replace('T', ' '))
        today = datetime.now().date()
        d = start_dt.date()
        delta_days = (d - today).days
        if delta_days == 0:
            return 'Hoy'
        if delta_days == 1:
            return 'Mañana'
        if 1 < delta_days <= 7:
            return f'En {delta_days} días'
        return d.strftime('%d/%m/%Y')
    except Exception:
        return fmt_field_display(start_dt)


def build_image_url(image_field):
    """Construye la URL pública de una imagen almacenada.

    Reglas:
    - Si es una URL absoluta (http/https), devolverla tal cual.
    - Si comienza con '/', devolverla tal cual (ya es ruta pública).
    - Si comienza con 'static/', devolver '/'+campo (p.ej. 'static/uploads/x' -> '/static/uploads/x').
    - En otro caso, asumir que es el nombre de archivo en 'static/' y devolver '/static/<value>'.
    """
    if not image_field:
        return ''
    if isinstance(image_field, str) and (image_field.startswith('http://') or image_field.startswith('https://')):
        return image_field
    if image_field.startswith('/'):
        return image_field
    if image_field.startswith('static/'):
        return '/' + image_field
    return '/' + os.path.join('static', image_field).replace('\\', '/')


def require_login_for_panel(app):
    @app.before_request
    def _before_request():
        try:
            path = request.path
        except Exception:
            return None
        # Rutas públicas del panel
        public_panel_paths = ['/panel/avisos', '/api/clima']
        if path.startswith('/panel') and path not in public_panel_paths:
            if not current_user.is_authenticated:
                return redirect(url_for('login', next=request.url))


def handle_needs_login(app):
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


def register_routes(app):
    @app.route('/')
    @app.route('/home')
    def home():
        error_message = None
        error_type = None
        try:
            db = connectToMySQL(os.environ.get('DB_NAME', 'panel_informativo'))
            all_rows = db.query_db('SELECT * FROM notice ORDER BY idnotice DESC')
            if all_rows:
                avisos_con_fecha = []
                avisos_sin_fecha = []
                for r in all_rows:
                    if r.get('start_date'):
                        avisos_con_fecha.append(r)
                    else:
                        avisos_sin_fecha.append(r)
                now = datetime.now()

                def calcular_proximidad(aviso):
                    try:
                        fecha_inicio = aviso.get('start_date')
                        if fecha_inicio:
                            if isinstance(fecha_inicio, str):
                                fecha_inicio = datetime.fromisoformat(fecha_inicio.replace('T', ' '))
                            diff = abs((fecha_inicio - now).days)
                            return diff if fecha_inicio >= now else diff + 1000
                        return 9999
                    except Exception:
                        return 9999

                avisos_con_fecha.sort(key=calcular_proximidad)
                avisos_ordenados = avisos_con_fecha[:4]
                if len(avisos_ordenados) < 4:
                    faltan = 4 - len(avisos_ordenados)
                    avisos_ordenados = avisos_ordenados + avisos_sin_fecha[:faltan]

                if avisos_ordenados:
                    r = avisos_ordenados[0]
                    imagen_main = build_image_url(r.get('image_url')) if r.get('image_url') else '/static/main_panel/img/logo.png'
                    main_card = {
                        'titulo': r.get('name_notice', 'Se acerca el 18, con ello<br>actividades recreativas<br>¡Pasalo chancho!'),
                        'imagen_url': imagen_main,
                        'id': str(r.get('idnotice')),
                        'etiqueta_fecha': humanize_main_date(r.get('start_date')),
                    }
                    eventos = []
                    main_card_id = r.get('idnotice')
                    for r in avisos_ordenados[1:]:
                        if len(eventos) >= 3:
                            break
                        if r.get('idnotice') != main_card_id:
                            eventos.append({
                                'titulo': r.get('name_notice', ''),
                                'fecha_inicio': fmt_field_display(r.get('start_date')),
                                'fecha_fin': fmt_field_display(r.get('end_date')),
                                'imagen_url': (build_image_url(r.get('image_url')) if r.get('image_url') else '/static/main_panel/img/logo.png'),
                                'id': str(r.get('idnotice')),
                            })
                else:
                    main_card = {
                        'titulo': 'Se acerca el 18, con ello<br>actividades recreativas<br>¡Pasalo chancho!',
                        'imagen_url': 'https://storage.googleapis.com/chile-travel-cdn/2021/03/fiestas-patrias-shutterstock_703979611.jpg',
                    }
                    eventos = [{
                        'titulo': 'Próximamente más noticias',
                        'fecha_inicio': '',
                        'fecha_fin': '',
                        'imagen_url': 'https://images.unsplash.com/photo-1517649763962-0c623066013b?auto=format&fit=crop&w=400&q=80',
                        'id': 'placeholder_0',
                    }]
            else:
                main_card = {
                    'titulo': 'No hay noticias disponibles<br>en la base de datos',
                    'imagen_url': '/static/main_panel/img/logo.png',
                    'etiqueta_fecha': '',
                    'id': 'empty_database'
                }
                eventos = []
        except Exception as e:
            error_message = str(e)
            error_type = 'database_connection'
            current_app.logger.exception('Error en home')
            main_card = {
                'titulo': f'Error de conexión<br>{error_message}',
                'imagen_url': '/static/main_panel/img/logo.png',
                'etiqueta_fecha': '',
                'id': f'error_{error_type}'
            }
            eventos = []

        try:
            clima = obtener_clima_nueva_imperial()
        except Exception as e:
            current_app.logger.exception('Error obteniendo clima')
            clima = {'temperatura_actual': 15, 'icono_bootstrap': 'bi-sun', 'descripcion': 'Soleado'}

        return render_template('main_panel/home.html', eventos=eventos, main_card=main_card, clima=clima, error_message=error_message, error_type=error_type)


    @app.route('/api/clima', methods=['GET'])
    def get_clima():
        """API pública para obtener datos del clima"""
        try:
            clima = obtener_clima_nueva_imperial()
            return jsonify(clima)
        except Exception as e:
            current_app.logger.exception('Error en get_clima')
            return jsonify({'error': str(e), 'temperatura_actual': 15, 'icono_bootstrap': 'bi-sun', 'descripcion': 'Soleado'}), 500


    @app.route('/panel/avisos', methods=['GET'])
    def get_avisos():
        """API pública para obtener todos los avisos ordenados por proximidad de fecha"""
        try:
            db = connectToMySQL(os.environ.get('DB_NAME', 'panel_informativo'))
            rows = db.query_db('SELECT * FROM notice ORDER BY idnotice DESC')
            
            mapped_all = []
            avisos_con_fecha = []
            avisos_sin_fecha = []

            for r in rows:
                image_field = r.get('image_url')
                aviso_data = {
                    'id': str(r.get('idnotice')),
                    'title': r.get('name_notice'),
                    'description': r.get('description') if 'description' in r else '',
                    'image_url': build_image_url(image_field) if image_field else '',
                    'fecha_inicio': fmt_field(r.get('start_date')),
                    'fecha_fin': fmt_field(r.get('end_date')),
                }
                mapped_all.append(aviso_data)

                if r.get('start_date'):
                    avisos_con_fecha.append((aviso_data, r.get('start_date')))
                else:
                    avisos_sin_fecha.append(aviso_data)

            now = datetime.now()

            def calcular_proximidad_api(item):
                aviso_data, fecha_inicio = item
                try:
                    if isinstance(fecha_inicio, str):
                        fecha_inicio = datetime.fromisoformat(fecha_inicio.replace('T', ' '))
                    diff = abs((fecha_inicio - now).days)
                    return diff if fecha_inicio >= now else diff + 1000
                except Exception:
                    return 9999

            avisos_con_fecha.sort(key=calcular_proximidad_api)
            mapped = [item[0] for item in avisos_con_fecha] + avisos_sin_fecha

            return jsonify(mapped)
        except Exception as e:
            current_app.logger.exception('Error en get_avisos')
            return jsonify({'error': str(e)}), 500


    @app.route('/panel/avisos_hash', methods=['GET'])
    def get_avisos_hash():
        """Devuelve un hash representando el estado actual de los avisos.
        El frontend puede usarlo para detectar cambios y recargar.
        """
        try:
            db = connectToMySQL(os.environ.get('DB_NAME', 'panel_informativo'))
            rows = db.query_db('SELECT idnotice, name_notice, start_date, end_date, image_url FROM notice ORDER BY idnotice')
            parts = []
            for r in rows:
                parts.append(
                    f"{r.get('idnotice')}|{r.get('name_notice') or ''}|{fmt_field(r.get('start_date')) or ''}|{fmt_field(r.get('end_date')) or ''}|{r.get('image_url') or ''}"
                )
            payload = '\n'.join(parts)
            digest = hashlib.md5(payload.encode('utf-8')).hexdigest()
            return jsonify({'hash': digest})
        except Exception as e:
            current_app.logger.exception('Error en get_avisos_hash')
            return jsonify({'error': str(e)}), 500


    @app.route('/register', methods=['GET', 'POST'])
    def register():
        """Página de registro de usuarios"""
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

                db.query_db(
                    'INSERT INTO usuarios (username, password, email, created_at, updated_at) VALUES (%(username)s, %(password)s, %(email)s, NOW(), NOW())',
                    {'username': username, 'password': hashed, 'email': email}
                )
                flash('Registro exitoso. Ya puedes ingresar.')
                return redirect(url_for('login'))
            except Exception as e:
                current_app.logger.exception('Error en registro')
                flash(f'Error al conectar con la base de datos: {e}')
                return redirect(url_for('register'))

        return render_template('registrer_panel/registrer.html')


    @app.route('/logout')
    @login_required
    def logout():
        """Cerrar sesión"""
        logout_user()
        session.clear()
        return redirect(url_for('home'))


    @app.route('/panel')
    @login_required
    def panel():
        """Panel de administración principal"""
        if not current_user.is_authenticated:
            return redirect(url_for('login', next=request.path))
        
        try:
            db = connectToMySQL(os.environ.get('DB_NAME', 'panel_informativo'))
            rows = db.query_db('SELECT * FROM notice ORDER BY idnotice DESC')
            mapped = []
            for r in rows:
                mapped.append({
                    'id': str(r.get('idnotice')),
                    'title': r.get('name_notice'),
                    'description': r.get('description') if 'description' in r else '',
                    'image_url': build_image_url(r.get('image_url')) if r.get('image_url') else '',
                    'fecha_inicio': fmt_field(r.get('start_date')),
                    'fecha_fin': fmt_field(r.get('end_date')),
                })
            return render_template('admin_panel/panel.html', avisos=mapped)
        except Exception as e:
            current_app.logger.exception('Error cargando panel')
            flash(f'Error cargando avisos desde la base de datos: {e}')
            return render_template('admin_panel/panel.html', avisos=avisos)


    @app.route('/edit_panel')
    @login_required
    def edit_panel():
        """Panel de edición (redirige al panel principal)"""
        if not current_user.is_authenticated:
            return redirect(url_for('login', next=request.path))
        return render_template('admin_panel/panel.html', avisos=avisos)


    @app.route('/panel/add', methods=['POST'])
    @login_required
    def add_aviso():
        """API para añadir un aviso (JSON)"""
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
        """API para editar un aviso existente"""
        if not request.is_json:
            return jsonify({"error": "El contenido debe ser JSON"}), 400

        data = request.get_json()
        
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
            
            set_clauses = []
            params = {'id': aviso_id}

            if 'title' in data:
                set_clauses.append('name_notice = %(name)s')
                params['name'] = data.get('title')
            
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
                    fallback_clauses = [c for c in set_clauses if not c.startswith('description') and not c.startswith('image_url')]
                    if fallback_clauses:
                        sql2 = 'UPDATE notice SET ' + ', '.join(fallback_clauses) + ' WHERE idnotice = %(id)s'
                        db.query_db(sql2, params)

            row = db.query_db('SELECT * FROM notice WHERE idnotice = %(id)s', {'id': aviso_id})
            r = row[0] if row else rows[0]

            mapped = {
                'id': str(r.get('idnotice')),
                'title': r.get('name_notice'),
                'description': r.get('description') if 'description' in r else '',
                'image_url': r.get('image_url') if 'image_url' in r else '',
                'fecha_inicio': fmt_field(r.get('start_date')),
                'fecha_fin': fmt_field(r.get('end_date')),
            }

            for aviso in avisos:
                if aviso.get('id') == mapped['id']:
                    aviso.update(mapped)
                    break

            return jsonify(mapped)
        except Exception as e:
            current_app.logger.exception('Error en edit_aviso')
            return jsonify({'error': str(e)}), 500


    @app.route('/panel/delete/<int:aviso_id>', methods=['DELETE'])
    @login_required
    def delete_aviso(aviso_id):
        """API para eliminar un aviso"""
        try:
            db = connectToMySQL(os.environ.get('DB_NAME', 'panel_informativo'))
            rows = db.query_db('SELECT * FROM notice WHERE idnotice = %(id)s', {'id': aviso_id})
            if not rows:
                return jsonify({"error": "Aviso no encontrado"}), 404
            
            row = rows[0]
            img_field = row.get('image_url') if 'image_url' in row else None
            
            if img_field:
                filename = os.path.basename(img_field)
                base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
                upload_folder = os.path.join(base_dir, UPLOAD_FOLDER)
                file_path = os.path.join(upload_folder, filename)
                try:
                    if os.path.exists(file_path):
                        os.remove(file_path)
                except Exception:
                    pass
            
            db.query_db('DELETE FROM notice WHERE idnotice = %(id)s', {'id': aviso_id})
        except Exception as e:
            current_app.logger.exception('Error en delete_aviso')
            return jsonify({'error': f'Error al eliminar en la base de datos: {e}'}), 500

        aviso_index = next((index for (index, aviso) in enumerate(avisos) if aviso['id'] == aviso_id), None)
        aviso_eliminado = None
        if aviso_index is not None:
            aviso_eliminado = avisos.pop(aviso_index)

        return jsonify({'deleted': aviso_id, 'removed_from_memory': aviso_eliminado is not None})


    @app.route('/panel/upload', methods=['POST'])
    @login_required
    def upload_news():
        """Subir una nueva noticia con imagen"""
        if 'photo' not in request.files:
            flash('No se ha enviado ninguna imagen')
            return redirect(url_for('panel'))

        file = request.files['photo']
        title = request.form.get('title')
        fecha_inicio = request.form.get('fecha_inicio')
        fecha_fin = request.form.get('fecha_fin')

        try:
            current_app.logger.info(f"upload_news called: title={title!r}, fecha_inicio={fecha_inicio!r}, fecha_fin={fecha_fin!r}, file_present={bool(file and getattr(file, 'filename', None))}")
        except Exception:
            pass

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
        image_url_db = ''
        
        if file and file.filename:
            if not allowed_file(file.filename):
                flash('Tipo de archivo no permitido. Usa png/jpg/jpeg/gif/webp')
                return redirect(url_for('panel'))
            
            filename = secure_filename(file.filename)
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            upload_folder = os.path.join(base_dir, UPLOAD_FOLDER)
            os.makedirs(upload_folder, exist_ok=True)
            save_path = os.path.join(upload_folder, filename)
            
            try:
                file.save(save_path)
            except Exception as e:
                current_app.logger.exception('Error guardando archivo')
                flash(f'Error guardando archivo: {e}')
                return redirect(url_for('panel'))
            
            image_url_db = os.path.join('static', 'uploads', filename).replace('\\', '/')

        try:
            db = connectToMySQL(os.environ.get('DB_NAME', 'panel_informativo'))
            
            start_sql = fmt_mysql(fecha_inicio)
            end_sql = fmt_mysql(fecha_fin)
            
            try:
                if filename:
                    insert_result = db.query_db(
                        'INSERT INTO notice (name_notice, start_date, end_date, image_url) VALUES (%(name)s, %(start)s, %(end)s, %(img)s)',
                        {'name': title, 'start': start_sql, 'end': end_sql, 'img': image_url_db}
                    )
                else:
                    insert_result = db.query_db(
                        'INSERT INTO notice (name_notice, start_date, end_date) VALUES (%(name)s, %(start)s, %(end)s)',
                        {'name': title, 'start': start_sql, 'end': end_sql}
                    )
            except Exception:
                insert_result = db.query_db(
                    'INSERT INTO notice (name_notice, start_date, end_date) VALUES (%(name)s, %(start)s, %(end)s)',
                    {'name': title, 'start': start_sql, 'end': end_sql}
                )

            row = db.query_db('SELECT * FROM notice ORDER BY idnotice DESC LIMIT 1')
            inserted = row[0] if row else None

            nuevo_aviso = {
                'id': str(inserted['idnotice']) if inserted else str(len(avisos) + 1),
                'title': title,
                'description': request.form.get('description', ''),
                'image_url': image_url_db if image_url_db else '',
                'fecha_inicio': fecha_inicio,
                'fecha_fin': fecha_fin,
                'created_at': datetime.now().isoformat(),
            }
            avisos.append(nuevo_aviso)
            flash('Noticia añadida correctamente')
            return redirect(url_for('panel'))
            
        except Exception as e:
            current_app.logger.exception('Error en upload_news')
            flash(f'Error al guardar en la base de datos: {e}')
            return redirect(url_for('panel'))


    @app.route('/panel/upload_image/<int:aviso_id>', methods=['POST'])
    @login_required
    def upload_image_edit(aviso_id):
        """Endpoint para permitir subir/actualizar la imagen de un aviso ya existente desde el modal de edición"""
        if 'photo' not in request.files:
            return jsonify({'error': 'No se ha enviado ningún fichero'}), 400

        file = request.files['photo']
        if not file or not file.filename:
            return jsonify({'error': 'Fichero inválido'}), 400

        if not allowed_file(file.filename):
            return jsonify({'error': 'Tipo de archivo no permitido. Usa png/jpg/jpeg/gif/webp'}), 400

        filename = secure_filename(file.filename)
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        upload_folder = os.path.join(base_dir, UPLOAD_FOLDER)
        os.makedirs(upload_folder, exist_ok=True)
        save_path = os.path.join(upload_folder, filename)
        
        try:
            file.save(save_path)
        except Exception as e:
            current_app.logger.exception('Error guardando archivo al editar')
            return jsonify({'error': str(e)}), 500

        image_url_db = os.path.join('static', 'uploads', filename).replace('\\', '/')

        title = request.form.get('title')
        fecha_inicio = request.form.get('fecha_inicio')
        fecha_fin = request.form.get('fecha_fin')

        try:
            db = connectToMySQL(os.environ.get('DB_NAME', 'panel_informativo'))
            
            set_clauses = ['image_url = %(img)s']
            params = {'img': image_url_db, 'id': aviso_id}

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
            current_app.logger.exception('Error actualizando imagen en BD')
            return jsonify({'error': str(e)}), 500