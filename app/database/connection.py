import os

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

load_dotenv()

database_url_env = os.getenv('DATABASE_URL', '').strip()
if database_url_env:
    if database_url_env.startswith("mysql://"):
        DATABASE_URL = database_url_env.replace("mysql://", "mysql+pymysql://", 1)
    else:
        DATABASE_URL = database_url_env
else:
    DB_USER = os.getenv('DB_USER', 'root')
    DB_PASSWORD = os.getenv('DB_PASSWORD', '')
    DB_HOST = os.getenv('DB_HOST', '127.0.0.1')
    DB_PORT = os.getenv('DB_PORT', '3306')
    DB_NAME = os.getenv('DB_NAME', 'vitalia')

    if DB_PASSWORD:
        USER_PASS = f"{DB_USER}:{DB_PASSWORD}"
    else:
        USER_PASS = f"{DB_USER}"

    DATABASE_URL = f"mysql+pymysql://{USER_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

engine = create_engine(
    DATABASE_URL,
    connect_args={"connect_timeout": 5},
    echo=False
)

SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False
)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()
