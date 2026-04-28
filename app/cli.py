import os
from dotenv import load_dotenv
from werkzeug.security import generate_password_hash

load_dotenv()

from app.db.base import SessionLocal
from app.models.user import User


def create_admin():
    email = input("Email admina: ")
    password = input("Hasło admina: ")
    db = SessionLocal()
    if db.query(User).filter_by(email=email).first():
        print("Użytkownik już istnieje.")
        db.close()
        return
    user = User(
        email=email,
        password_hash=generate_password_hash(password),
        role="admin"
    )
    db.add(user)
    db.commit()
    db.close()
    print(f"Admin {email} utworzony.")


if __name__ == "__main__":
    create_admin()
