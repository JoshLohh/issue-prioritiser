from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os

# Environment variable for the database URL
DATABASE_URL = os.environ.get("DATABASE_URL")

if not DATABASE_URL:
    # Fallback for local development, assuming a local PostgreSQL named 'issue_prioritiser_db'
    # Local testing: 'postgresql://user:password@localhost/issue_prioritiser_db', must have local db server and db created
    print("DATABASE_URL environment variable not set. Using fallback for local development.")
    DATABASE_URL = "postgresql://user:password@localhost/issue_prioritiser_db" # Replace with local DB credentials if different

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Dependency to get a database session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
