from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# Usamos SQLite para empezar rápido y fácil
SQLALCHEMY_DATABASE_URL = "postgresql://postgres:xvm8e8Mc2wJ7ZG28@db.rzjhvfhljljkdsvpquwh.supabase.co:5432/postgres"

engine = create_engine(SQLALCHEMY_DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()