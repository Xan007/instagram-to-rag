import time
from typing import List, Optional
import uuid

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


def _new_uuid() -> str:
    return str(uuid.uuid4())


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
        if profile.interests is not None:
            existing.interests = profile.interests
        if profile.max_posts is not None:
            existing.max_posts = profile.max_posts
        if profile.processed_ids is not None:
            existing.processed_ids = profile.processed_ids
        if profile.failed_ids is not None:
            existing.failed_ids = profile.failed_ids
        if profile.analysis_mode is not None:
            existing.analysis_mode = profile.analysis_mode
        if profile.audio_only is not None:
            existing.audio_only = profile.audio_only
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


get_profile = get_ig_profile
list_profiles = list_ig_profiles
upsert_profile = upsert_ig_profile
delete_profile = delete_ig_profile


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


get_processed_post = get_post
upsert_processed_post = upsert_post


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


def get_group(db: Session, group_id: str) -> Optional[Group]:
    return db.query(Group).filter(Group.id == group_id).first()


def get_group_by_name(db: Session, owner_id: str, name: str) -> Optional[Group]:
    return (
        db.query(Group)
        .filter(Group.owner_id == owner_id, Group.name == name)
        .first()
    )


def list_groups_for_user(db: Session, user_id: str) -> List[Group]:
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
    db.query(GroupPost).filter(GroupPost.group_id == group_id).delete()
    db.query(GroupShare).filter(GroupShare.group_id == group_id).delete()
    db.delete(group)
    db.commit()
    return True


def add_post_to_group(db: Session, group_id: str, post_id: str) -> bool:
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
    return [
        row.user_id
        for row in db.query(GroupShare).filter(GroupShare.group_id == group_id).all()
    ]


def user_can_access_group(db: Session, user_id: str, group_id: str) -> bool:
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


def get_saved_state(db: Session, user_id: str = "default") -> UserSavedState:
    return get_user_saved_state(db, user_id)


def save_saved_state(db: Session, state: UserSavedState) -> None:
    save_user_saved_state(db, state)


def upsert_saved_posts_bulk(db: Session, posts: List[UserSavedPost]) -> None:
    for p in posts:
        existing = (
            db.query(UserSavedPost)
            .filter(UserSavedPost.user_id == p.user_id, UserSavedPost.post_id == p.post_id)
            .first()
        )
        if not existing:
            db.add(p)
    db.commit()

