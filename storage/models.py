from datetime import datetime, timezone
import time
from typing import Optional

from sqlalchemy import Boolean, Column, Float, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True)
    username = Column(String, unique=True, nullable=False)
    created_at = Column(Float, default=time.time)


class IGProfile(Base):
    __tablename__ = "ig_profiles"

    username = Column(String, primary_key=True)
    last_scraped_at = Column(Float, nullable=True, default=None)
    last_run_at = Column(String, nullable=True, default=None)
    total_posts_scraped = Column(Integer, default=0)
    interests = Column(String, default="")
    max_posts = Column(Integer, default=50)
    processed_ids = Column(JSON, default=list)
    failed_ids = Column(JSON, default=list)
    analysis_mode = Column(String, default="gemini")
    audio_only = Column(Boolean, default=False)


Profile = IGProfile


class Post(Base):
    __tablename__ = "posts"

    id = Column(String, primary_key=True)
    url = Column(String, default="")
    creator_username = Column(String, default="")
    type = Column(String, default="Post")
    description = Column(Text, default="")
    extracted_knowledge = Column(Text, default="")
    indexed_at = Column(Float, nullable=True)


ProcessedPost = Post


class Group(Base):
    __tablename__ = "groups"

    id = Column(String, primary_key=True)
    owner_id = Column(String, ForeignKey("users.id"), nullable=False)
    name = Column(String, nullable=False)
    description = Column(Text, default="")
    created_at = Column(Float, default=time.time)

    __table_args__ = (
        UniqueConstraint("owner_id", "name", name="uq_group_owner_name"),
    )


class GroupPost(Base):
    __tablename__ = "group_posts"

    group_id = Column(String, ForeignKey("groups.id"), primary_key=True)
    post_id = Column(String, ForeignKey("posts.id"), primary_key=True)
    added_at = Column(Float, default=time.time)


class GroupShare(Base):
    __tablename__ = "group_shares"

    group_id = Column(String, ForeignKey("groups.id"), primary_key=True)
    user_id = Column(String, ForeignKey("users.id"), primary_key=True)


class UserSavedPost(Base):
    __tablename__ = "user_saved_posts"

    user_id = Column(String, ForeignKey("users.id"), primary_key=True)
    post_id = Column(String, ForeignKey("posts.id"), primary_key=True)
    saved_at = Column(Float, default=time.time)
    source_url = Column(String, default="")


SavedPost = UserSavedPost


class UserSavedState(Base):
    __tablename__ = "user_saved_states"

    user_id = Column(String, ForeignKey("users.id"), primary_key=True)
    total = Column(Integer, default=0)
    imported_at = Column(String, default="")
    source = Column(String, default="")
    processed_ids = Column(JSON, default=list)
    failed_ids = Column(JSON, default=list)


class Setting(Base):
    __tablename__ = "settings"

    key = Column(String, primary_key=True)
    value = Column(JSON)

