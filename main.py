import time

from utils.api import FatSecretAPI
from utils.auth import FatSecretAuth

auth = FatSecretAuth(token_file="tokens.json")
api = FatSecretAPI(auth)

profile = api.get_user_profile()
print(f"Hello! Your current weight is {profile.last_weight_kg}kg")

results = api.search_foods("apple")
for food in results["foods"]["food"]:
    print(f"{food['food_name']}: {food['food_description']}")

today = time.strftime("%Y-%m-%d")
entries = api.get_food_entries(today)
