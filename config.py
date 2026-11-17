# config.py
import os
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

class Config:
    SECRET_KEY = os.getenv("SECRET_KEY")
    ADMIN_MASTER_PASSWORD = os.getenv("ADMIN_MASTER_PASSWORD")

    DATABASE_PATH = os.path.join(BASE_DIR, 'instance', 'numer.db')

    POSTGRES_HOST = os.getenv("POSTGRES_HOST", "localhost")
    POSTGRES_PORT = os.getenv("POSTGRES_PORT", "5432")
    POSTGRES_DB = os.getenv("POSTGRES_DB", "unanum")
    POSTGRES_USER = os.getenv("POSTGRES_USER", "unanum")
    POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "")

    PAYWALL_PRICE_RUB = 599