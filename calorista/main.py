import json
import os
import ssl
from collections import defaultdict
from datetime import datetime, timedelta, date
from pathlib import Path
from typing import Any, Dict, List
from urllib.parse import urlparse

import redis
from dotenv import load_dotenv
import pytz

from utils.api import FatSecretAPI
from utils.auth import FatSecretAuth

load_dotenv()

REDIS_FOOD_ENTRIES_PREFIX = "food_entries:"
REDIS_DATE_MAPPINGS_KEY = "date_mappings"
REDIS_URL = os.getenv("REDIS_URL")

KYIV_TZ = pytz.timezone('Europe/Kiev')


def get_current_date() -> date:
    """Get current date in Kyiv timezone"""
    kyiv_time = datetime.now(KYIV_TZ)
    print(f"\nCurrent time in Kyiv: {kyiv_time}")
    return kyiv_time.date()


def convert_days_to_date(days_str: str) -> str:
    try:
        days = int(float(days_str))
        return (datetime(1970, 1, 1) + timedelta(days=days)).strftime("%Y-%m-%d")
    except (ValueError, TypeError):
        return None


def create_redis_connection():
    parsed = urlparse(REDIS_URL)
    return redis.Redis(
        host=parsed.hostname,
        port=parsed.port,
        password=parsed.password,
        ssl=True,
        ssl_cert_reqs=ssl.CERT_NONE,
        decode_responses=False,
    )


def create_entry_fingerprint(entry: dict) -> str:
    """Create a unique fingerprint for an entry to detect duplicates"""
    return f"{entry.get('food_entry_id', '')}_{entry.get('date_int', '')}_{entry.get('timestamp', '')}"


def get_historical_entries(api: FatSecretAPI, start_date: str, end_date: str) -> List[Dict[str, Any]]:
    """Fetch historical entries with duplicate detection, safely handling skipped days"""
    all_entries: List[Dict[str, Any]] = []
    seen_entries = set()

    try:
        print(f"\nFetching historical food entries from {start_date} to {end_date}...")
        historical_entries = api.get_historical_food_entries(start_date, end_date)

        if not historical_entries:
            print("⚠️ No historical entries received from API")
            return all_entries

        for daily_result in historical_entries:
            # Handle None or unexpected structures
            if not daily_result or not isinstance(daily_result, dict):
                continue

            food_entries_container = daily_result.get("food_entries")
            if not food_entries_container:
                # This is a valid "empty day" → just continue
                continue

            entries = food_entries_container.get("food_entry", [])
            if isinstance(entries, dict):
                entries = [entries]

            for entry in entries:
                if not isinstance(entry, dict):
                    continue
                if not entry.get("food_entry_id"):
                    continue

                fingerprint = create_entry_fingerprint(entry)
                if fingerprint not in seen_entries:
                    seen_entries.add(fingerprint)
                    all_entries.append(entry)
                else:
                    print(
                        f"⚠️ Duplicate entry skipped: "
                        f"{entry.get('food_entry_name', 'unknown')} on {entry.get('date_int')}"
                    )

        print(f"\n✅ Retrieved {len(all_entries)} unique historical food entries.")
        return all_entries

    except Exception as e:
        print(f"⚠️ Error processing historical entries: {e}")
        return all_entries


def load_entries_to_redis(redis_client: redis.Redis, entries: List[Dict[str, Any]]):
    date_groups = defaultdict(list)
    loaded_count = 0
    skipped_count = 0

    for entry in entries:
        if "date_int" not in entry or "food_entry_id" not in entry:
            skipped_count += 1
            continue

        human_date = convert_days_to_date(entry["date_int"])
        if not human_date:
            skipped_count += 1
            continue

        date_groups[human_date].append(entry)
        loaded_count += 1

    for date, new_entries in date_groups.items():
        redis_key = f"{REDIS_FOOD_ENTRIES_PREFIX}{date}"

        existing_entries = []
        if redis_client.exists(redis_key):
            existing_entries = json.loads(redis_client.get(redis_key))

        existing_fingerprints = {
            create_entry_fingerprint(e): e 
            for e in existing_entries 
            if "food_entry_id" in e
        }

        entries_to_update = []
        for entry in new_entries:
            fingerprint = create_entry_fingerprint(entry)
            if fingerprint not in existing_fingerprints:
                entries_to_update.append(entry)
            elif entry != existing_fingerprints[fingerprint]:
                entries_to_update.append(entry)

        if entries_to_update:
            updated_entries = [
                e for e in existing_entries
                if create_entry_fingerprint(e) not in 
                   {create_entry_fingerprint(ne) for ne in entries_to_update}
            ]
            updated_entries.extend(entries_to_update)
            
            redis_client.set(redis_key, json.dumps(updated_entries))
            redis_client.hset(REDIS_DATE_MAPPINGS_KEY, date, str(new_entries[0]["date_int"]))
            print(f"✅ Updated {len(entries_to_update)} entries for {date}")
        else:
            print(f"⏩ No changes needed for {date}")

    print("\n📊 Final Summary:")
    print(f"Total entries processed: {len(entries)}")
    print(f"Entries available for loading: {loaded_count}")
    print(f"Entries skipped (invalid): {skipped_count}")


def main():
    try:
        BASE_DIR = Path(__file__).resolve().parent.parent
        token_file = BASE_DIR / "auth_tokens" / "tokens.json"
        if not token_file.exists():
            print(f"❌ Token file not found at: {token_file}")
            return
            
        auth = FatSecretAuth(token_file=str(token_file))
        api = FatSecretAPI(auth)

        try:
            profile = api.get_user_weight()
            print(f"Hello! Your current weight is {profile.last_weight_kg}kg")
        except Exception as e:
            print(f"⚠️ Error getting weight profile: {e}")

        today = get_current_date()
        today_str = today.strftime("%Y-%m-%d")

        start_date = "2025-04-07"
        all_entries = get_historical_entries(api, start_date, today_str)

        if not all_entries:
            print("No entries to process")
            return

        if not REDIS_URL:
            print("❌ REDIS_URL environment variable not found")
            return

        print("🔌 Connecting to Redis...")
        redis_client = create_redis_connection()
        redis_client.ping()
        print("✅ Connected successfully")

        load_entries_to_redis(redis_client, all_entries)

    except Exception as e:
        print(f"❌ Error: {str(e)}")
    finally:
        if "redis_client" in locals():
            redis_client.close()


if __name__ == "__main__":
    main()