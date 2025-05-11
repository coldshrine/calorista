import time 
from utils.auth import FatSecretAuth
from utils.api import FatSecretAPI

# Initialize with token persistence
auth = FatSecretAuth(token_file="tokens.json")
api = FatSecretAPI(auth)

# Get user profile (will use cached tokens or authenticate if needed)
profile = api.get_user_profile()
print(f"Hello! Your current weight is {profile.last_weight_kg}kg")

# Search for foods
results = api.search_foods("apple")
for food in results['foods']['food']:
    print(f"{food['food_name']}: {food['food_description']}")

# Get today's food entries
today = time.strftime("%Y-%m-%d")
entries = api.get_food_entries(today)