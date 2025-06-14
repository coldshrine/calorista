import json
from pathlib import Path
from collections import defaultdict

from utils.api import cache_food_entries_to_redis

json_file_path = Path(__file__).resolve().parent.parent / "historical_food_data" / "historical_food_entries_2025-04-07_to_2025-06-15.json"

if not json_file_path.exists():
    raise FileNotFoundError(f"❌ File not found: {json_file_path}")

with open(json_file_path, "r", encoding="utf-8") as f:
    entries = json.load(f)

grouped_by_date: dict[str, list] = defaultdict(list)
for entry in entries:
    date = entry.get("date_int")
    if not date:
        continue
    grouped_by_date[date].append(entry)

for date, items in grouped_by_date.items():
    cache_food_entries_to_redis(items, date)
    print(f"📤 Cached {len(items)} entries for {date}")
