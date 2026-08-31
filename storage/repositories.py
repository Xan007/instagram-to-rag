"""Repository layer — all DB access lives here.

Each function takes a Session and returns ORM objects or primitives.
Callers are responsible for opening/closing the session.
"""
from typing import List, Optional
import uuid
import time

from sqlalchemy.orm import Session

from storage.models import (
    Group,
    GroupPost,
    GroupShare,
    IGProfile,
    Post,
    Setting,
    User,
    UserSavedPost,
    UserSavedState,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _new_uuid() -> str:
    return str(uuid.uuid4())


# ── Settings ──────────────────────────────────────────────────────────────────

def get_setting(db: Session, key: str) -> Optional[dict]:
    row = db.query(Setting).filter(Setting.key == key).first()
    return row.value if row else None


def set_setting(db: Session, key: str, value: dict) -> None:
    row = db.query(Setting).filter(Setting.key == key).first()
    if row:
        row.value = value
    else:
        db.add(Setting(key=key, value=value))
    db.commit()


def get_all_settings(db: Session) -> dict:
    return {row.key: row.value for row in db.query(Setting).all()}


# ── Users ─────────────────────────────────────────────────────────────────────

def get_user_by_id(db: Session, user_id: str) -> Optional[User]:
    return db.query(User).filter(User.id == user_id).first()


def get_user_by_username(db: Session, username: str) -> Optional[User]:
    return db.query(User).filter(User.username == username).first()


def list_users(db: Session) -> List[User]:
    return db.query(User).all()


def create_user(db: Session, username: str) -> User:
    user = User(id=_new_uuid(), username=username, created_at=time.time())
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def delete_user(db: Session, user_id: str) -> bool:
    user = get_user_by_id(db, user_id)
    if not user:
        return False
    db.delete(user)
    db.commit()
    return True


# ── IGProfiles (global) ───────────────────────────────────────────────────────

def get_ig_profile(db: Session, username: str) -> Optional[IGProfile]:
    return db.query(IGProfile).filter(IGProfile.username == username).first()


def list_ig_profiles(db: Session) -> List[IGProfile]:
    return db.query(IGProfile).all()


def upsert_ig_profile(db: Session, profile: IGProfile) -> IGProfile:
    existing = get_ig_profile(db, profile.username)
    if existing:
        if profile.last_scraped_at is not None:
            existing.last_scraped_at = profile.last_scraped_at
        if profile.last_run_at is not None:
            existing.last_run_at = profile.last_run_at
        if profile.total_posts_scraped is not None:
            existing.total_posts_scraped = profile.total_posts_scraped
        db.commit()
        db.refresh(existing)
        return existing
    db.add(profile)
    db.commit()
    db.refresh(profile)
    return profile


def delete_ig_profile(db: Session, username: str) -> bool:
    profile = get_ig_profile(db, username)
    if not profile:
        return False
    db.delete(profile)
    db.commit()
    return True


# ── Posts (global, deduplicated) ──────────────────────────────────────────────

def get_post(db: Session, post_id: str) -> Optional[Post]:
    return db.query(Post).filter(Post.id == post_id).first()


def upsert_post(db: Session, post: Post) -> Post:
    existing = get_post(db, post.id)
    if existing:
        existing.url = post.url or existing.url
        existing.creator_username = post.creator_username or existing.creator_username
        existing.type = post.type or existing.type
        existing.description = post.description or existing.description
        existing.extracted_knowledge = post.extracted_knowledge or existing.extracted_knowledge
        if post.indexed_at is not None:
            existing.indexed_at = post.indexed_at
        db.commit()
        db.refresh(existing)
        return existing
    db.add(post)
    db.commit()
    db.refresh(post)
    return post


def list_posts(db: Session, creator_username: Optional[str] = None) -> List[Post]:
    q = db.query(Post)
    if creator_username:
        q = q.filter(Post.creator_username == creator_username)
    return q.all()


def count_posts(db: Session, creator_username: Optional[str] = None) -> int:
    q = db.query(Post)
    if creator_username:
        q = q.filter(Post.creator_username == creator_username)
    return q.count()


def get_all_post_ids(db: Session, creator_username: Optional[str] = None) -> List[str]:
    q = db.query(Post.id)
    if creator_username:
        q = q.filter(Post.creator_username == creator_username)
    return [row[0] for row in q.all()]


# ── Groups ────────────────────────────────────────────────────────────────────

def get_group(db: Session, group_id: str) -> Optional[Group]:
    return db.query(Group).filter(Group.id == group_id).first()


def get_group_by_name(db: Session, owner_id: str, name: str) -> Optional[Group]:
    return (
        db.query(Group)
        .filter(Group.owner_id == owner_id, Group.name == name)
        .first()
    )


def list_groups_for_user(db: Session, user_id: str) -> List[Group]:
    """Own groups + groups shared with this user."""
    owned = db.query(Group).filter(Group.owner_id == user_id).all()
    shared_ids = [
        row.group_id
        for row in db.query(GroupShare).filter(GroupShare.user_id == user_id).all()
    ]
    shared = db.query(Group).filter(Group.id.in_(shared_ids)).all() if shared_ids else []
    return owned + [g for g in shared if g.id not in {o.id for o in owned}]


def create_group(db: Session, owner_id: str, name: str, description: str = "") -> Group:
    group = Group(
        id=_new_uuid(),
        owner_id=owner_id,
        name=name,
        description=description,
        created_at=time.time(),
    )
    db.add(group)
    db.commit()
    db.refresh(group)
    return group


def delete_group(db: Session, group_id: str) -> bool:
    group = get_group(db, group_id)
    if not group:
        return False
    # Cascade: remove group posts and shares
    db.query(GroupPost).filter(GroupPost.group_id == group_id).delete()
    db.query(GroupShare).filter(GroupShare.group_id == group_id).delete()
    db.delete(group)
    db.commit()
    return True


# ── GroupPosts ────────────────────────────────────────────────────────────────

def add_post_to_group(db: Session, group_id: str, post_id: str) -> bool:
    """Add post to group; returns False if already present."""
    existing = (
        db.query(GroupPost)
        .filter(GroupPost.group_id == group_id, GroupPost.post_id == post_id)
        .first()
    )
    if existing:
        return False
    db.add(GroupPost(group_id=group_id, post_id=post_id, added_at=time.time()))
    db.commit()
    return True


def remove_post_from_group(db: Session, group_id: str, post_id: str) -> bool:
    deleted = (
        db.query(GroupPost)
        .filter(GroupPost.group_id == group_id, GroupPost.post_id == post_id)
        .delete()
    )
    db.commit()
    return deleted > 0


def get_post_ids_in_group(db: Session, group_id: str) -> List[str]:
    return [
        row.post_id
        for row in db.query(GroupPost).filter(GroupPost.group_id == group_id).all()
    ]


def count_posts_in_group(db: Session, group_id: str) -> int:
    return db.query(GroupPost).filter(GroupPost.group_id == group_id).count()


# ── GroupShares ───────────────────────────────────────────────────────────────

def share_group(db: Session, group_id: str, user_id: str) -> bool:
    existing = (
        db.query(GroupShare)
        .filter(GroupShare.group_id == group_id, GroupShare.user_id == user_id)
        .first()
    )
    if existing:
        return False
    db.add(GroupShare(group_id=group_id, user_id=user_id))
    db.commit()
    return True


def unshare_group(db: Session, group_id: str, user_id: str) -> bool:
    deleted = (
        db.query(GroupShare)
        .filter(GroupShare.group_id == group_id, GroupShare.user_id == user_id)
        .delete()
    )
    db.commit()
    return deleted > 0


def list_group_shares(db: Session, group_id: str) -> List[str]:
    """Return user_ids that have read access to this group."""
    return [
        row.user_id
        for row in db.query(GroupShare).filter(GroupShare.group_id == group_id).all()
    ]


def user_can_access_group(db: Session, user_id: str, group_id: str) -> bool:
    """True if the user owns or has shared access to the group."""
    group = get_group(db, group_id)
    if not group:
        return False
    if group.owner_id == user_id:
        return True
    return (
        db.query(GroupShare)
        .filter(GroupShare.group_id == group_id, GroupShare.user_id == user_id)
        .first()
        is not None
    )


# ── UserSavedPosts ────────────────────────────────────────────────────────────

def add_user_saved_post(db: Session, user_id: str, post_id: str, source_url: str = "") -> bool:
    existing = (
        db.query(UserSavedPost)
        .filter(UserSavedPost.user_id == user_id, UserSavedPost.post_id == post_id)
        .first()
    )
    if existing:
        return False
    db.add(UserSavedPost(user_id=user_id, post_id=post_id, saved_at=time.time(), source_url=source_url))
    db.commit()
    return True


def get_user_saved_post_ids(db: Session, user_id: str) -> List[str]:
    return [
        row.post_id
        for row in db.query(UserSavedPost).filter(UserSavedPost.user_id == user_id).all()
    ]


def count_user_saved_posts(db: Session, user_id: str) -> int:
    return db.query(UserSavedPost).filter(UserSavedPost.user_id == user_id).count()


# ── UserSavedState ────────────────────────────────────────────────────────────

def get_user_saved_state(db: Session, user_id: str) -> UserSavedState:
    state = db.query(UserSavedState).filter(UserSavedState.user_id == user_id).first()
    if not state:
        state = UserSavedState(user_id=user_id)
        db.add(state)
        db.commit()
        db.refresh(state)
    return state


def save_user_saved_state(db: Session, state: UserSavedState) -> None:
    db.commit()
