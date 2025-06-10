from flask import Flask, render_template, request, redirect, url_for, session, flash
from ultralytics import YOLO
import requests
import os
import sqlite3

app = Flask(__name__)
app.secret_key = 'clave_secreta_para_sesiones'

# ================= BASE DE DATOS ================
def init_db():
    with sqlite3.connect('usuarios.db') as conn:
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS usuarios (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre TEXT NOT NULL,
                codigo TEXT NOT NULL UNIQUE,
                carrera TEXT NOT NULL,
                password TEXT NOT NULL
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS historial (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                codigo TEXT NOT NULL,
                componente TEXT NOT NULL,
                mpn TEXT,
                fabricante TEXT,
                descripcion TEXT,
                categoria TEXT,
                fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        conn.commit()

init_db()

# ========== CREDENCIALES DE NEXAR ==========
CLIENT_ID = '2ec98ebb-9c17-4128-b28a-35e95a4f338c'
CLIENT_SECRET = 'V-9IAEDOARvKAa3s57QeVy1NIbfL-lbZoXr3'

def obtener_token():
    url = "https://identity.nexar.com/connect/token"
    data = {
        "grant_type": "client_credentials",
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "scope": "supply.domain"
    }
    response = requests.post(url, data=data)
    if response.status_code == 200:
        return response.json()["access_token"]
    else:
        print("❌ Error al obtener token:", response.text)
        return None

def buscar_componente(nombre, token):
    url = "https://api.nexar.com/graphql"
    headers = {"Authorization": f"Bearer {token}"}
    query = """
    query BuscarComponente($busqueda: String!) {
      supSearch(q: $busqueda, limit: 3) {
        results {
          part {
            mpn
            manufacturer { name }
            shortDescription
            category { name }
          }
        }
      }
    }
    """
    variables = {"busqueda": nombre}
    response = requests.post(url, json={"query": query, "variables": variables}, headers=headers)
    if response.status_code == 200:
        return response.json()["data"]["supSearch"]["results"]
    else:
        print("❌ Error en la consulta:", response.text)
        return []

# ========== LOGIN ==========
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        codigo = request.form['codigo']
        password = request.form['password']
        conn = sqlite3.connect('usuarios.db')
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM usuarios WHERE codigo = ? AND password = ?", (codigo, password))
        usuario = cursor.fetchone()
        conn.close()
        if usuario:
            session['usuario'] = usuario[1]
            session['codigo'] = usuario[2]
            session['carrera'] = usuario[3]
            return redirect(url_for('index'))
        else:
            flash('⚠️ Código o contraseña incorrectos.')
            return redirect(url_for('login'))
    return render_template('login.html')

# ========== REGISTRO ==========
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        nombre = request.form['nombre']
        codigo = request.form['codigo']
        carrera = request.form['carrera']
        password = request.form['password']
        conn = sqlite3.connect('usuarios.db')
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM usuarios WHERE codigo = ?", (codigo,))
        if cursor.fetchone():
            flash('⚠️ El código de estudiante ya está registrado.')
            conn.close()
            return redirect(url_for('register'))
        cursor.execute("INSERT INTO usuarios (nombre, codigo, carrera, password) VALUES (?, ?, ?, ?)", (nombre, codigo, carrera, password))
        conn.commit()
        conn.close()
        flash('✅ Registro exitoso. Inicia sesión.')
        return redirect(url_for('login'))
    return render_template('register.html')

# ========== LOGOUT ==========
@app.route('/logout')
def logout():
    session.pop('usuario', None)
    flash('Has cerrado sesión correctamente.')
    return redirect(url_for('login'))

# ========== HISTORIAL ==========
@app.route('/historial')
def historial():
    if 'usuario' not in session:
        return redirect(url_for('login'))
    conn = sqlite3.connect('usuarios.db')
    cursor = conn.cursor()
    cursor.execute('''
        SELECT componente, mpn, fabricante, descripcion, categoria, fecha
        FROM historial
        WHERE codigo = ?
        ORDER BY fecha DESC
    ''', (session['codigo'],))
    datos = cursor.fetchall()
    conn.close()
    return render_template('historial.html', historial=datos)

# ========== RUTA PRINCIPAL ==========
@app.route('/', methods=['GET', 'POST'])
def index():
    if 'usuario' not in session:
        return redirect(url_for('login'))

    nombre = None
    resultados = []

    if request.method == 'POST':
        imagen = request.files['imagen']
        ruta_original = os.path.join('static', 'original.jpg')
        imagen.save(ruta_original)

        model = YOLO('best.pt')
        resultado = model(ruta_original)[0]
        ruta_resultado = os.path.join('static', 'resultado.jpg')
        resultado.save(filename=ruta_resultado)

        for box in resultado.boxes:
            clase_id = int(box.cls[0])
            nombre = model.names[clase_id]
            break

        if nombre:
            token = obtener_token()
            if token:
                consulta = buscar_componente(nombre, token)
                if consulta:
                    for r in consulta:
                        parte = r.get('part')
                        if parte:
                            mpn = parte.get('mpn', 'Desconocido')
                            fabricante = parte.get('manufacturer', {}).get('name', 'Desconocido')
                            descripcion = parte.get('shortDescription', 'Sin descripción')
                            categoria = parte.get('category', {}).get('name', 'Sin categoría')

                            resultados.append({
                                'mpn': mpn,
                                'manufacturer': fabricante,
                                'descripcion': descripcion,
                                'categoria': categoria
                            })

                            # Guardar en historial
                            conn = sqlite3.connect('usuarios.db')
                            cursor = conn.cursor()
                            cursor.execute('''
                                INSERT INTO historial (codigo, componente, mpn, fabricante, descripcion, categoria)
                                VALUES (?, ?, ?, ?, ?, ?)
                            ''', (
                                session.get('codigo', 'Desconocido'),
                                nombre or 'Desconocido',
                                mpn,
                                fabricante,
                                descripcion,
                                categoria
                            ))
                            conn.commit()
                            conn.close()

    return render_template('index.html', nombre=nombre, resultados=resultados)

# ========== EJECUTAR ==========
if __name__ == '__main__':
    app.run(debug=True)
