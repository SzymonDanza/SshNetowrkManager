from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required
from werkzeug.security import generate_password_hash, check_password_hash
from app.db.base import SessionLocal
from app.models.user import User

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")
        db = SessionLocal()
        user = db.query(User).filter_by(email=email).first()
        db.close()
        if user and check_password_hash(user.password_hash, password):
            login_user(user)
            return redirect(url_for("dashboard"))
        return render_template("auth/login.html", error="Nieprawidłowy email lub hasło.")
    return render_template("auth/login.html")


@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("auth.login"))


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")
        db = SessionLocal()
        if db.query(User).filter_by(email=email).first():
            db.close()
            return render_template("auth/register.html", error="Email już zajęty.")
        user = User(
            email=email,
            password_hash=generate_password_hash(password),
            role="operator"
        )
        db.add(user)
        db.commit()
        db.close()
        return redirect(url_for("auth.login"))
    return render_template("auth/register.html")
