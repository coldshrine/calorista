import json
import os
import sys
from pathlib import Path
from collections import defaultdict
import redis
from datetime import datetime, timedelta
from dotenv import load_dotenv
import ssl
from urllib.parse import urlparse

# Load environment variables
load_dotenv()

# Constants
REDIS_FOOD_ENTRIES_PREFIX = "food_entries:"
REDIS_DATE_MAPPINGS_KEY = "date_mappings"
REDIS_URL = os.getenv("REDIS_URL")

def convert_days_to_date(days_str: str) -> str:
    """Convert days since epoch to YYYY-MM-DD format"""
    try:
        days = int(float(days_str))
        date = datetime(1970, 1, 1) + timedelta(days=days)
        return date.strftime("%Y-%m-%d")
    except (ValueError, TypeError):
        return None

def get_existing_dates(redis_client: redis.Redis) -> set:
    """Get set of dates already in Redis"""
    try:
        existing_keys = redis_client.keys(f"{REDIS_FOOD_ENTRIES_PREFIX}*")
        return {key.decode().split(":")[1] for key in existing_keys} if existing_keys else set()
    except Exception as e:
        print(f"⚠️ Error checking existing dates: {e}")
        return set()

def create_redis_connection():
    """Create Redis connection with proper SSL configuration for Upstash"""
    if not REDIS_URL:
        raise ValueError("REDIS_URL not found in environment variables")
    
    parsed = urlparse(REDIS_URL)
    password = parsed.password or parsed.netloc.split('@')[0].split(':')[-1]
    host = parsed.hostname
    port = parsed.port or 6379
    
    return redis.Redis(
        host=host,
        port=port,
        password=password,
        ssl=True,
        ssl_cert_reqs=ssl.CERT_NONE,
        decode_responses=False
    )

def process_file(file_path: Path, redis_client: redis.Redis, force_reload: bool = False):
    """Process JSON file and load data with detailed debugging"""
    existing_dates = set() if force_reload else get_existing_dates(redis_client)
    stats = {
        'total': 0,
        'loaded': 0,
        'skipped': 0,
        'conversion_failed': 0,
        'invalid': 0,
        'sample_entries': [],
        'existing_dates_sample': list(existing_dates)[:3] if existing_dates else []
    }

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            entries = json.load(f)
            stats['total'] = len(entries)
            stats['sample_entries'] = entries[:1]  # Sample first entry
    except Exception as e:
        print(f"❌ Failed to load {file_path}: {e}")
        return

    date_groups = defaultdict(list)
    
    for entry in entries:
        if 'date_int' not in entry:
            stats['invalid'] += 1
            continue
            
        human_date = convert_days_to_date(entry['date_int'])
        if not human_date:
            stats['conversion_failed'] += 1
            continue
            
        if human_date not in existing_dates:
            date_groups[human_date].append(entry)
        else:
            stats['skipped'] += 1

    # Load to Redis
    for date, items in date_groups.items():
        redis_key = f"{REDIS_FOOD_ENTRIES_PREFIX}{date}"
        try:
            redis_client.set(redis_key, json.dumps(items))
            redis_client.hset(REDIS_DATE_MAPPINGS_KEY, date, str(items[0]['date_int']))
            stats['loaded'] += len(items)
            print(f"✅ Loaded {len(items)} entries for {date}")
        except redis.RedisError as e:
            print(f"❌ Failed to save {date}: {e}")

    # Print detailed summary
    print(f"\n📊 Detailed summary for {file_path.name}:")
    print(f"Total entries processed: {stats['total']}")
    print(f"Entries loaded: {stats['loaded']}")
    print(f"Entries skipped (existing): {stats['skipped']}")
    print(f"Entries with conversion issues: {stats['conversion_failed']}")
    print(f"Invalid entries (missing date_int): {stats['invalid']}")
    
    if stats['sample_entries']:
        sample = stats['sample_entries'][0]
        print("\nSample entry:")
        print(f"date_int: {sample.get('date_int')}")
        print(f"Converted date: {convert_days_to_date(sample.get('date_int'))}")
        print(f"Food name: {sample.get('food_name', 'N/A')}")
    
    if stats['existing_dates_sample']:
        print("\nSample existing dates in Redis:")
        for date in stats['existing_dates_sample']:
            print(f"- {date}")

def main():
    try:
        if not REDIS_URL:
            print("❌ REDIS_URL environment variable not found")
            print("Please ensure your .env file contains REDIS_URL")
            return

        print("🔌 Connecting to Redis...")
        redis_client = create_redis_connection()
        redis_client.ping()
        print("✅ Connected successfully")
        
        # Clear existing data if force reload
        force_reload = "--force" in sys.argv
        if force_reload:
            print("⚠️ FORCE RELOAD MODE - Clearing existing data...")
            existing_keys = redis_client.keys(f"{REDIS_FOOD_ENTRIES_PREFIX}*")
            if existing_keys:
                redis_client.delete(*existing_keys)
                redis_client.delete(REDIS_DATE_MAPPINGS_KEY)
                print(f"🧹 Cleared {len(existing_keys)} existing date entries")
        
        historical_dir = Path(__file__).parent.parent / "historical_food_data"
        files = sorted(historical_dir.glob("historical_food_entries_*.json"))
        
        if not files:
            print("❌ No historical files found")
            return
            
        for file_path in files:
            process_file(file_path, redis_client, force_reload)
            
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
    finally:
        if 'redis_client' in locals():
            redis_client.close()

if __name__ == "__main__":
    main()