"""
Controlador principal del panel informativo
"""
from flask import render_template, request, redirect, url_for, flash, jsonify, session
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from datetime import datetime
import os
import hashlib

# Usar el helper mysqlconnection.py (pymysql)
from flask_app.config.mysqlconnection import connectToMySQL

# Password hashing
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

# Importar función del clima
from flask_app.clima import obtener_clima_nueva_imperial

# ============================================================================
# CONFIGURACIÓN DE LA APLICACIÓN
# ============================================================================

# Carpeta para subir imágenes (relativa a la carpeta raíz de la app)
UPLOAD_FOLDER = os.environ.get('UPLOAD_FOLDER', 'static/uploads')

# Extensiones permitidas (opcional, se puede ampliar)
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

# Clave maestra requerida para crear usuarios desde el formulario de registro.
# Se puede sobreescribir con la variable de entorno MASTER_KEY si se desea.
MASTER_KEY = os.environ.get('MASTER_KEY', 'complejoprincipedegalescuenta25')

# Lista temporal para almacenar los avisos (en producción usar una base de datos)
avisos = []

# ============================================================================
# MODELOS Y UTILIDADES
# ============================================================================

class User(UserMixin):
    def __init__(self, username):
        self.username = username
        self.id = username

    def get_id(self):
        return self.username


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def fmt_mysql(dt_str):
    """Formatea una fecha ISO para MySQL"""
    if not dt_str:
        return None
    s = dt_str.replace('T', ' ')
    parts = s.split(' ')
    if len(parts) > 1 and len(parts[1]) == 5:
        s = s + ':00'
    return s


def fmt_field(dt):
    """Formatea un campo de fecha para respuesta JSON"""
    if not dt:
        return None
    try:
        return dt.isoformat()
    except Exception:
        return str(dt)


def fmt_field_display(dt):
    """Formatea un campo de fecha para mostrar (DD/MM/YYYY)"""
    if not dt:
        return ""
    if hasattr(dt, 'strftime'):
        return dt.strftime('%d/%m/%Y')
    return str(dt)


def humanize_main_date(start_dt):
    """Devuelve texto humano para la tarjeta principal según proximidad.
    - Hoy / Mañana
    - En X días (<= 7 días)
    - Si > 7 días o pasado, fecha dd/mm/YYYY
    """
    if not start_dt:
        return ""
    try:
        if isinstance(start_dt, str):
            # Normalizar 'YYYY-MM-DDTHH:MM' o 'YYYY-MM-DD HH:MM:SS'
            start_dt = datetime.fromisoformat(start_dt.replace('T', ' '))
        today = datetime.now().date()
        d = start_dt.date()
        delta_days = (d - today).days

        if delta_days == 0:
            return "Hoy"
        if delta_days == 1:
            return "Mañana"
        if 1 < delta_days <= 7:
            return f"En {delta_days} días"
        # Para pasado o más de una semana, mostrar fecha
        return d.strftime('%d/%m/%Y')
    except Exception:
        return fmt_field_display(start_dt)


# ============================================================================
# MIDDLEWARE Y HANDLERS
# ============================================================================

def require_login_for_panel(app):
    """Proteger cualquier ruta que comience con /panel excepto las excepciones públicas"""
    @app.before_request
    def before_request():
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


def handle_needs_login(app):
    """Cuando un usuario no autorizado intenta acceder a una ruta protegida,
    redirigimos al login y preservamos la ruta solicitada en el parámetro "next"."""
    @app.route('/login', methods=['GET', 'POST'])
    def login():
        """Página de inicio de sesión"""
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


# ============================================================================
# RUTAS PÚBLICAS
# ============================================================================

def register_routes(app):
    """Registra todas las rutas de la aplicación"""
    
    @app.route('/')
    @app.route('/home')
    def home():
        """Página principal que muestra noticias priorizadas por proximidad de fecha"""
        try:
            db = connectToMySQL(os.environ.get('DB_NAME', 'panel_informativo'))
            
            # Obtener todos los avisos para procesarlos por proximidad de fecha
            all_rows = db.query_db('SELECT * FROM notice ORDER BY idnotice DESC')
            
            if all_rows:
                # Separar avisos con fecha y sin fecha
                avisos_con_fecha = []
                avisos_sin_fecha = []
                
                for r in all_rows:
                    if r.get('start_date'):
                        avisos_con_fecha.append(r)
                    else:
                        avisos_sin_fecha.append(r)
                
                # Ordenar por proximidad sin limitar por rango; priorizar próximos
                from datetime import datetime, timedelta
                now = datetime.now()

                def calcular_proximidad(aviso):
                    try:
                        fecha_inicio = aviso.get('start_date')
                        if fecha_inicio:
                            if isinstance(fecha_inicio, str):
                                fecha_inicio = datetime.fromisoformat(fecha_inicio.replace('T', ' '))
                            # Calcular diferencia absoluta en días
                            diff = abs((fecha_inicio - now).days)
                            # Priorizar eventos futuros cercanos
                            if fecha_inicio >= now:
                                return diff
                            else:
                                # Eventos pasados tienen menor prioridad
                                return diff + 1000
                        return 9999  # Sin fecha, menor prioridad
                    except:
                        return 9999
                # Ordenar todos los que tienen fecha por proximidad y tomar los 4 más próximos
                avisos_con_fecha.sort(key=calcular_proximidad)
                avisos_ordenados = avisos_con_fecha[:4]
                # Completar con sin fecha si faltan
                if len(avisos_ordenados) < 4:
                    faltan = 4 - len(avisos_ordenados)
                    avisos_ordenados = avisos_ordenados + avisos_sin_fecha[:faltan]
                
                # Obtener el aviso más próximo para el recuadro principal
                if avisos_ordenados:
                    r = avisos_ordenados[0]
                    imagen_main = r.get('image_url') if r.get('image_url') else 'static/main_panel/img/logo.png'
                    main_card = {
                        'titulo': r.get('name_notice', 'Se acerca el 18, con ello<br>actividades recreativas<br>¡Pasalo chancho!'),
                        'imagen_url': imagen_main,
                        'id': r.get('idnotice'),  # Agregar ID para evitar duplicados
                        'etiqueta_fecha': humanize_main_date(r.get('start_date')),
                    }
                    
                    # Obtener las siguientes noticias para las tarjetas laterales (evitando duplicados)
                    eventos = []
                    main_card_id = r.get('idnotice')
                    
                    # Buscar avisos únicos para las tarjetas laterales
                    for r in avisos_ordenados[1:]:  # Empezar desde el segundo aviso
                        if len(eventos) >= 3:  # Solo necesitamos 3 tarjetas laterales
                            break
                            
                        # Verificar que no sea el mismo que el principal
                        if r.get('idnotice') != main_card_id:
                            eventos.append({
                                'titulo': r.get('name_notice', ''),
                                'fecha_inicio': fmt_field_display(r.get('start_date')),
                                'fecha_fin': fmt_field_display(r.get('end_date')),
                                'imagen_url': (r.get('image_url') if r.get('image_url') else 'static/main_panel/img/logo.png'),
                                'id': r.get('idnotice'),  # Agregar ID para JavaScript
                            })
                    
                    # No agregar placeholders cuando sí hay avisos
                else:
                    # Fallback si no hay avisos
                    main_card = {
                        'titulo': 'Se acerca el 18, con ello<br>actividades recreativas<br>¡Pasalo chancho!',
                        'imagen_url': 'https://storage.googleapis.com/chile-travel-cdn/2021/03/fiestas-patrias-shutterstock_703979611.jpg',
                    }
                    # Mostrar un solo placeholder cuando no hay ningún aviso
                    eventos = [{
                        'titulo': 'Próximamente más noticias',
                        'fecha_inicio': '',
                        'fecha_fin': '',
                        'imagen_url': 'https://images.unsplash.com/photo-1517649763962-0c623066013b?auto=format&fit=crop&w=400&q=80',
                        'id': 'placeholder_0',
                    }]
            else:
                # Fallback si no hay avisos en la base de datos
                main_card = {
                    'titulo': 'Se acerca el 18, con ello<br>actividades recreativas<br>¡Pasalo chancho!',
                    'imagen_url': 'https://storage.googleapis.com/chile-travel-cdn/2021/03/fiestas-patrias-shutterstock_703979611.jpg',
                }
                eventos = []
                
        except Exception as e:
            # Fallback en caso de error con la base de datos
            print(f"Error en home(): {e}")  # Para debug
            main_card = {
                'titulo': 'Se acerca el 18, con ello<br>actividades recreativas<br>¡Pasalo chancho!',
                'imagen_url': 'https://storage.googleapis.com/chile-travel-cdn/2021/03/fiestas-patrias-shutterstock_703979611.jpg',
            }
            eventos = []
        
        # Obtener datos del clima
        try:
            clima = obtener_clima_nueva_imperial()
        except Exception as e:
            print(f"Error obteniendo clima: {e}")
            # Valores por defecto en caso de error
            clima = {
                "temperatura_actual": 15,
                "icono_bootstrap": "bi-sun",
                "descripcion": "Soleado"
            }
            
        return render_template('main_panel/home.html', eventos=eventos, main_card=main_card, clima=clima)


    @app.route('/api/clima', methods=['GET'])
    def get_clima():
        """API pública para obtener datos del clima"""
        try:
            clima = obtener_clima_nueva_imperial()
            return jsonify(clima)
        except Exception as e:
            return jsonify({
                "error": str(e),
                "temperatura_actual": 15,
                "icono_bootstrap": "bi-sun",
                "descripcion": "Soleado"
            }), 500

    @app.route('/panel/avisos', methods=['GET'])
    def get_avisos():
        """API pública para obtener todos los avisos ordenados por proximidad de fecha"""
        try:
            db = connectToMySQL(os.environ.get('DB_NAME', 'panel_informativo'))
            rows = db.query_db('SELECT * FROM notice ORDER BY idnotice DESC')
            
            # Mapear todos los avisos (estructura que usa el cliente)
            mapped_all = []
            avisos_con_fecha = []
            avisos_sin_fecha = []

            for r in rows:
                aviso_data = {
                    'id': r.get('idnotice'),
                    'title': r.get('name_notice'),
                    'description': r.get('description') if 'description' in r else '',
                    'image_url': r.get('image_url') if 'image_url' in r else '',
                    'fecha_inicio': fmt_field(r.get('start_date')),
                    'fecha_fin': fmt_field(r.get('end_date')),
                }
                mapped_all.append(aviso_data)

                # Mantener la separación por fecha para la lógica actual
                if r.get('start_date'):
                    avisos_con_fecha.append((aviso_data, r.get('start_date')))
                else:
                    avisos_sin_fecha.append(aviso_data)

            # Ordenar por proximidad SIN límite de rango, priorizando próximos
            from datetime import datetime
            now = datetime.now()

            def calcular_proximidad_api(item):
                aviso_data, fecha_inicio = item
                try:
                    if isinstance(fecha_inicio, str):
                        fecha_inicio = datetime.fromisoformat(fecha_inicio.replace('T', ' '))
                    diff = abs((fecha_inicio - now).days)
                    return diff if fecha_inicio >= now else diff + 1000
                except:
                    return 9999

            avisos_con_fecha.sort(key=calcular_proximidad_api)
            mapped = [item[0] for item in avisos_con_fecha] + avisos_sin_fecha

            return jsonify(mapped)
        except Exception as e:
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
            return jsonify({'error': str(e)}), 500


    # ============================================================================
    # RUTAS DE AUTENTICACIÓN
    # ============================================================================

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


    # ============================================================================
    # RUTAS DEL PANEL DE ADMINISTRACIÓN
    # ============================================================================

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


    @app.route('/edit_panel')
    @login_required
    def edit_panel():
        """Panel de edición (redirige al panel principal)"""
        if not current_user.is_authenticated:
            return redirect(url_for('login', next=request.path))
        return render_template('admin_panel/panel.html', avisos=avisos)


    # ============================================================================
    # RUTAS API - GESTIÓN DE AVISOS
    # ============================================================================

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
        
        # Validar fechas si vienen en la petición
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
                    # Fallback: intentar actualizar solo columnas básicas si alguna columna no existe
                    fallback_clauses = [c for c in set_clauses if not c.startswith('description') and not c.startswith('image_url')]
                    if fallback_clauses:
                        sql2 = 'UPDATE notice SET ' + ', '.join(fallback_clauses) + ' WHERE idnotice = %(id)s'
                        db.query_db(sql2, params)

            # Leer fila actualizada
            row = db.query_db('SELECT * FROM notice WHERE idnotice = %(id)s', {'id': aviso_id})
            r = row[0] if row else rows[0]

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
        """API para eliminar un aviso"""
        try:
            db = connectToMySQL(os.environ.get('DB_NAME', 'panel_informativo'))
            rows = db.query_db('SELECT * FROM notice WHERE idnotice = %(id)s', {'id': aviso_id})
            if not rows:
                return jsonify({"error": "Aviso no encontrado"}), 404
            
            row = rows[0]
            img_field = row.get('image_url') if 'image_url' in row else None
            
            # Intentar eliminar la imagen física
            if img_field:
                filename = os.path.basename(img_field)
                upload_folder = os.path.join(app.root_path, UPLOAD_FOLDER)
                file_path = os.path.join(upload_folder, filename)
                try:
                    if os.path.exists(file_path):
                        os.remove(file_path)
                except Exception:
                    pass
            
            # Eliminar de la base de datos
            db.query_db('DELETE FROM notice WHERE idnotice = %(id)s', {'id': aviso_id})
        except Exception as e:
            return jsonify({'error': f'Error al eliminar en la base de datos: {e}'}), 500

        # Eliminar de la memoria local
        aviso_index = next((index for (index, aviso) in enumerate(avisos) if aviso['id'] == aviso_id), None)
        aviso_eliminado = None
        if aviso_index is not None:
            aviso_eliminado = avisos.pop(aviso_index)

        return jsonify({'deleted': aviso_id, 'removed_from_memory': aviso_eliminado is not None})


    # ============================================================================
    # RUTAS DE SUBIDA DE ARCHIVOS
    # ============================================================================

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

        filename = None
        image_url = ''
        
        if file and file.filename:
            if not allowed_file(file.filename):
                flash('Tipo de archivo no permitido. Usa png/jpg/jpeg/gif/webp')
                return redirect(url_for('panel'))
            
            filename = secure_filename(file.filename)
            upload_folder = os.path.join(app.root_path, UPLOAD_FOLDER)
            os.makedirs(upload_folder, exist_ok=True)
            save_path = os.path.join(upload_folder, filename)
            
            try:
                file.save(save_path)
            except Exception as e:
                app.logger.exception('Error guardando archivo')
                flash(f'Error guardando archivo: {e}')
                return redirect(url_for('panel'))
            
            image_url = url_for('static', filename=f'uploads/{filename}')

        try:
            db = connectToMySQL(os.environ.get('DB_NAME', 'panel_informativo'))
            
            start_sql = fmt_mysql(fecha_inicio)
            end_sql = fmt_mysql(fecha_fin)
            
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
                    
            except Exception:
                # Fallback por si la tabla no tiene columna image_url
                insert_result = db.query_db(
                    'INSERT INTO notice (name_notice, start_date, end_date) VALUES (%(name)s, %(start)s, %(end)s)',
                    {'name': title, 'start': start_sql, 'end': end_sql}
                )
                try:
                    app.logger.info(f'Fallback insert result: {insert_result!r}')
                except Exception:
                    pass

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
        """Endpoint para permitir subir/actualizar la imagen de un aviso ya existente desde el modal de edición"""
        if 'photo' not in request.files:
            return jsonify({'error': 'No se ha enviado ningún fichero'}), 400

        file = request.files['photo']
        if not file or not file.filename:
            return jsonify({'error': 'Fichero inválido'}), 400

        if not allowed_file(file.filename):
            return jsonify({'error': 'Tipo de archivo no permitido. Usa png/jpg/jpeg/gif/webp'}), 400

        filename = secure_filename(file.filename)
        upload_folder = os.path.join(app.root_path, UPLOAD_FOLDER)
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
