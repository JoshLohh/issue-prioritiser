from sqlalchemy import Column, Integer, String, Float, DateTime, Text, ARRAY
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.dialects.postgresql import ARRAY as PG_ARRAY
import datetime

Base = declarative_base()

class Issue(Base):
    __tablename__ = "issues"

    id = Column(Integer, primary_key=True, index=True)
    number = Column(Integer, unique=True, index=True, nullable=False)
    title = Column(String, index=True, nullable=False)
    user = Column(String, nullable=False)
    state = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.now, nullable=False)
    updated_at = Column(DateTime, default=datetime.datetime.now, onupdate=datetime.datetime.now, nullable=False)
    labels = Column(PG_ARRAY(String), nullable=False, default=[]) # Use PG_ARRAY for PostgreSQL array type
    html_url = Column(String, nullable=False)
    priority_score = Column(Float, nullable=False)
    friendliness_score = Column(Float, nullable=False)
