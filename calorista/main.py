import datetime
import json
from pathlib import Path

from utils.api import FatSecretAPI
from utils.auth import FatSecretAuth

BASE_DIR = Path(__file__).resolve().parent.parent
token_file = BASE_DIR / "auth_tokens" / "tokens.json"
auth = FatSecretAuth(token_file=str(token_file))
api = FatSecretAPI(auth)

profile = api.get_user_weight()
print(f"Hello! Your current weight is {profile.last_weight_kg}kg")

today_str = datetime.date.today().strftime("%Y-%m-%d")
todays_food_entries = api.get_todays_food_entries(today_str)
print("\nToday's Food Entries:")
print(json.dumps(todays_food_entries, indent=4, ensure_ascii=False))

start_date = "2025-04-07"
end_date = "2025-06-15"  # dynamically set to today's date

historical_entries = api.get_historical_food_entries(start_date, end_date)
print(f"\nHistorical Food Entries from {start_date} to {end_date}:")

all_entries = []
for daily_result in historical_entries:
    date = daily_result.get("date", "unknown date")
    food_entries = daily_result.get("food_entries")
    
    if not food_entries:
        print(f"⚠️  No food entries on {date}")
        continue

    entries = food_entries.get("food_entry", [])
    if isinstance(entries, dict): 
        entries = [entries]
    all_entries.extend(entries)

print(f"\n✅ Retrieved {len(all_entries)} historical food entries.\n")

output_dir = Path("historical_food_data")
output_dir.mkdir(exist_ok=True)

json_path = output_dir / f"historical_food_entries_{start_date}_to_{end_date}.json"
with open(json_path, "w", encoding="utf-8") as f:
    json.dump(all_entries, f, ensure_ascii=False, indent=2)

print(f"📦 JSON saved to {json_path}")
