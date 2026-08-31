"""SQLAlchemy models for persistent storage."""
from sqlalchemy import JSON, Boolean, Column, Float, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


class Profile(Base):
    __tablename__ = "profiles"

    username = Column(String, primary_key=True)
    interests = Column(Text, default="")
    max_posts = Column(Integer, default=50)
    analysis_mode = Column(String, default="gemini")
    audio_only = Column(Boolean, default=False)
    processed_ids = Column(JSON, default=list)
    failed_ids = Column(JSON, default=list)
    # Tracking when the profile was last successfully scraped (Unix timestamp)
    last_scraped_at = Column(Float, nullable=True, default=None)
    # ISO-8601 string of the last pipeline run start time
    last_run_at = Column(String, nullable=True, default=None)


class Setting(Base):
    __tablename__ = "settings"

    key = Column(String, primary_key=True)
    value = Column(JSON)


class SavedPost(Base):
    __tablename__ = "saved_posts"

    id = Column(String, primary_key=True)
    url = Column(String, default="")
    caption = Column(Text, default="")
    title = Column(Text, default="")
    timestamp = Column(Float, default=0)


class SavedState(Base):
    __tablename__ = "saved_state"

    id = Column(Integer, primary_key=True, default=1)
    total = Column(Integer, default=0)
    imported_at = Column(String, default="")
    source = Column(String, default="")
    processed_ids = Column(JSON, default=list)
    failed_ids = Column(JSON, default=list)


class ProcessedPost(Base):
    __tablename__ = "processed_posts"

    id = Column(String, primary_key=True)
    url = Column(String, default="")
    username = Column(String, default="")
    type = Column(String, default="Post")
    original_description = Column(Text, default="")
    extracted_knowledge = Column(Text, default="")
