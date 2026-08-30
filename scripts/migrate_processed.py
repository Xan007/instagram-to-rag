"""Migrate data/processed/*.json files to the database.

Run with: uv run python scripts/migrate_processed.py
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from storage.db import get_session, init_db
from storage.models import ProcessedPost
import storage.repositories as repo


def migrate():
    processed_dir = Path("data/processed")
    if not processed_dir.exists():
        print("No data/processed/ directory found. Nothing to migrate.")
        return

    json_files = list(processed_dir.glob("*.json"))
    if not json_files:
        print("No JSON files found in data/processed/. Nothing to migrate.")
        return

    print(f"Found {len(json_files)} JSON files to migrate.")

    init_db()
    db = get_session()

    migrated = 0
    skipped = 0
    errors = 0

    for file_path in json_files:
        try:
            data = json.loads(file_path.read_text(encoding="utf-8"))
            post_id = data.get("id")
            if not post_id:
                skipped += 1
                continue

            existing = repo.get_processed_post(db, post_id)
            if existing:
                skipped += 1
                continue

            post = ProcessedPost(
                id=post_id,
                url=data.get("url", ""),
                username=data.get("username", ""),
                type=data.get("type", "Post"),
                original_description=data.get("original_description", ""),
                extracted_knowledge=data.get("extracted_knowledge", ""),
            )
            repo.upsert_processed_post(db, post)
            migrated += 1

            if migrated % 50 == 0:
                print(f"  Migrated {migrated} posts...")

        except Exception as e:
            print(f"  Error migrating {file_path.name}: {e}")
            errors += 1

    db.close()
    print(f"\nMigration complete: {migrated} migrated, {skipped} skipped, {errors} errors.")


if __name__ == "__main__":
    migrate()
