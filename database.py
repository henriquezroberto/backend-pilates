from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# Usamos SQLite para empezar rápido y fácil
SQLALCHEMY_DATABASE_URL = "postgresql://postgres.rzjhvfhljljkdsvpquwh:xvm8e8Mc2wJ7ZG28@aws-1-us-west-2.pooler.supabase.com:6543/postgres"

engine = create_engine(SQLALCHEMY_DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()