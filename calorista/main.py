import datetime
import json
from pathlib import Path
from typing import Any, Dict, List

from utils.api import FatSecretAPI
from utils.auth import FatSecretAuth


def process_historical_entries(
    api: FatSecretAPI, start_date: str, end_date: str
) -> List[Dict[str, Any]]:
    """Process historical food entries between two dates."""
    all_entries: List[Dict[str, Any]] = []
    try:
        print(f"\nFetching historical food entries from {start_date} to {end_date}...")
        historical_entries = api.get_historical_food_entries(start_date, end_date)

        if not historical_entries:
            print("⚠️ No historical entries received from API")
            return all_entries

        for daily_result in historical_entries:
            if not daily_result:
                continue

            date = daily_result.get("date", "unknown date")
            food_entries = daily_result.get("food_entries", {})

            entries = food_entries.get("food_entry", [])
            if isinstance(entries, dict):
                entries = [entries]

            if entries:
                all_entries.extend(entries)
            else:
                print(f"⚠️ No food entries on {date}")

        print(f"\n✅ Retrieved {len(all_entries)} historical food entries.")
        return all_entries

    except Exception as e:
        print(f"⚠️ Error processing historical entries: {e}")
        return all_entries


def main():
    # Initialize API client
    BASE_DIR = Path(__file__).resolve().parent.parent
    token_file = BASE_DIR / "auth_tokens" / "tokens.json"
    if not token_file.exists():
        print(f"❌ Token file not found at: {token_file}")
        return
    auth = FatSecretAuth(token_file=str(token_file))
    api = FatSecretAPI(auth)

    try:
        # Get and display current weight
        profile = api.get_user_weight()
        print(f"Hello! Your current weight is {profile.last_weight_kg}kg")
    except Exception as e:
        print(f"⚠️ Error getting weight profile: {e}")

    # Get today's date
    today = datetime.date.today()
    today_str = today.strftime("%Y-%m-%d")

    # Process today's food entries
    has_todays_entries = False
    try:
        todays_food_entries = api.get_todays_food_entries(today_str)
        if todays_food_entries and todays_food_entries.get("food_entries"):
            print("\nToday's Food Entries:")
            print(json.dumps(todays_food_entries, indent=4, ensure_ascii=False))
            has_todays_entries = True
        else:
            print("\n⚠️ No food entries found for today")
    except Exception as e:
        print(f"\n⚠️ Error getting today's food entries: {e}")

    # Process historical food entries
    start_date = "2025-04-07"
    # If no entries today, set end date to yesterday
    end_date = (
        (today - datetime.timedelta(days=1)).strftime("%Y-%m-%d")
        if not has_todays_entries
        else today_str
    )

    all_entries = process_historical_entries(api, start_date, end_date)

    # Save to file if we have entries
    if all_entries:
        output_dir = Path("food")
        output_dir.mkdir(exist_ok=True)

        json_path = (
            output_dir / f"historical_food_entries_{start_date}_to_{end_date}.json"
        )
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(all_entries, f, ensure_ascii=False, indent=2)

        print(f"📦 JSON saved to {json_path}")


if __name__ == "__main__":
    main()
