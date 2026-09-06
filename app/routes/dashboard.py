from flask import Blueprint, redirect, render_template, url_for

bp = Blueprint("dashboard", __name__)
PAGES = {"dashboard": "Panel de monitoreo", "sensors": "Sensores", "history": "Históricos", "alerts": "Alertas", "control": "Control PID", "vision": "Visión vegetal", "settings": "Configuración", "users": "Usuarios", "audit": "Auditoría"}

@bp.get("/")
def index():
    return redirect(url_for("dashboard.index_page"))

@bp.get("/landing")
def landing():
    return render_template("landing.html")

@bp.get("/dashboard")
def index_page():
    return render_template("dashboard.html", page="dashboard", title=PAGES["dashboard"])

@bp.get("/<page>")
def page_view(page):
    from flask import abort
    if page not in PAGES:
        abort(404)
    return render_template("dashboard.html", page=page, title=PAGES[page])
