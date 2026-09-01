from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class GroupInfo:
    id: str
    owner_id: str
    name: str
    description: str = ""
    created_at: float = 0.0
    post_count: int = 0
    shared_with: List[str] = field(default_factory=list)


def _repo():
    import storage.repositories as repo
    return repo



def _db():
    from storage.db import get_session
    return get_session()


def _from_model(model, post_count: int = 0, shared_with: List[str] = None) -> GroupInfo:
    return GroupInfo(
        id=model.id,
        owner_id=model.owner_id,
        name=model.name,
        description=model.description or "",
        created_at=model.created_at or 0.0,
        post_count=post_count,
        shared_with=shared_with or [],
    )


def load_group(group_id: str) -> Optional[GroupInfo]:
    db = _db()
    try:
        model = _repo().get_group(db, group_id)
        if not model:
            return None
        count = _repo().count_posts_in_group(db, group_id)
        shared = _repo().list_group_shares(db, group_id)
        return _from_model(model, post_count=count, shared_with=shared)
    finally:
        db.close()


def load_group_by_name(owner_id: str, name: str) -> Optional[GroupInfo]:
    db = _db()
    try:
        model = _repo().get_group_by_name(db, owner_id, name)
        if not model:
            return None
        count = _repo().count_posts_in_group(db, model.id)
        shared = _repo().list_group_shares(db, model.id)
        return _from_model(model, post_count=count, shared_with=shared)
    finally:
        db.close()


def create_group(owner_id: str, name: str, description: str = "") -> GroupInfo:
    db = _db()
    try:
        model = _repo().create_group(db, owner_id, name, description)
        return _from_model(model)
    finally:
        db.close()


def list_groups_for_user(user_id: str) -> List[GroupInfo]:
    db = _db()
    try:
        models = _repo().list_groups_for_user(db, user_id)
        result = []
        for m in models:
            count = _repo().count_posts_in_group(db, m.id)
            shared = _repo().list_group_shares(db, m.id)
            result.append(_from_model(m, post_count=count, shared_with=shared))
        return result
    finally:
        db.close()


def delete_group(group_id: str) -> bool:
    db = _db()
    try:
        return _repo().delete_group(db, group_id)
    finally:
        db.close()


def get_post_ids_in_group(group_id: str) -> List[str]:
    db = _db()
    try:
        return _repo().get_post_ids_in_group(db, group_id)
    finally:
        db.close()


def add_post_to_group(group_id: str, post_id: str) -> bool:
    db = _db()
    try:
        return _repo().add_post_to_group(db, group_id, post_id)
    finally:
        db.close()


def remove_post_from_group(group_id: str, post_id: str) -> bool:
    db = _db()
    try:
        return _repo().remove_post_from_group(db, group_id, post_id)
    finally:
        db.close()


def share_group(group_id: str, user_id: str) -> bool:
    db = _db()
    try:
        return _repo().share_group(db, group_id, user_id)
    finally:
        db.close()


def unshare_group(group_id: str, user_id: str) -> bool:
    db = _db()
    try:
        return _repo().unshare_group(db, group_id, user_id)
    finally:
        db.close()


def user_can_access_group(user_id: str, group_id: str) -> bool:
    db = _db()
    try:
        return _repo().user_can_access_group(db, user_id, group_id)
    finally:
        db.close()
