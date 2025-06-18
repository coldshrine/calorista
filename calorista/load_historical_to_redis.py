import json
import re
import sys
from pathlib import Path
from collections import defaultdict
from typing import Optional
import redis
from redis.exceptions import ConnectionError
from urllib.parse import urlparse
import ssl
from datetime import datetime, timedelta

from utils.constants import REDIS_URL

def convert_days_to_date(days_str: str) -> str:
    """Convert days since epoch (1970-01-01) to YYYY-MM-DD format"""
    try:
        days = int(days_str)
        date = datetime(1970, 1, 1) + timedelta(days=days)
        return date.strftime("%Y-%m-%d")
    except (ValueError, TypeError):
        return "unknown_date"

def find_latest_historical_file(directory: Path) -> Optional[Path]:
    """Find the most recent historical food entries file."""
    historical_files = list(directory.glob("historical_food_entries_*_to_*.json"))
    if not historical_files:
        print(f"ℹ️ No historical files found in {directory}")
        return None
    
    dated_files = []
    date_pattern = re.compile(r".*_to_(\d{4}-\d{2}-\d{2})\.json")
    
    for file in historical_files:
        if match := date_pattern.search(file.name):
            dated_files.append((match.group(1), file))
    
    if not dated_files:
        print("ℹ️ No valid historical files found")
        return None
    
    dated_files.sort(key=lambda x: x[0], reverse=True)
    return dated_files[0][1]

def create_redis_connection():
    """Create a Redis connection with SSL for Upstash."""
    parsed = urlparse(REDIS_URL)
    
    connection_params = {
        'host': parsed.hostname,
        'port': parsed.port,
        'password': parsed.password,
        'socket_timeout': 10,
        'socket_connect_timeout': 5,
        'ssl': True,
        'ssl_cert_reqs': ssl.CERT_NONE,
        'decode_responses': True  # For easier string handling
    }
    
    return redis.Redis(**connection_params)

def main():
    try:
        # Initialize Redis connection
        print("🔌 Connecting to Upstash Redis...")
        redis_client = create_redis_connection()
        redis_client.ping()  # Test connection
        print("✅ Connected to Redis successfully")
        
        # Find and process historical file
        historical_dir = Path(__file__).resolve().parent.parent / "historical_food_data"
        if not (json_file_path := find_latest_historical_file(historical_dir)):
            sys.exit(1)

        print(f"📂 Processing: {json_file_path.name}")
        
        with open(json_file_path, "r", encoding="utf-8") as f:
            entries = json.load(f)

        # Process and cache entries with human-readable dates
        grouped_by_human_date = defaultdict(list)
        date_mapping = {}  # Track original date_int to human date
        
        for entry in entries:
            if date_int := entry.get("date_int"):
                human_date = convert_days_to_date(date_int)
                date_mapping[date_int] = human_date
                grouped_by_human_date[human_date].append(entry)
                # Add human date to the entry
                entry['human_date'] = human_date

        print(f"📊 Found {len(grouped_by_human_date)} dates with {len(entries)} entries")
        
        # Cache both original and human-readable formats
        for human_date, items in grouped_by_human_date.items():
            # Store with human date as key
            redis_key = f"food_entries:{human_date}"
            redis_client.set(redis_key, json.dumps(items))
            
            # Also store the mapping for reference
            original_date_int = items[0]['date_int']
            redis_client.hset("date_mappings", human_date, original_date_int)
            
            print(f"✅ Cached {len(items)} entries for {human_date} (original date_int: {original_date_int})")

        print("🎉 All data cached successfully with human-readable dates")

    except ConnectionError:
        print("\n❌ Failed to connect to Upstash Redis. Please check:")
        print("1. Your REDIS_URL in .env")
        print("2. Your internet connection")
        print("3. That SSL/TLS is enabled in your Upstash settings")
    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
    finally:
        if 'redis_client' in locals():
            redis_client.close()

if __name__ == "__main__":
    main()