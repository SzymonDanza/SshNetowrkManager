import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from dotenv import load_dotenv

load_dotenv()


class Base(DeclarativeBase):
    pass

def get_engine():
    return create_engine(os.environ["DATABASE_URL"])

SessionLocal = sessionmaker()