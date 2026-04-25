import os
from cryptography.fernet import Fernet
from dotenv import load_dotenv

load_dotenv()


def encrypt_password(plain: str) -> str:
    key = os.environ["ENCRYPTION_KEY"].encode()
    return Fernet(key).encrypt(plain.encode()).decode()


def decrypt_password(encrypted: str) -> str:
    key = os.environ["ENCRYPTION_KEY"].encode()
    return Fernet(key).decrypt(encrypted.encode()).decode()


def generate_key() -> str:
    return Fernet.generate_key().decode()
