import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from storage.db import get_session, init_db
from storage.models import Post
import storage.repositories as repo


def migrate() -> None:
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

            existing = repo.get_post(db, post_id)
            if existing:
                skipped += 1
                continue

            post = Post(
                id=post_id,
                url=data.get("url", ""),
                creator_username=data.get("creator_username") or data.get("username", ""),
                type=data.get("type", "Post"),
                description=data.get("original_description") or data.get("description", ""),
                extracted_knowledge=data.get("extracted_knowledge", ""),
            )
            repo.upsert_post(db, post)
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

