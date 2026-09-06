"""Sesiones locales, CSRF y control de acceso en páginas y API."""
import hmac
import re
import secrets
import sqlite3
import time
from datetime import datetime, timezone, timedelta

import click
from flask import Blueprint, abort, current_app, g, jsonify, redirect, render_template, request, session
from flask.cli import with_appcontext
from werkzeug.security import generate_password_hash, check_password_hash

from app.db import get_db
from app.models.repository import audit, utcnow

bp=Blueprint('auth',__name__)
ADMIN_PAGES={'control','settings','users','audit'}


def create_user(username,password,role):
    if not isinstance(username,str) or not re.fullmatch(r'[a-zA-Z0-9_.-]{3,40}',username):
        raise ValueError('Usuario: 3 a 40 letras, números, punto, guion o guion bajo')
    if not isinstance(password,str) or not 12<=len(password)<=128:
        raise ValueError('La contraseña debe tener entre 12 y 128 caracteres')
    if not isinstance(role,str) or role not in {'ADMIN','OPERADOR'}:
        raise ValueError('Rol inválido')
    try:
        cursor=get_db().execute('INSERT INTO users(username,password_hash,role,created_at) VALUES (?,?,?,?)',
                                (username,generate_password_hash(password,method='pbkdf2:sha256:1000000'),role,utcnow()))
    except sqlite3.IntegrityError:
        raise ValueError('El usuario ya existe') from None
    return cursor.lastrowid


@click.command('create-user')
@click.option('--username',prompt='Usuario')
@click.option('--role',type=click.Choice(['ADMIN','OPERADOR']),default='ADMIN')
@click.password_option(confirmation_prompt=True)
@with_appcontext
def create_user_command(username,role,password):
    """Crear un usuario local; la contraseña se solicita sin mostrarla."""
    try:
        with get_db():
            user_id=create_user(username,password,role)
            audit('user.create.cli',username,user_id)
    except ValueError as exc:
        raise click.ClickException(str(exc)) from None
    click.echo('Usuario creado')


def init_app(app):
    app.register_blueprint(bp)
    app.cli.add_command(create_user_command)

    @app.before_request
    def protect():
        g.request_started=time.perf_counter()
        g.user=None
        user_id=session.get('user_id')
        if user_id:
            row=get_db().execute('SELECT id,username,role,active FROM users WHERE id=?',(user_id,)).fetchone()
            if row and row['active']:
                g.user=dict(row)
        public=request.path in {'/login','/landing','/api/health'} or request.path.startswith('/static/')
        if not public and not g.user:
            if request.path.startswith('/api/'):
                return jsonify(error='Autenticación requerida'),401
            return redirect('/login')
        path=request.path.strip('/').split('/')
        admin=(path[0] in ADMIN_PAGES or request.path.startswith(('/api/settings','/api/users','/api/audit','/api/backup','/api/metrics','/api/simulation'))
               or (request.path.startswith('/api/control') and request.method!='GET'))
        if admin and (not g.user or g.user['role']!='ADMIN'):
            abort(403)
        if request.method in {'POST','PUT','PATCH','DELETE'}:
            sent=request.headers.get('X-CSRF-Token') or request.form.get('csrf_token','')
            expected=session.get('csrf_token','')
            if not expected or not hmac.compare_digest(sent,expected):
                abort(400,description='Token CSRF inválido; recargar la página')
            if request.is_json and not isinstance(request.get_json(),dict):
                raise ValueError('Se requiere un objeto JSON')

    @app.after_request
    def record_response(response):
        response.headers['X-Content-Type-Options']='nosniff'
        response.headers['X-Frame-Options']='DENY'
        response.headers['Referrer-Policy']='same-origin'
        if not request.path.startswith('/static/'):
            response.headers['Cache-Control']='no-store'
            try:
                with get_db() as db:
                    duration=(time.perf_counter()-g.request_started)*1000
                    db.execute('INSERT INTO web_metrics(timestamp,path,status,duration_ms) VALUES (?,?,?,?)',
                               (utcnow(),request.path[:160],response.status_code,duration))
            except sqlite3.Error:
                current_app.logger.exception('No se pudo registrar métrica web')
        return response


@bp.route('/login',methods=['GET','POST'])
def login():
    session.setdefault('csrf_token',secrets.token_hex(32))
    error=None
    if request.method=='POST':
        username=request.form.get('username','')[:40]
        password=request.form.get('password','')
        cutoff=(datetime.now(timezone.utc)-timedelta(minutes=5)).isoformat(timespec='milliseconds')
        attempts=get_db().execute("SELECT count(*) FROM audit_log WHERE action='login.failed' AND details=? AND timestamp>=?",(username,cutoff)).fetchone()[0]
        if attempts>=10:
            return render_template('login.html',error='Demasiados intentos. Esperar 5 minutos.'),429
        row=get_db().execute('SELECT * FROM users WHERE username=? AND active=1',(username,)).fetchone()
        if row and len(password)<=128 and check_password_hash(row['password_hash'],password):
            session.clear()
            session.update(user_id=row['id'],csrf_token=secrets.token_hex(32))
            session.permanent=True
            with get_db(): audit('login.success',username,row['id'])
            current_app.logger.info('Login: %s',username)
            return redirect('/dashboard')
        with get_db(): audit('login.failed',username)
        error='Usuario o contraseña incorrectos'
    return render_template('login.html',error=error),401 if error else 200


@bp.post('/logout')
def logout():
    with get_db(): audit('logout','',g.user['id'])
    session.clear()
    return redirect('/login')
