from sqlalchemy import Column, Integer, String, Float, DateTime, Text, ARRAY, BigInteger, UniqueConstraint
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.dialects.postgresql import ARRAY as PG_ARRAY
import datetime

Base = declarative_base()

class Repo(Base):
    __tablename__ = "repos"

    id = Column(Integer, primary_key=True, index=True)
    owner = Column(String, nullable=False)
    name = Column(String, nullable=False)
    last_refreshed = Column(DateTime, nullable=False, default=datetime.datetime.now)

    __table_args__ = (UniqueConstraint('owner', 'name', name='_owner_name_uc'),)

class Issue(Base):
    __tablename__ = "issues"

    id = Column(BigInteger, primary_key=True, index=True)
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

__all__ = ["Repo", "Issue"]
