from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_mysqldb import MySQL
from functools import wraps
import hashlib
from flask_mail import Mail, Message
from itsdangerous import URLSafeTimedSerializer

import hashlib
app = Flask(__name__)

# Mysql Connection
app.config["MYSQL_HOST"] = "localhost"
app.config["MYSQL_USER"] = "root"
app.config["MYSQL_PASSWORD"] = ""  
app.config["MYSQL_DB"] = "motorepuestos"   
app.config["MYSQL_PORT"] = 3307
mysql = MySQL(app)



# Settings
app.secret_key = "mysecretkey"



# Configuracion de Gmail
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'jbazurto3977@utm.edu.ec'
app.config['MAIL_PASSWORD'] = 'nfrk hihs sfcz ksif'  
app.config['MAIL_DEFAULT_SENDER'] = 'jbazurto3977@utm.edu.ec'

mail = Mail(app)
serializer = URLSafeTimedSerializer(app.secret_key)

@app.route("/forgot_password", methods=["GET", "POST"])
def forgot_password():
    if request.method == "POST":
        email = request.form["email"]
        cur = mysql.connection.cursor()
        cur.execute("""
            SELECT id_persona, nombres, apellidos 
            FROM personas 
            WHERE correo = %s AND tipo_persona = 'EMPLEADO' AND estado = 'ACTIVO'
        """, (email,))
        empleado = cur.fetchone()
        
        if empleado:
            # Token válido por 1 hora
            token = serializer.dumps(email, salt='reset')
            link = url_for('reset_password', token=token, _external=True)
            
            msg = Message('Recuperación de contraseña - Motorepuestos',
                          recipients=[email])
            msg.body = f"""Hola {empleado[1]} {empleado[2]},

Para restablecer tu contraseña, haz clic en el siguiente enlace (válido por 1 hora):
{link}

Si no solicitaste este cambio, ignora el mensaje.

Saludos,
Sistema Motorepuestos"""
            mail.send(msg)
            flash("Te hemos enviado un enlace de recuperación a tu correo electrónico.")
        else:
            # Por seguridad, no revelamos si el correo existe
            flash("Si el correo pertenece a un empleado activo, recibirás instrucciones.")
        return redirect(url_for('login'))
    
    return render_template("forgot_password.html")


@app.route("/reset_password/<token>", methods=["GET", "POST"])
def reset_password(token):
    try:
        email = serializer.loads(token, salt='reset', max_age=3600)
        print(f"CORREO DEL TOKEN: '{email}'")  
    except Exception as e:
        print("Error al decodificar token:", e)
        flash("El enlace es inválido o ha expirado. Solicita uno nuevo.")
        return redirect(url_for('forgot_password'))
    
    if request.method == "POST":
        nueva = request.form["contrasena"]
        confirmar = request.form["confirmar"]
        
        if nueva != confirmar:
            flash("Las contraseñas no coinciden.")
            return redirect(url_for('reset_password', token=token))
        
        if len(nueva) < 6:
            flash("La contraseña debe tener al menos 6 caracteres.")
            return redirect(url_for('reset_password', token=token))
        
        hash_pwd = hashlib.sha256(nueva.encode()).hexdigest()
        
        cur = mysql.connection.cursor()
        # Ejecuta la actualización y guarda cuántas filas se modificaron
        cur.execute("""
            UPDATE personas SET contrasena = %s 
            WHERE correo = %s AND tipo_persona = 'EMPLEADO'
        """, (hash_pwd, email))
        filas_actualizadas = cur.rowcount   # número de filas afectadas
        mysql.connection.commit()
        
        print(f"Filas actualizadas: {filas_actualizadas}") 
        
        if filas_actualizadas == 0:
            flash("No se encontró un empleado con ese correo exacto. Contacta al administrador.")
            return redirect(url_for('forgot_password'))
        
        flash("Contraseña actualizada correctamente. Ahora puedes iniciar sesión.")
        return redirect(url_for('login'))
    
    return render_template("reset_password.html", token=token)

























# Decorador para proteger rutas
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'empleado_id' not in session:
            flash("Debes iniciar sesión para acceder")
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# AUTH

@app.route("/login", methods=["GET", "POST"])
def login():
    if 'empleado_id' in session:
        return redirect(url_for('dashboard'))
    
    if request.method == "POST":
        usuario = request.form["usuario"]
        contrasena = request.form["contrasena"]
        contrasena_hash = hashlib.sha256(contrasena.encode()).hexdigest()

        cur = mysql.connection.cursor()
        cur.execute("""
            SELECT id_persona, nombres, apellidos, cargo 
            FROM personas 
            WHERE usuario = %s AND contrasena = %s 
              AND tipo_persona = 'EMPLEADO' AND estado = 'ACTIVO'
        """, (usuario, contrasena_hash))
        empleado = cur.fetchone()

        if empleado:
            session['empleado_id'] = empleado[0]
            session['empleado_nombre'] = f"{empleado[1]} {empleado[2]}"
            session['empleado_cargo'] = empleado[3]
            flash(f"Bienvenido, {empleado[1]}!")
            return redirect(url_for('dashboard'))
        else:
            flash("Usuario o contraseña incorrectos")
            return redirect(url_for('login'))

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("Sesión cerrada correctamente")
    return redirect(url_for('login'))


# DASHBOARD

@app.route("/dashboard")
@login_required
def dashboard():
    cur = mysql.connection.cursor()

    cur.execute("SELECT COUNT(*) FROM personas WHERE tipo_persona = 'CLIENTE'")
    total_clientes = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM personas WHERE tipo_persona = 'PROVEEDOR'")
    total_proveedores = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM personas WHERE tipo_persona = 'EMPLEADO'")
    total_empleados = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM productos")
    total_productos = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM compras")
    total_compras = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM ventas")
    total_ventas = cur.fetchone()[0]

    cur.execute("SELECT IFNULL(SUM(total_compra), 0) FROM compras")
    total_comprado = cur.fetchone()[0]

    cur.execute("SELECT IFNULL(SUM(total_venta), 0) FROM ventas")
    total_vendido = cur.fetchone()[0]

    cur.execute("""
        SELECT id_producto, nombre_producto, stock_actual, stock_minimo
        FROM productos
        WHERE stock_actual <= stock_minimo
    """)
    productos_bajo_stock = cur.fetchall()

    return render_template("dashboard.html",
        total_clientes=total_clientes,
        total_proveedores=total_proveedores,
        total_empleados=total_empleados,
        total_productos=total_productos,
        total_compras=total_compras,
        total_ventas=total_ventas,
        total_comprado=total_comprado,
        total_vendido=total_vendido,
        productos_bajo_stock=productos_bajo_stock
    )


# PERSONAS

@app.route("/")
@login_required
def Index():
    search = request.args.get('search', '').strip()
    cur = mysql.connection.cursor()
    
    if search:
        
        cur.execute("""
            SELECT * FROM personas 
            WHERE CAST(id_persona AS CHAR) LIKE %s 
               OR nombres LIKE %s 
               OR apellidos LIKE %s 
               OR cedula_ruc LIKE %s 
               OR correo LIKE %s
            ORDER BY id_persona DESC
        """, (f'%{search}%', f'%{search}%', f'%{search}%', f'%{search}%', f'%{search}%'))
    else:
        cur.execute("SELECT * FROM personas ORDER BY id_persona DESC")
    
    personas = cur.fetchall()
    return render_template("index.html", personas=personas, search=search)


@app.route("/add_persona", methods=["POST"])
def add_persona():
    if request.method == "POST":
        tipo_persona = request.form["tipo_persona"]
        nombres = request.form["nombres"]
        apellidos = request.form["apellidos"]
        cedula_ruc = request.form["cedula_ruc"].strip()
        telefono = request.form["telefono"]
        correo = request.form["correo"]
        direccion = request.form["direccion"]
        cargo = request.form["cargo"]

        if len(cedula_ruc) > 10:
            flash("La cédula no puede tener más de 10 caracteres")
            return redirect(url_for("Index"))

        if cedula_ruc == "":
            cedula_ruc = None

        cur = mysql.connection.cursor()

        if cedula_ruc != None:
            cur.execute("SELECT * FROM personas WHERE cedula_ruc = %s", (cedula_ruc,))
            persona = cur.fetchall()

            if len(persona) > 0:
                flash("La cédula ingresada ya está registrada")
                return redirect(url_for("Index"))

        cur.execute("""
            INSERT INTO personas 
            (tipo_persona, nombres, apellidos, cedula_ruc, telefono, correo, direccion, cargo)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, (tipo_persona, nombres, apellidos, cedula_ruc, telefono, correo, direccion, cargo))
        mysql.connection.commit()

        flash("Persona agregada satisfactoriamente")
        return redirect(url_for("Index"))


@app.route("/editar_persona/<id>")
def get_persona(id):
    cur = mysql.connection.cursor()
    cur.execute("SELECT * FROM personas WHERE id_persona = %s", (id,))
    data = cur.fetchall()
    return render_template("edit-persona.html", persona=data[0])


@app.route("/update_persona/<id>", methods=["POST"])
def update_persona(id):
    if request.method == "POST":
        tipo_persona = request.form["tipo_persona"]
        nombres = request.form["nombres"]
        apellidos = request.form["apellidos"]
        cedula_ruc = request.form["cedula_ruc"].strip()
        telefono = request.form["telefono"]
        correo = request.form["correo"]
        direccion = request.form["direccion"]
        cargo = request.form["cargo"]

        if len(cedula_ruc) > 10:
            flash("La cédula no puede tener más de 10 caracteres")
            return redirect(url_for("Index"))

        if cedula_ruc == "":
            cedula_ruc = None

        cur = mysql.connection.cursor()

        if cedula_ruc != None:
            cur.execute("SELECT * FROM personas WHERE cedula_ruc = %s AND id_persona != %s", (cedula_ruc, id))
            persona = cur.fetchall()

            if len(persona) > 0:
                flash("La cédula ingresada ya está registrada")
                return redirect(url_for("Index"))

        cur.execute("""
            UPDATE personas
            SET tipo_persona = %s,
                nombres = %s,
                apellidos = %s,
                cedula_ruc = %s,
                telefono = %s,
                correo = %s,
                direccion = %s,
                cargo = %s
            WHERE id_persona = %s
        """, (tipo_persona, nombres, apellidos, cedula_ruc, telefono, correo, direccion, cargo, id))
        mysql.connection.commit()

        flash("Persona actualizada satisfactoriamente")
        return redirect(url_for("Index"))


@app.route("/eliminar_persona/<string:id>")
def delete_persona(id):
    cur = mysql.connection.cursor()

    cur.execute("SELECT * FROM ventas WHERE id_cliente = %s", (id,))
    ventas_cliente = cur.fetchall()

    if len(ventas_cliente) > 0:
        flash("No se puede eliminar la persona porque está registrada como cliente en ventas")
        return redirect(url_for("Index"))

    cur.execute("SELECT * FROM ventas WHERE id_empleado = %s", (id,))
    ventas_empleado = cur.fetchall()

    if len(ventas_empleado) > 0:
        flash("No se puede eliminar la persona porque está registrada como empleado en ventas")
        return redirect(url_for("Index"))

    cur.execute("SELECT * FROM compras WHERE id_proveedor = %s", (id,))
    compras_proveedor = cur.fetchall()

    if len(compras_proveedor) > 0:
        flash("No se puede eliminar la persona porque está registrada como proveedor en compras")
        return redirect(url_for("Index"))

    cur.execute("SELECT * FROM compras WHERE id_empleado = %s", (id,))
    compras_empleado = cur.fetchall()

    if len(compras_empleado) > 0:
        flash("No se puede eliminar la persona porque está registrada como empleado en compras")
        return redirect(url_for("Index"))

    cur.execute("DELETE FROM personas WHERE id_persona = %s", (id,))
    mysql.connection.commit()

    flash("Persona eliminada satisfactoriamente")
    return redirect(url_for("Index"))


# CATEGORIAS

@app.route("/categorias")
@login_required
def categorias():
    cur = mysql.connection.cursor()
    cur.execute("SELECT * FROM categorias")
    data = cur.fetchall()
    return render_template("categorias.html", categorias=data)


@app.route("/add_categoria", methods=["POST"])
def add_categoria():
    if request.method == "POST":
        nombre_categoria = request.form["nombre_categoria"]
        descripcion = request.form["descripcion"]

        cur = mysql.connection.cursor()
        cur.execute("""
            INSERT INTO categorias (nombre_categoria, descripcion)
            VALUES (%s, %s)
        """, (nombre_categoria, descripcion))
        mysql.connection.commit()

        flash("Categoría agregada satisfactoriamente")
        return redirect(url_for("categorias"))


@app.route("/editar_categoria/<id>")
def get_categoria(id):
    cur = mysql.connection.cursor()
    cur.execute("SELECT * FROM categorias WHERE id_categoria = %s", (id,))
    data = cur.fetchall()
    return render_template("edit-categoria.html", categoria=data[0])


@app.route("/update_categoria/<id>", methods=["POST"])
def update_categoria(id):
    if request.method == "POST":
        nombre_categoria = request.form["nombre_categoria"]
        descripcion = request.form["descripcion"]

        cur = mysql.connection.cursor()
        cur.execute("""
            UPDATE categorias
            SET nombre_categoria = %s,
                descripcion = %s
            WHERE id_categoria = %s
        """, (nombre_categoria, descripcion, id))
        mysql.connection.commit()

        flash("Categoría actualizada satisfactoriamente")
        return redirect(url_for("categorias"))


@app.route("/eliminar_categoria/<string:id>")
def delete_categoria(id):
    cur = mysql.connection.cursor()

    cur.execute("SELECT * FROM productos WHERE id_categoria = %s", (id,))
    productos = cur.fetchall()

    if len(productos) > 0:
        flash("No se puede eliminar la categoría porque tiene productos registrados")
        return redirect(url_for("categorias"))

    cur.execute("DELETE FROM categorias WHERE id_categoria = %s", (id,))
    mysql.connection.commit()

    flash("Categoría eliminada satisfactoriamente")
    return redirect(url_for("categorias"))


# USUARIOS EMPLEADOS

@app.route("/asignar_usuario/<id>", methods=["GET", "POST"])
@login_required
def asignar_usuario(id):
    cur = mysql.connection.cursor()
    cur.execute("SELECT * FROM personas WHERE id_persona = %s AND tipo_persona = 'EMPLEADO'", (id,))
    empleado = cur.fetchone()

    if not empleado:
        flash("El empleado no existe")
        return redirect(url_for('Index'))

    if request.method == "POST":
        usuario = request.form["usuario"]
        contrasena = request.form["contrasena"]

        if not usuario or not contrasena:
            flash("Usuario y contraseña son obligatorios")
            return redirect(url_for('asignar_usuario', id=id))

        # Verificar que el usuario no esté en uso por otro empleado
        cur.execute("SELECT id_persona FROM personas WHERE usuario = %s AND id_persona != %s", (usuario, id))
        existente = cur.fetchone()
        if existente:
            flash("Ese nombre de usuario ya está en uso")
            return redirect(url_for('asignar_usuario', id=id))

        contrasena_hash = hashlib.sha256(contrasena.encode()).hexdigest()

        cur.execute("""
            UPDATE personas SET usuario = %s, contrasena = %s
            WHERE id_persona = %s
        """, (usuario, contrasena_hash, id))
        mysql.connection.commit()

        flash("Usuario asignado satisfactoriamente")
        return redirect(url_for('Index'))

    return render_template("asignar_usuario.html", empleado=empleado)

# PRODUCTOS

@app.route("/productos")
@login_required
def productos():
    search = request.args.get('search', '').strip()
    cur = mysql.connection.cursor()
    
    if search:
        cur.execute("""
            SELECT p.*, c.nombre_categoria 
            FROM productos p
            LEFT JOIN categorias c ON p.id_categoria = c.id_categoria
            WHERE p.nombre_producto LIKE %s 
               OR p.marca LIKE %s 
               OR p.descripcion LIKE %s
               OR c.nombre_categoria LIKE %s
            ORDER BY p.id_producto DESC
        """, (f'%{search}%', f'%{search}%', f'%{search}%', f'%{search}%'))
        productos = cur.fetchall()
    else:
        cur.execute("""
            SELECT p.*, c.nombre_categoria 
            FROM productos p
            LEFT JOIN categorias c ON p.id_categoria = c.id_categoria
            ORDER BY p.id_producto DESC
        """)
        productos = cur.fetchall()
    
    
    cur.execute("SELECT id_categoria, nombre_categoria FROM categorias")
    categorias = cur.fetchall()
    
    return render_template("productos.html", productos=productos, categorias=categorias, search=search)



@app.route("/add_producto", methods=["POST"])
def add_producto():
    if request.method == "POST":
        nombre_producto = request.form["nombre_producto"]
        marca = request.form["marca"]
        descripcion = request.form["descripcion"]
        precio_compra = request.form["precio_compra"]
        precio_venta = request.form["precio_venta"]
        stock_actual = request.form["stock_actual"]
        stock_minimo = request.form["stock_minimo"]
        id_categoria = request.form["id_categoria"]

        cur = mysql.connection.cursor()

        cur.execute("SELECT * FROM categorias WHERE id_categoria = %s", (id_categoria,))
        categoria = cur.fetchall()

        if len(categoria) == 0:
            flash("La categoría ingresada no existe")
            return redirect(url_for("productos"))

        if float(precio_compra) < 0 or float(precio_venta) < 0 or int(stock_actual) < 0 or int(stock_minimo) < 0:
            flash("No se permiten valores negativos")
            return redirect(url_for("productos"))

        cur.execute("""
            INSERT INTO productos
            (nombre_producto, marca, descripcion, precio_compra, precio_venta, stock_actual, stock_minimo, id_categoria)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, (nombre_producto, marca, descripcion, precio_compra, precio_venta, stock_actual, stock_minimo, id_categoria))
        mysql.connection.commit()

        flash("Producto agregado satisfactoriamente")
        return redirect(url_for("productos"))


@app.route("/editar_producto/<id>")
def get_producto(id):
    cur = mysql.connection.cursor()
    cur.execute("SELECT * FROM productos WHERE id_producto = %s", (id,))
    data = cur.fetchall()

    if len(data) == 0:
        flash("El producto no existe")
        return redirect(url_for("productos"))

    cur.execute("SELECT id_categoria, nombre_categoria FROM categorias")
    categorias = cur.fetchall()
    return render_template("edit-producto.html", producto=data[0], categorias=categorias)


@app.route("/update_producto/<id>", methods=["POST"])
def update_producto(id):
    if request.method == "POST":
        nombre_producto = request.form["nombre_producto"]
        marca = request.form["marca"]
        descripcion = request.form["descripcion"]
        precio_compra = request.form["precio_compra"]
        precio_venta = request.form["precio_venta"]
        stock_actual = request.form["stock_actual"]
        stock_minimo = request.form["stock_minimo"]
        id_categoria = request.form["id_categoria"]

        cur = mysql.connection.cursor()

        cur.execute("SELECT * FROM categorias WHERE id_categoria = %s", (id_categoria,))
        categoria = cur.fetchall()

        if len(categoria) == 0:
            flash("La categoría ingresada no existe")
            return redirect(url_for("productos"))

        if float(precio_compra) < 0 or float(precio_venta) < 0 or int(stock_actual) < 0 or int(stock_minimo) < 0:
            flash("No se permiten valores negativos")
            return redirect(url_for("productos"))

        cur.execute("""
            UPDATE productos
            SET nombre_producto = %s,
                marca = %s,
                descripcion = %s,
                precio_compra = %s,
                precio_venta = %s,
                stock_actual = %s,
                stock_minimo = %s,
                id_categoria = %s
            WHERE id_producto = %s
        """, (nombre_producto, marca, descripcion, precio_compra, precio_venta, stock_actual, stock_minimo, id_categoria, id))
        mysql.connection.commit()

        flash("Producto actualizado satisfactoriamente")
        return redirect(url_for("productos"))


@app.route("/eliminar_producto/<string:id>")
def delete_producto(id):
    cur = mysql.connection.cursor()

    cur.execute("SELECT * FROM detalle_compras WHERE id_producto = %s", (id,))
    detalle_compras = cur.fetchall()

    if len(detalle_compras) > 0:
        flash("No se puede eliminar el producto porque está registrado en detalles de compras")
        return redirect(url_for("productos"))

    cur.execute("SELECT * FROM detalle_ventas WHERE id_producto = %s", (id,))
    detalle_ventas = cur.fetchall()

    if len(detalle_ventas) > 0:
        flash("No se puede eliminar el producto porque está registrado en detalles de ventas")
        return redirect(url_for("productos"))

    cur.execute("DELETE FROM productos WHERE id_producto = %s", (id,))
    mysql.connection.commit()

    flash("Producto eliminado satisfactoriamente")
    return redirect(url_for("productos"))


# COMPRAS

@app.route("/compras")
@login_required
def compras():
    search = request.args.get('search', '').strip()
    fecha_desde = request.args.get('fecha_desde', '')
    fecha_hasta = request.args.get('fecha_hasta', '')
    estado = request.args.get('estado', '')
    
    cur = mysql.connection.cursor()
    
   
    query = """
        SELECT c.*, p.nombres as proveedor_nombre, e.nombres as empleado_nombre
        FROM compras c
        LEFT JOIN personas p ON c.id_proveedor = p.id_persona
        LEFT JOIN personas e ON c.id_empleado = e.id_persona
        WHERE 1=1
    """
    params = []
    
    if search:
        query += """ AND (c.numero_factura LIKE %s 
                         OR p.nombres LIKE %s 
                         OR p.apellidos LIKE %s
                         OR DATE(c.fecha_compra) LIKE %s
                         OR c.estado_compra LIKE %s)"""
        search_param = f'%{search}%'
        params.extend([search_param, search_param, search_param, search_param, search_param])
    
    if fecha_desde:
        query += " AND c.fecha_compra >= %s"
        params.append(fecha_desde)
    if fecha_hasta:
        query += " AND c.fecha_compra <= %s"
        params.append(fecha_hasta)
    if estado:
        query += " AND c.estado_compra = %s"
        params.append(estado)
    
    query += " ORDER BY c.id_compra DESC"
    cur.execute(query, params)
    compras = cur.fetchall()
    
    # Para los selects del formulario de creación (proveedores y empleados)
    cur.execute("SELECT id_persona, nombres, apellidos FROM personas WHERE tipo_persona = 'PROVEEDOR' AND estado = 'ACTIVO'")
    proveedores = cur.fetchall()
    cur.execute("SELECT id_persona, nombres, apellidos FROM personas WHERE tipo_persona = 'EMPLEADO' AND estado = 'ACTIVO'")
    empleados = cur.fetchall()
    
    return render_template("compras.html", compras=compras, proveedores=proveedores, empleados=empleados,
                           search=search, fecha_desde=fecha_desde, fecha_hasta=fecha_hasta, estado=estado)

@app.route("/add_compra", methods=["POST"])
def add_compra():
    if request.method == "POST":
        fecha_compra = request.form["fecha_compra"]
        numero_factura = request.form["numero_factura"]
        id_proveedor = request.form["id_proveedor"]
        id_empleado = request.form["id_empleado"]
        estado_compra = request.form["estado_compra"]

        cur = mysql.connection.cursor()

        cur.execute("SELECT * FROM personas WHERE id_persona = %s AND tipo_persona = 'PROVEEDOR'", (id_proveedor,))
        proveedor = cur.fetchall()

        if len(proveedor) == 0:
            flash("El proveedor ingresado no existe")
            return redirect(url_for("compras"))

        cur.execute("SELECT * FROM personas WHERE id_persona = %s AND tipo_persona = 'EMPLEADO'", (id_empleado,))
        empleado = cur.fetchall()

        if len(empleado) == 0:
            flash("El empleado ingresado no existe")
            return redirect(url_for("compras"))

        cur.execute("""
            INSERT INTO compras
            (fecha_compra, numero_factura, id_proveedor, id_empleado, subtotal, iva, total_compra, estado_compra)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, (fecha_compra, numero_factura, id_proveedor, id_empleado, 0, 0, 0, estado_compra))
        mysql.connection.commit()

        flash("Compra agregada satisfactoriamente")
        return redirect(url_for("compras"))


@app.route("/editar_compra/<id>")
def get_compra(id):
    cur = mysql.connection.cursor()
    cur.execute("SELECT * FROM compras WHERE id_compra = %s", (id,))
    data = cur.fetchall()
    cur.execute("SELECT id_persona, nombres, apellidos FROM personas WHERE tipo_persona = 'PROVEEDOR' AND estado = 'ACTIVO'")
    proveedores = cur.fetchall()
    cur.execute("SELECT id_persona, nombres, apellidos FROM personas WHERE tipo_persona = 'EMPLEADO' AND estado = 'ACTIVO'")
    empleados = cur.fetchall()
    return render_template("edit-compra.html", compra=data[0], proveedores=proveedores, empleados=empleados)


@app.route("/update_compra/<id>", methods=["POST"])
def update_compra(id):
    if request.method == "POST":
        fecha_compra = request.form["fecha_compra"]
        numero_factura = request.form["numero_factura"]
        id_proveedor = request.form["id_proveedor"]
        id_empleado = request.form["id_empleado"]
        estado_compra = request.form["estado_compra"]

        cur = mysql.connection.cursor()

        cur.execute("SELECT * FROM personas WHERE id_persona = %s AND tipo_persona = 'PROVEEDOR'", (id_proveedor,))
        proveedor = cur.fetchall()

        if len(proveedor) == 0:
            flash("El proveedor ingresado no existe")
            return redirect(url_for("compras"))

        cur.execute("SELECT * FROM personas WHERE id_persona = %s AND tipo_persona = 'EMPLEADO'", (id_empleado,))
        empleado = cur.fetchall()

        if len(empleado) == 0:
            flash("El empleado ingresado no existe")
            return redirect(url_for("compras"))

        cur.execute("""
            UPDATE compras
            SET fecha_compra = %s,
                numero_factura = %s,
                id_proveedor = %s,
                id_empleado = %s,
                estado_compra = %s
            WHERE id_compra = %s
        """, (fecha_compra, numero_factura, id_proveedor, id_empleado, estado_compra, id))
        mysql.connection.commit()

        flash("Compra actualizada satisfactoriamente")
        return redirect(url_for("compras"))


@app.route("/eliminar_compra/<string:id>")
def delete_compra(id):
    cur = mysql.connection.cursor()

    cur.execute("SELECT * FROM detalle_compras WHERE id_compra = %s", (id,))
    detalles = cur.fetchall()

    if len(detalles) > 0:
        flash("No se puede eliminar la compra porque tiene detalles registrados")
        return redirect(url_for("compras"))

    cur.execute("DELETE FROM compras WHERE id_compra = %s", (id,))
    mysql.connection.commit()

    flash("Compra eliminada satisfactoriamente")
    return redirect(url_for("compras"))


# DETALLE COMPRAS

@app.route("/detalle_compras")
@login_required
def detalle_compras():
    cur = mysql.connection.cursor()
    cur.execute("SELECT * FROM detalle_compras")
    data = cur.fetchall()
    cur.execute("SELECT id_compra, numero_factura FROM compras")
    compras = cur.fetchall()
    cur.execute("SELECT id_producto, nombre_producto FROM productos")
    productos = cur.fetchall()
    return render_template("detalle_compras.html", detalle_compras=data, compras=compras, productos=productos)


@app.route("/add_detalle_compra", methods=["POST"])
def add_detalle_compra():
    if request.method == "POST":
        id_compra = request.form["id_compra"]
        id_producto = request.form["id_producto"]
        cantidad = request.form["cantidad"]
        precio_unitario = request.form["precio_unitario"]

        cur = mysql.connection.cursor()

        cur.execute("SELECT * FROM compras WHERE id_compra = %s", (id_compra,))
        compra = cur.fetchall()

        if len(compra) == 0:
            flash("La compra ingresada no existe")
            return redirect(url_for("detalle_compras"))

        cur.execute("SELECT * FROM productos WHERE id_producto = %s", (id_producto,))
        producto = cur.fetchall()

        if len(producto) == 0:
            flash("El producto ingresado no existe")
            return redirect(url_for("detalle_compras"))

        if int(cantidad) <= 0 or float(precio_unitario) < 0:
            flash("La cantidad debe ser mayor a 0 y el precio no puede ser negativo")
            return redirect(url_for("detalle_compras"))

        subtotal = int(cantidad) * float(precio_unitario)

        cur.execute("""
            INSERT INTO detalle_compras
            (id_compra, id_producto, cantidad, precio_unitario, subtotal)
            VALUES (%s, %s, %s, %s, %s)
        """, (id_compra, id_producto, cantidad, precio_unitario, subtotal))
        mysql.connection.commit()

        cur.execute("SELECT IFNULL(SUM(subtotal), 0) FROM detalle_compras WHERE id_compra = %s", (id_compra,))
        subtotal_compra = cur.fetchone()[0]

        iva = float(subtotal_compra) * 0.15
        total_compra = float(subtotal_compra) + iva

        cur.execute("""
            UPDATE compras
            SET subtotal = %s,
                iva = %s,
                total_compra = %s
            WHERE id_compra = %s
        """, (subtotal_compra, iva, total_compra, id_compra))
        mysql.connection.commit()

        flash("Detalle de compra agregado satisfactoriamente")
        return redirect(url_for("detalle_compras"))


@app.route("/editar_detalle_compra/<id>")
def get_detalle_compra(id):
    cur = mysql.connection.cursor()
    cur.execute("SELECT * FROM detalle_compras WHERE id_detalle_compra = %s", (id,))
    data = cur.fetchall()
    return render_template("edit-detalle-compra.html", detalle_compra=data[0])


@app.route("/update_detalle_compra/<id>", methods=["POST"])
def update_detalle_compra(id):
    if request.method == "POST":
        id_compra = request.form["id_compra"]
        id_producto = request.form["id_producto"]
        cantidad = request.form["cantidad"]
        precio_unitario = request.form["precio_unitario"]

        cur = mysql.connection.cursor()

        cur.execute("SELECT id_compra FROM detalle_compras WHERE id_detalle_compra = %s", (id,))
        compra_anterior = cur.fetchall()

        if len(compra_anterior) == 0:
            flash("El detalle de compra no existe")
            return redirect(url_for("detalle_compras"))

        id_compra_anterior = compra_anterior[0][0]

        cur.execute("SELECT * FROM compras WHERE id_compra = %s", (id_compra,))
        compra = cur.fetchall()

        if len(compra) == 0:
            flash("La compra ingresada no existe")
            return redirect(url_for("detalle_compras"))

        cur.execute("SELECT * FROM productos WHERE id_producto = %s", (id_producto,))
        producto = cur.fetchall()

        if len(producto) == 0:
            flash("El producto ingresado no existe")
            return redirect(url_for("detalle_compras"))

        if int(cantidad) <= 0 or float(precio_unitario) < 0:
            flash("La cantidad debe ser mayor a 0 y el precio no puede ser negativo")
            return redirect(url_for("detalle_compras"))

        subtotal = int(cantidad) * float(precio_unitario)

        cur.execute("""
            UPDATE detalle_compras
            SET id_compra = %s,
                id_producto = %s,
                cantidad = %s,
                precio_unitario = %s,
                subtotal = %s
            WHERE id_detalle_compra = %s
        """, (id_compra, id_producto, cantidad, precio_unitario, subtotal, id))
        mysql.connection.commit()

        cur.execute("SELECT IFNULL(SUM(subtotal), 0) FROM detalle_compras WHERE id_compra = %s", (id_compra,))
        subtotal_compra = cur.fetchone()[0]

        iva = float(subtotal_compra) * 0.15
        total_compra = float(subtotal_compra) + iva

        cur.execute("""
            UPDATE compras
            SET subtotal = %s,
                iva = %s,
                total_compra = %s
            WHERE id_compra = %s
        """, (subtotal_compra, iva, total_compra, id_compra))
        mysql.connection.commit()

        if str(id_compra_anterior) != str(id_compra):
            cur.execute("SELECT IFNULL(SUM(subtotal), 0) FROM detalle_compras WHERE id_compra = %s", (id_compra_anterior,))
            subtotal_anterior = cur.fetchone()[0]

            iva_anterior = float(subtotal_anterior) * 0.15
            total_anterior = float(subtotal_anterior) + iva_anterior

            cur.execute("""
                UPDATE compras
                SET subtotal = %s,
                    iva = %s,
                    total_compra = %s
                WHERE id_compra = %s
            """, (subtotal_anterior, iva_anterior, total_anterior, id_compra_anterior))
            mysql.connection.commit()

        flash("Detalle de compra actualizado satisfactoriamente")
        return redirect(url_for("detalle_compras"))


@app.route("/eliminar_detalle_compra/<string:id>")
def delete_detalle_compra(id):
    cur = mysql.connection.cursor()

    cur.execute("SELECT id_compra FROM detalle_compras WHERE id_detalle_compra = %s", (id,))
    detalle = cur.fetchall()

    if len(detalle) == 0:
        flash("El detalle de compra no existe")
        return redirect(url_for("detalle_compras"))

    id_compra = detalle[0][0]

    cur.execute("DELETE FROM detalle_compras WHERE id_detalle_compra = %s", (id,))
    mysql.connection.commit()

    cur.execute("SELECT IFNULL(SUM(subtotal), 0) FROM detalle_compras WHERE id_compra = %s", (id_compra,))
    subtotal_compra = cur.fetchone()[0]

    iva = float(subtotal_compra) * 0.15
    total_compra = float(subtotal_compra) + iva

    cur.execute("""
        UPDATE compras
        SET subtotal = %s,
            iva = %s,
            total_compra = %s
        WHERE id_compra = %s
    """, (subtotal_compra, iva, total_compra, id_compra))
    mysql.connection.commit()

    flash("Detalle de compra eliminado satisfactoriamente")
    return redirect(url_for("detalle_compras"))


# VENTAS
@app.route("/ventas")
@login_required
def ventas():
    search = request.args.get('search', '').strip()
    cur = mysql.connection.cursor()
    
    if search:
        cur.execute("""
            SELECT v.*, c.nombres as cliente_nombre, e.nombres as empleado_nombre
            FROM ventas v
            LEFT JOIN personas c ON v.id_cliente = c.id_persona
            LEFT JOIN personas e ON v.id_empleado = e.id_persona
            WHERE CAST(v.id_venta AS CHAR) LIKE %s 
               OR c.nombres LIKE %s 
               OR c.apellidos LIKE %s
               OR DATE(v.fecha_venta) LIKE %s
               OR v.metodo_pago LIKE %s
               OR v.estado_venta LIKE %s
            ORDER BY v.id_venta DESC
        """, (f'%{search}%', f'%{search}%', f'%{search}%', f'%{search}%', f'%{search}%', f'%{search}%'))
    else:
        cur.execute("""
            SELECT v.*, c.nombres as cliente_nombre, e.nombres as empleado_nombre
            FROM ventas v
            LEFT JOIN personas c ON v.id_cliente = c.id_persona
            LEFT JOIN personas e ON v.id_empleado = e.id_persona
            ORDER BY v.id_venta DESC
        """)
    ventas = cur.fetchall()
    
    # Datos para los selects del formulario de creación
    cur.execute("SELECT id_persona, nombres, apellidos FROM personas WHERE tipo_persona = 'CLIENTE' AND estado = 'ACTIVO'")
    clientes = cur.fetchall()
    cur.execute("SELECT id_persona, nombres, apellidos FROM personas WHERE tipo_persona = 'EMPLEADO' AND estado = 'ACTIVO'")
    empleados = cur.fetchall()
    
    return render_template("ventas.html", ventas=ventas, clientes=clientes, empleados=empleados, search=search)

@app.route("/add_venta", methods=["POST"])
def add_venta():
    if request.method == "POST":
        fecha_venta = request.form["fecha_venta"]
        id_cliente = request.form["id_cliente"]
        id_empleado = request.form["id_empleado"]
        metodo_pago = request.form["metodo_pago"]
        estado_venta = request.form["estado_venta"]

        cur = mysql.connection.cursor()

        cur.execute("SELECT * FROM personas WHERE id_persona = %s AND tipo_persona = 'CLIENTE'", (id_cliente,))
        cliente = cur.fetchall()

        if len(cliente) == 0:
            flash("El cliente ingresado no existe")
            return redirect(url_for("ventas"))

        cur.execute("SELECT * FROM personas WHERE id_persona = %s AND tipo_persona = 'EMPLEADO'", (id_empleado,))
        empleado = cur.fetchall()

        if len(empleado) == 0:
            flash("El empleado ingresado no existe")
            return redirect(url_for("ventas"))

        cur.execute("""
            INSERT INTO ventas
            (fecha_venta, id_cliente, id_empleado, subtotal, descuento, iva, total_venta, metodo_pago, estado_venta)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (fecha_venta, id_cliente, id_empleado, 0, 0, 0, 0, metodo_pago, estado_venta))
        mysql.connection.commit()

        flash("Venta agregada satisfactoriamente")
        return redirect(url_for("ventas"))

@app.route("/editar_venta/<id>")
def get_venta(id):
    cur = mysql.connection.cursor()
    cur.execute("SELECT * FROM ventas WHERE id_venta = %s", (id,))
    data = cur.fetchall()
    cur.execute("SELECT id_persona, nombres, apellidos FROM personas WHERE tipo_persona = 'CLIENTE' AND estado = 'ACTIVO'")
    clientes = cur.fetchall()
    cur.execute("SELECT id_persona, nombres, apellidos FROM personas WHERE tipo_persona = 'EMPLEADO' AND estado = 'ACTIVO'")
    empleados = cur.fetchall()
    return render_template("edit-venta.html", venta=data[0], clientes=clientes, empleados=empleados)


@app.route("/update_venta/<id>", methods=["POST"])
def update_venta(id):
    if request.method == "POST":
        fecha_venta = request.form["fecha_venta"]
        id_cliente = request.form["id_cliente"]
        id_empleado = request.form["id_empleado"]
        metodo_pago = request.form["metodo_pago"]
        estado_venta = request.form["estado_venta"]

        cur = mysql.connection.cursor()

        cur.execute("SELECT * FROM personas WHERE id_persona = %s AND tipo_persona = 'CLIENTE'", (id_cliente,))
        cliente = cur.fetchall()

        if len(cliente) == 0:
            flash("El cliente ingresado no existe")
            return redirect(url_for("ventas"))

        cur.execute("SELECT * FROM personas WHERE id_persona = %s AND tipo_persona = 'EMPLEADO'", (id_empleado,))
        empleado = cur.fetchall()

        if len(empleado) == 0:
            flash("El empleado ingresado no existe")
            return redirect(url_for("ventas"))

        cur.execute("""
            UPDATE ventas
            SET fecha_venta = %s,
                id_cliente = %s,
                id_empleado = %s,
                metodo_pago = %s,
                estado_venta = %s
            WHERE id_venta = %s
        """, (fecha_venta, id_cliente, id_empleado, metodo_pago, estado_venta, id))
        mysql.connection.commit()

        flash("Venta actualizada satisfactoriamente")
        return redirect(url_for("ventas"))


@app.route("/eliminar_venta/<string:id>")
def delete_venta(id):
    cur = mysql.connection.cursor()
    cur.execute("DELETE FROM ventas WHERE id_venta = %s", (id,))
    mysql.connection.commit()

    flash("Venta eliminada satisfactoriamente")
    return redirect(url_for("ventas"))


# DETALLE VENTAS

@app.route("/detalle_ventas")
@login_required
def detalle_ventas():
    cur = mysql.connection.cursor()
    cur.execute("SELECT * FROM detalle_ventas")
    data = cur.fetchall()
    cur.execute("SELECT id_venta, fecha_venta FROM ventas")  
    ventas = cur.fetchall()
    cur.execute("SELECT id_producto, nombre_producto FROM productos")
    productos = cur.fetchall()
    return render_template("detalle_ventas.html", detalle_ventas=data, ventas=ventas, productos=productos)


@app.route("/add_detalle_venta", methods=["POST"])
def add_detalle_venta():
    if request.method == "POST":
        id_venta = request.form["id_venta"]
        id_producto = request.form["id_producto"]
        cantidad = request.form["cantidad"]
        precio_unitario = request.form["precio_unitario"]
        descuento = request.form["descuento"]

        if descuento == "":
            descuento = 0

        cur = mysql.connection.cursor()

        cur.execute("SELECT * FROM ventas WHERE id_venta = %s", (id_venta,))
        venta = cur.fetchall()

        if len(venta) == 0:
            flash("La venta ingresada no existe")
            return redirect(url_for("detalle_ventas"))

        cur.execute("SELECT * FROM productos WHERE id_producto = %s", (id_producto,))
        producto = cur.fetchall()

        if len(producto) == 0:
            flash("El producto ingresado no existe")
            return redirect(url_for("detalle_ventas"))

        if int(cantidad) <= 0 or float(precio_unitario) < 0 or float(descuento) < 0:
            flash("La cantidad debe ser mayor a 0 y no se permiten valores negativos")
            return redirect(url_for("detalle_ventas"))

        subtotal = (int(cantidad) * float(precio_unitario)) - float(descuento)

        if subtotal < 0:
            flash("El descuento no puede ser mayor al subtotal")
            return redirect(url_for("detalle_ventas"))

        cur.execute("""
            INSERT INTO detalle_ventas
            (id_venta, id_producto, cantidad, precio_unitario, descuento, subtotal)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (id_venta, id_producto, cantidad, precio_unitario, descuento, subtotal))
        mysql.connection.commit()

        cur.execute("SELECT IFNULL(SUM(subtotal), 0), IFNULL(SUM(descuento), 0) FROM detalle_ventas WHERE id_venta = %s", (id_venta,))
        datos = cur.fetchone()

        subtotal_venta = datos[0]
        descuento_venta = datos[1]
        iva = float(subtotal_venta) * 0.15
        total_venta = float(subtotal_venta) + iva

        cur.execute("""
            UPDATE ventas
            SET subtotal = %s,
                descuento = %s,
                iva = %s,
                total_venta = %s
            WHERE id_venta = %s
        """, (subtotal_venta, descuento_venta, iva, total_venta, id_venta))
        mysql.connection.commit()

        flash("Detalle de venta agregado satisfactoriamente")
        return redirect(url_for("detalle_ventas"))


@app.route("/editar_detalle_venta/<id>")
def get_detalle_venta(id):
    cur = mysql.connection.cursor()
    cur.execute("SELECT * FROM detalle_ventas WHERE id_detalle_venta = %s", (id,))
    data = cur.fetchall()
    cur.execute("SELECT id_venta, fecha_venta FROM ventas")
    ventas = cur.fetchall()
    cur.execute("SELECT id_producto, nombre_producto FROM productos")
    productos = cur.fetchall()
    return render_template("edit-detalle-venta.html", detalle_venta=data[0], ventas=ventas, productos=productos)


@app.route("/update_detalle_venta/<id>", methods=["POST"])
def update_detalle_venta(id):
    if request.method == "POST":
        id_venta = request.form["id_venta"]
        id_producto = request.form["id_producto"]
        cantidad = request.form["cantidad"]
        precio_unitario = request.form["precio_unitario"]
        descuento = request.form["descuento"]

        if descuento == "":
            descuento = 0

        cur = mysql.connection.cursor()

        cur.execute("SELECT id_venta FROM detalle_ventas WHERE id_detalle_venta = %s", (id,))
        venta_anterior = cur.fetchall()

        if len(venta_anterior) == 0:
            flash("El detalle de venta no existe")
            return redirect(url_for("detalle_ventas"))

        id_venta_anterior = venta_anterior[0][0]

        cur.execute("SELECT * FROM ventas WHERE id_venta = %s", (id_venta,))
        venta = cur.fetchall()

        if len(venta) == 0:
            flash("La venta ingresada no existe")
            return redirect(url_for("detalle_ventas"))

        cur.execute("SELECT * FROM productos WHERE id_producto = %s", (id_producto,))
        producto = cur.fetchall()

        if len(producto) == 0:
            flash("El producto ingresado no existe")
            return redirect(url_for("detalle_ventas"))

        if int(cantidad) <= 0 or float(precio_unitario) < 0 or float(descuento) < 0:
            flash("La cantidad debe ser mayor a 0 y no se permiten valores negativos")
            return redirect(url_for("detalle_ventas"))

        subtotal = (int(cantidad) * float(precio_unitario)) - float(descuento)

        if subtotal < 0:
            flash("El descuento no puede ser mayor al subtotal")
            return redirect(url_for("detalle_ventas"))

        cur.execute("""
            UPDATE detalle_ventas
            SET id_venta = %s,
                id_producto = %s,
                cantidad = %s,
                precio_unitario = %s,
                descuento = %s,
                subtotal = %s
            WHERE id_detalle_venta = %s
        """, (id_venta, id_producto, cantidad, precio_unitario, descuento, subtotal, id))
        mysql.connection.commit()

        cur.execute("SELECT IFNULL(SUM(subtotal), 0), IFNULL(SUM(descuento), 0) FROM detalle_ventas WHERE id_venta = %s", (id_venta,))
        datos = cur.fetchone()

        subtotal_venta = datos[0]
        descuento_venta = datos[1]
        iva = float(subtotal_venta) * 0.15
        total_venta = float(subtotal_venta) + iva

        cur.execute("""
            UPDATE ventas
            SET subtotal = %s,
                descuento = %s,
                iva = %s,
                total_venta = %s
            WHERE id_venta = %s
        """, (subtotal_venta, descuento_venta, iva, total_venta, id_venta))
        mysql.connection.commit()

        if str(id_venta_anterior) != str(id_venta):
            cur.execute("SELECT IFNULL(SUM(subtotal), 0), IFNULL(SUM(descuento), 0) FROM detalle_ventas WHERE id_venta = %s", (id_venta_anterior,))
            datos_anterior = cur.fetchone()

            subtotal_anterior = datos_anterior[0]
            descuento_anterior = datos_anterior[1]
            iva_anterior = float(subtotal_anterior) * 0.15
            total_anterior = float(subtotal_anterior) + iva_anterior

            cur.execute("""
                UPDATE ventas
                SET subtotal = %s,
                    descuento = %s,
                    iva = %s,
                    total_venta = %s
                WHERE id_venta = %s
            """, (subtotal_anterior, descuento_anterior, iva_anterior, total_anterior, id_venta_anterior))
            mysql.connection.commit()

        flash("Detalle de venta actualizado satisfactoriamente")
        return redirect(url_for("detalle_ventas"))


@app.route("/eliminar_detalle_venta/<string:id>")
def delete_detalle_venta(id):
    cur = mysql.connection.cursor()

    cur.execute("SELECT id_venta FROM detalle_ventas WHERE id_detalle_venta = %s", (id,))
    detalle = cur.fetchall()

    if len(detalle) == 0:
        flash("El detalle de venta no existe")
        return redirect(url_for("detalle_ventas"))

    id_venta = detalle[0][0]

    cur.execute("DELETE FROM detalle_ventas WHERE id_detalle_venta = %s", (id,))
    mysql.connection.commit()

    cur.execute("SELECT IFNULL(SUM(subtotal), 0), IFNULL(SUM(descuento), 0) FROM detalle_ventas WHERE id_venta = %s", (id_venta,))
    datos = cur.fetchone()

    subtotal_venta = datos[0]
    descuento_venta = datos[1]
    iva = float(subtotal_venta) * 0.15
    total_venta = float(subtotal_venta) + iva

    cur.execute("""
        UPDATE ventas
        SET subtotal = %s,
            descuento = %s,
            iva = %s,
            total_venta = %s
        WHERE id_venta = %s
    """, (subtotal_venta, descuento_venta, iva, total_venta, id_venta))
    mysql.connection.commit()

    flash("Detalle de venta eliminado satisfactoriamente")
    return redirect(url_for("detalle_ventas"))


if __name__ == "__main__":
    app.run(port=3000, debug=True)
