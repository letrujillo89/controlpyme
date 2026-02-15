from flask import render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required
from . import auth_bp
from ..extensions import db
from ..models import User, Business

# ✅ PON AQUÍ TU CORREO REAL (el que será ADMIN)
ADMIN_EMAIL = "ltrujilloirarragorri@gmail.com"


@auth_bp.get("/login")
def login():
    return render_template("auth/login.html")


@auth_bp.post("/login")
def login_post():
    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")

    user = User.query.filter_by(email=email).first()
    if not user or not user.check_password(password):
        flash("Credenciales incorrectas.", "danger")
        return redirect(url_for("auth.login"))

    login_user(user)
    return redirect(url_for("main.dashboard"))


@auth_bp.get("/register")
def register():
    return render_template("auth/register.html")


@auth_bp.post("/register")
def register_post():
    business_name = request.form.get("business_name", "").strip()
    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")

    if not business_name or not email or not password:
        flash("Completa todos los campos.", "danger")
        return redirect(url_for("auth.register"))

    if User.query.filter_by(email=email).first():
        flash("Ese correo ya está registrado.", "warning")
        return redirect(url_for("auth.register"))

    biz = Business(name=business_name)

    # ✅ Admin automático si el correo coincide
    user = User(
        email=email,
        business=biz,
        is_admin=(email == ADMIN_EMAIL.lower())
    )
    user.set_password(password)

    db.session.add_all([biz, user])
    db.session.commit()

    login_user(user)
    flash("Cuenta creada. ¡Bienvenido!", "success")
    return redirect(url_for("main.dashboard"))


@auth_bp.get("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("auth.login"))
