import os
from sqlalchemy import create_engine
from dotenv import load_dotenv 
# Import your Base and all models that inherit from it
from models import Base 
print("Loading environment variables...")
load_dotenv()
DATABASE_URL = os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("DATABASE_URL environment variable is not set.")

print(f"Connecting to database...")
engine = create_engine(DATABASE_URL)

try:
    print("Creating all tables based on models...")
    # The Base.metadata object contains all the schema information of your models
    Base.metadata.create_all(bind=engine)
    print("Tables created successfully!")
except Exception as e:
    print(f"An error occurred during table creation: {e}")