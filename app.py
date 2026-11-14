# -*- coding: utf-8 -*-
import os, json, calendar, hmac, secrets
from pathlib import Path
from datetime import date
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, flash, session

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'cambia-esta-clave-secreta-antes-de-publicar-2026')
app.config.update(SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE='Lax',
                  SESSION_COOKIE_SECURE=os.environ.get('RENDER', '') == 'true', PERMANENT_SESSION_LIFETIME=60*60*12)
ROOT = Path(__file__).resolve().parent
DB = ROOT / 'reservas.json'
ADMIN_USER = os.environ.get('ADMIN_USER', 'mare')
ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'Mare2026!')

PACKAGES = {
    'Propuesta 1': {'price': 900, 'details': 'Corazón de rosas rosadas, 24 velas LED, pétalos y luces, alfombra rosada, 6 floreros, ramo de rosas, mesa decorada, cena romántica y 2 postres.'},
    'Propuesta 2': {'price': 650, 'details': 'Corazón de rosas rosadas, 24 velas LED, pétalos y luces, alfombra rosada, 6 floreros y mesa decorada.'},
    'Propuesta 3': {'price': 650, 'details': 'Corazón de rosas rosadas, 17 letras LED de 22 cm, 24 velas LED, pétalos y luces, alfombra rosada, 6 floreros y mesa decorada.'},
    'Propuesta 4': {'price': 650, 'details': '24 velas LED, 17 letras pequeñas, pétalos y luces, alfombra rosada, 6 floreros, mesa decorada, cena romántica y 2 postres.'},
    'Propuesta 5': {'price': 400, 'details': '24 velas LED, 17 letras pequeñas, pétalos y luces, alfombra rosada, 6 floreros y mesa decorada.'},
}

def login_required(fn):
    @wraps(fn)
    def wrapped(*args, **kwargs):
        if not session.get('mare_logged_in'):
            return redirect(url_for('login', next=request.path))
        return fn(*args, **kwargs)
    return wrapped

@app.route('/login', methods=['GET', 'POST'])
def login():
    if session.get('mare_logged_in'):
        return redirect(url_for('home'))
    error = None
    if request.method == 'POST':
        username = request.form.get('username', '')
        password = request.form.get('password', '')
        if hmac.compare_digest(username, ADMIN_USER) and hmac.compare_digest(password, ADMIN_PASSWORD):
            session.clear(); session['mare_logged_in'] = True; session.permanent = True
            return redirect(url_for('home'))
        error = 'Usuario o contraseña incorrectos.'
    return render_template('login.html', error=error)

@app.route('/salir', methods=['POST'])
@login_required
def logout():
    session.clear()
    return redirect(url_for('login'))

def load():
    try:
        data = json.loads(DB.read_text(encoding='utf-8'))
        return data if isinstance(data, list) else []
    except (FileNotFoundError, json.JSONDecodeError):
        return []

def save(rows):
    DB.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding='utf-8')

def num(v):
    try: return max(0, float(v or 0))
    except (ValueError, TypeError): return 0

@app.route('/')
@login_required
def home():
    today = date.today()
    year = request.args.get('year', today.year, type=int)
    month = request.args.get('month', today.month, type=int)
    if month < 1: month, year = 12, year - 1
    if month > 12: month, year = 1, year + 1
    rows = load(); cal = calendar.Calendar(firstweekday=0); weeks = cal.monthdatescalendar(year, month)
    by_day = {}
    for r in rows: by_day.setdefault(r.get('fecha', ''), []).append(r)
    selected = request.args.get('day', today.isoformat())
    selected_rows = sorted([r for r in rows if r.get('fecha') == selected], key=lambda x:x.get('hora',''))
    total = sum(num(r.get('precio_catalogo')) for r in rows); paid = sum(num(r.get('pagado')) for r in rows)
    return render_template('index.html', weeks=weeks, year=year, month=month,
        month_name=['Enero','Febrero','Marzo','Abril','Mayo','Junio','Julio','Agosto','Septiembre','Octubre','Noviembre','Diciembre'][month-1],
        today=today.isoformat(), selected=selected, by_day=by_day, selected_rows=selected_rows,
        rows=rows, packages=PACKAGES, total=total, paid=paid)

@app.route('/guardar', methods=['POST'])
@login_required
def guardar():
    rows = load(); rid = request.form.get('id', '').strip()
    item = {'id': rid or str(max([int(x.get('id',0)) for x in rows if str(x.get('id','')).isdigit()] + [0]) + 1),
        'cliente': request.form.get('cliente','').strip(), 'fecha': request.form.get('fecha',''),
        'hora': request.form.get('hora',''), 'lugar': request.form.get('lugar','').strip(),
        'paquete': request.form.get('paquete',''), 'precio_catalogo': num(request.form.get('precio')),
        'pagado': num(request.form.get('pagado'))}
    if not item['cliente'] or not item['fecha'] or not item['hora'] or not item['lugar']:
        flash('Completa nombre, fecha, hora y lugar.', 'error')
        return redirect(url_for('home', day=item['fecha'] or date.today().isoformat()))
    conflict = next((r for r in rows if r.get('fecha')==item['fecha'] and r.get('hora')==item['hora'] and r.get('id')!=rid), None)
    if conflict:
        flash('Ya existe una reserva en esa fecha y hora.', 'error'); return redirect(url_for('home', day=item['fecha']))
    if rid and any(r.get('id')==rid for r in rows): rows = [item if r.get('id')==rid else r for r in rows]
    else: rows.append(item)
    save(rows); flash('Reserva guardada correctamente ♡', 'ok')
    return redirect(url_for('home', day=item['fecha']))

@app.route('/eliminar/<rid>', methods=['POST'])
@login_required
def eliminar(rid):
    save([r for r in load() if r.get('id') != rid]); flash('Reserva eliminada.', 'ok')
    return redirect(url_for('home'))

@app.route('/editar/<rid>')
@login_required
def editar(rid):
    item = next((r for r in load() if r.get('id')==rid), None)
    if not item: return redirect(url_for('home'))
    return render_template('index.html', edit=item, weeks=[], year=date.today().year, month=date.today().month,
        month_name='', today=date.today().isoformat(), selected=item.get('fecha'), by_day={}, selected_rows=[],
        rows=load(), packages=PACKAGES, total=0, paid=0)

@app.after_request
def security_headers(response):
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['Referrer-Policy'] = 'same-origin'
    response.headers['Cache-Control'] = 'no-store'
    return response

if __name__ == '__main__': app.run(host='0.0.0.0', port=5000, debug=False)
