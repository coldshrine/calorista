import datetime
import json
import csv
from pathlib import Path

from utils.api import FatSecretAPI
from utils.auth import FatSecretAuth

# Initialize authentication and API
auth = FatSecretAuth(token_file="tokens.json")
api = FatSecretAPI(auth)

# Display user's weight
profile = api.get_user_weight()
print(f"Hello! Your current weight is {profile.last_weight_kg}kg")

# Get today’s food entries
today_str = datetime.date.today().strftime("%Y-%m-%d")
todays_food_entries = api.get_todays_food_entries(today_str)
print("\nToday's Food Entries:")
print(json.dumps(todays_food_entries, indent=4, ensure_ascii=False))

# Define historical range
start_date = "2025-04-07"
end_date = "2025-05-15"

# Get full historical food entries
historical_entries = api.get_historical_food_entries(start_date, end_date)
print(f"\nHistorical Food Entries from {start_date} to {end_date}:")

# Flatten and collect all entries
all_entries = []
for daily_result in historical_entries:
    entries = daily_result.get("food_entries", {}).get("food_entry", [])
    if isinstance(entries, dict):  # if only one entry
        entries = [entries]
    all_entries.extend(entries)

# Print the result count
print(f"\n✅ Retrieved {len(all_entries)} historical food entries.\n")

# Save to JSON
output_dir = Path("historical_food_data")
output_dir.mkdir(exist_ok=True)

json_path = output_dir / f"historical_food_entries_{start_date}_to_{end_date}.json"
with open(json_path, "w", encoding="utf-8") as f:
    json.dump(all_entries, f, ensure_ascii=False, indent=2)

print(f"📦 JSON saved to {json_path}")

# Save to CSV
csv_path = output_dir / f"historical_food_entries_{start_date}_to_{end_date}.csv"
with open(csv_path, "w", newline="", encoding="utf-8") as csvfile:
    fieldnames = [
        "date_int", "food_id", "food_name", "meal",
        "serving_description", "number_of_units"
    ]
    writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
    writer.writeheader()

    for entry in all_entries:
        writer.writerow({
            "date_int": entry.get("date_int"),
            "food_id": entry.get("food_id"),
            "food_name": entry.get("food_name"),
            "meal": entry.get("meal"),
            "serving_description": entry.get("serving_description"),
            "number_of_units": entry.get("number_of_units"),
        })

print(f"📄 CSV saved to {csv_path}")
