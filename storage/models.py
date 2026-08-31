"""SQLAlchemy models for persistent storage.

Architecture:
- User          : local application account
- IGProfile     : global Instagram profile (scraped once, shared)
- Post          : globally deduplicated extracted post (one per IG shortcode)
- Group         : user-owned RAG agent (collection of posts)
- GroupPost     : many-to-many Group <-> Post
- GroupShare    : users who have read access to a group
- UserSavedPost : posts the user bookmarked from their IG export
- Setting       : key/value store for app-wide config
"""
import time

from sqlalchemy import Boolean, Column, Float, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


# ── Application users ─────────────────────────────────────────────────────────

class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True)         # UUID
    username = Column(String, unique=True, nullable=False)
    created_at = Column(Float, default=time.time)


# ── Global Instagram profiles ─────────────────────────────────────────────────

class IGProfile(Base):
    """A tracked Instagram creator profile. Shared globally — scraped once."""
    __tablename__ = "ig_profiles"

    username = Column(String, primary_key=True)
    # Timestamps for incremental updates
    last_scraped_at = Column(Float, nullable=True, default=None)
    last_run_at = Column(String, nullable=True, default=None)
    # Number of posts scraped in total (informational)
    total_posts_scraped = Column(Integer, default=0)


# ── Globally deduplicated posts ───────────────────────────────────────────────

class Post(Base):
    """A processed Instagram post. Created once per shortcode, shared by all users."""
    __tablename__ = "posts"

    id = Column(String, primary_key=True)           # IG shortcode
    url = Column(String, default="")
    creator_username = Column(String, default="")   # nullable for manually added reels
    type = Column(String, default="Post")           # Post | Reel | Sidecar | Image | Video
    description = Column(Text, default="")          # original caption
    extracted_knowledge = Column(Text, default="")  # Gemini/Whisper output
    indexed_at = Column(Float, nullable=True)        # when upserted into Pinecone


# ── User groups (RAG agents) ──────────────────────────────────────────────────

class Group(Base):
    """A user-owned named collection of posts that acts as a scoped RAG agent."""
    __tablename__ = "groups"

    id = Column(String, primary_key=True)           # UUID
    owner_id = Column(String, ForeignKey("users.id"), nullable=False)
    name = Column(String, nullable=False)
    description = Column(Text, default="")
    created_at = Column(Float, default=time.time)

    __table_args__ = (
        UniqueConstraint("owner_id", "name", name="uq_group_owner_name"),
    )


class GroupPost(Base):
    """Many-to-many: which posts belong to a group."""
    __tablename__ = "group_posts"

    group_id = Column(String, ForeignKey("groups.id"), primary_key=True)
    post_id = Column(String, ForeignKey("posts.id"), primary_key=True)
    added_at = Column(Float, default=time.time)


class GroupShare(Base):
    """Grants a user read access to another user's group."""
    __tablename__ = "group_shares"

    group_id = Column(String, ForeignKey("groups.id"), primary_key=True)
    user_id = Column(String, ForeignKey("users.id"), primary_key=True)


# ── User saved posts (bookmarks from IG export) ───────────────────────────────

class UserSavedPost(Base):
    """Posts the user bookmarked via their Instagram data export."""
    __tablename__ = "user_saved_posts"

    user_id = Column(String, ForeignKey("users.id"), primary_key=True)
    post_id = Column(String, ForeignKey("posts.id"), primary_key=True)
    saved_at = Column(Float, default=time.time)
    source_url = Column(String, default="")         # original URL from the export


# ── Import state for saved posts (per user) ───────────────────────────────────

class UserSavedState(Base):
    """Tracks the last IG export import for a given user."""
    __tablename__ = "user_saved_states"

    user_id = Column(String, ForeignKey("users.id"), primary_key=True)
    total = Column(Integer, default=0)
    imported_at = Column(String, default="")
    source = Column(String, default="")


# ── App-wide key/value settings ───────────────────────────────────────────────

class Setting(Base):
    __tablename__ = "settings"

    key = Column(String, primary_key=True)
    value = Column(JSON)
