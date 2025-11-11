# ================================================
#  Inicjalizacja aplikacji Flask
# ================================================
from flask import Flask

def create_app():
    app = Flask(__name__)
    app.secret_key = "supersecretkey"

    # Import tras po utworzeniu instancji (żeby uniknąć cyklicznych importów)
    from .routes import register_routes
    register_routes(app)

    return app
