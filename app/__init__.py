import os
from flask import Flask
from flask_login import LoginManager
from dotenv import load_dotenv
from app.db.base import SessionLocal
from app.models.user import User

load_dotenv()


def create_app():
    app = Flask(__name__)
    app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev")

    login_manager = LoginManager(app)
    login_manager.login_view = "auth.login"

    @login_manager.user_loader
    def load_user(user_id):
        db = SessionLocal()
        user = db.get(User, int(user_id))
        db.close()
        return user

    from app.auth.routes import auth_bp
    app.register_blueprint(auth_bp)

    from app.routes import register_routes
    register_routes(app)

    return app
