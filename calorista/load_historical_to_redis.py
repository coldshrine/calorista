import json
import re
import sys
from pathlib import Path
from collections import defaultdict
from typing import Optional, Set
import redis
from redis.exceptions import ConnectionError
from urllib.parse import urlparse
import ssl
from datetime import datetime, timedelta

from utils.constants import REDIS_URL

# Constants
REDIS_FOOD_ENTRIES_PREFIX = "food_entries:"
REDIS_DATE_MAPPINGS_KEY = "date_mappings"

def convert_days_to_date(days_str: str) -> str:
    """Convert days since epoch to YYYY-MM-DD format"""
    try:
        days = int(days_str)
        date = datetime(1970, 1, 1) + timedelta(days=days)
        return date.strftime("%Y-%m-%d")
    except (ValueError, TypeError):
        return None

def get_existing_dates(redis_client: redis.Redis) -> Set[str]:
    """Get set of dates already in Redis"""
    existing_keys = redis_client.keys(f"{REDIS_FOOD_ENTRIES_PREFIX}*")
    return {key.decode().replace(REDIS_FOOD_ENTRIES_PREFIX, "") 
            for key in existing_keys} if existing_keys else set()

def create_redis_connection():
    """Create Redis connection compatible with older versions"""
    parsed = urlparse(REDIS_URL)
    return redis.StrictRedis(
        host=parsed.hostname,
        port=parsed.port,
        password=parsed.password,
        ssl=True,
        ssl_cert_reqs=None,
        decode_responses=False
    )

def process_file(file_path: Path, redis_client: redis.Redis) -> None:
    """Process JSON file and load only missing dates"""
    existing_dates = get_existing_dates(redis_client)
    loaded_dates = set()
    skipped_dates = set()
    
    with open(file_path, 'r', encoding='utf-8') as f:
        entries = json.load(f)
    
    # Group entries by date
    date_groups = defaultdict(list)
    for entry in entries:
        if date_int := entry.get("date_int"):
            human_date = convert_days_to_date(date_int)
            if human_date and human_date not in existing_dates:
                date_groups[human_date].append(entry)
    
    # Load missing dates
    for date, items in date_groups.items():
        redis_key = f"{REDIS_FOOD_ENTRIES_PREFIX}{date}"
        redis_client.set(redis_key, json.dumps(items))
        redis_client.hset(REDIS_DATE_MAPPINGS_KEY, date, items[0]['date_int'])
        loaded_dates.add(date)
        print(f"✅ Loaded {len(items)} entries for {date}")
    
    print(f"\n📊 Summary for {file_path.name}:")
    print(f"Loaded {len(loaded_dates)} new dates")
    print(f"Skipped {len(existing_dates)} existing dates")

def main():
    try:
        # Initialize Redis
        print("🔌 Connecting to Redis...")
        redis_client = create_redis_connection()
        redis_client.ping()
        print("✅ Connected successfully")
        
        # Process all historical files in order
        historical_dir = Path(__file__).resolve().parent.parent / "historical_food_data"
        files = sorted(historical_dir.glob("historical_food_entries_*_to_*.json"))
        
        if not files:
            print("❌ No historical files found")
            return
            
        for file_path in files:
            print(f"\n🔍 Processing {file_path.name}...")
            process_file(file_path, redis_client)
            
    except ConnectionError as e:
        print(f"❌ Redis connection failed: {e}")
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        if 'redis_client' in locals():
            redis_client.close()

if __name__ == "__main__":
    main()