import json
import os
import ssl
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import urlparse

import redis
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configuration
REDIS_FOOD_ENTRIES_PREFIX = "food_entries:"
REDIS_DATE_MAPPINGS_KEY = "date_mappings"
REDIS_URL = os.getenv("REDIS_URL")


def convert_days_to_date(days_str: str) -> str:
    """Convert days since epoch to YYYY-MM-DD format"""
    try:
        days = int(float(days_str))
        return (datetime(1970, 1, 1) + timedelta(days=days)).strftime("%Y-%m-%d")
    except (ValueError, TypeError):
        return None


def create_redis_connection():
    """Create Redis connection with proper SSL configuration"""
    parsed = urlparse(REDIS_URL)
    return redis.Redis(
        host=parsed.hostname,
        port=parsed.port,
        password=parsed.password,
        ssl=True,
        ssl_cert_reqs=ssl.CERT_NONE,
        decode_responses=False,
    )


def get_latest_file(directory: Path) -> Path:
    """Get the most recently created JSON file in the directory"""
    files = list(directory.glob("historical_food_entries_*.json"))
    if not files:
        raise FileNotFoundError("No historical files found")
    return max(files, key=lambda f: f.stat().st_ctime)


def get_existing_entry_ids(redis_client: redis.Redis, date: str) -> set:
    """Get set of entry IDs already in Redis for a specific date"""
    redis_key = f"{REDIS_FOOD_ENTRIES_PREFIX}{date}"
    if not redis_client.exists(redis_key):
        return set()

    entries = json.loads(redis_client.get(redis_key))
    return {entry["id"] for entry in entries if "id" in entry}


def process_latest_file(redis_client: redis.Redis):
    """Properly handles incremental loading of new entries"""
    historical_dir = Path(__file__).parent.parent / "food"
    file_path = get_latest_file(historical_dir)
    print(f"🔍 Processing latest file: {file_path.name}")

    with open(file_path, "r", encoding="utf-8") as f:
        entries = json.load(f)

    date_groups = defaultdict(list)
    loaded_count = 0
    skipped_count = 0

    for entry in entries:
        if "date_int" not in entry:
            skipped_count += 1
            continue

        human_date = convert_days_to_date(entry["date_int"])
        if not human_date:
            skipped_count += 1
            continue

        # Always add to processing - we'll handle duplicates during merge
        date_groups[human_date].append(entry)
        loaded_count += 1

    # Improved merge logic
    for date, new_entries in date_groups.items():
        redis_key = f"{REDIS_FOOD_ENTRIES_PREFIX}{date}"

        existing_entries = []
        if redis_client.exists(redis_key):
            existing_entries = json.loads(redis_client.get(redis_key))

        # Create a set of existing entry hashes for comparison
        existing_hashes = {hash_entry(e) for e in existing_entries}

        # Only add truly new entries
        merged_entries = existing_entries + [
            e for e in new_entries if hash_entry(e) not in existing_hashes
        ]

        if len(merged_entries) > len(existing_entries):
            redis_client.set(redis_key, json.dumps(merged_entries))
            redis_client.hset(
                REDIS_DATE_MAPPINGS_KEY, date, str(new_entries[0]["date_int"])
            )
            print(
                f"✅ Added {len(merged_entries) - len(existing_entries)} new entries for {date}"
            )
        else:
            print(f"⏩ No new entries for {date} (already exists)")

    print("\n📊 Final Summary:")
    print(f"Total entries processed: {len(entries)}")
    print(f"Entries available for loading: {loaded_count}")
    print(f"Entries skipped (invalid): {skipped_count}")


def hash_entry(entry: dict) -> str:
    """Create a unique hash for an entry using multiple fields"""
    return hash(
        frozenset(
            {
                "food": entry.get("food_entry_name", ""),
                "meal": entry.get("meal", ""),
                "time": entry.get("timestamp", ""),
                "date_int": entry.get("date_int", ""),
                "calories": entry.get("calories", 0),
            }.items()
        )
    )


def main():
    try:
        if not REDIS_URL:
            print("❌ REDIS_URL environment variable not found")
            return

        print("🔌 Connecting to Redis...")
        redis_client = create_redis_connection()
        redis_client.ping()
        print("✅ Connected successfully")

        process_latest_file(redis_client)

    except Exception as e:
        print(f"❌ Error: {str(e)}")
    finally:
        if "redis_client" in locals():
            redis_client.close()


if __name__ == "__main__":
    main()
