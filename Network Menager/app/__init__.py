# app/__init__.py

from flask import Flask

def create_app():
    app = Flask(__name__)
    app.secret_key = "supersecretkey"

    from app.routes import register_routes
    register_routes(app)

    return app
