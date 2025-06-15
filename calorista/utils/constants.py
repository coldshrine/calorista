import os
from dotenv import load_dotenv
from pathlib import Path

env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

CONSUMER_KEY = os.getenv("CONSUMER_KEY")
CONSUMER_SECRET = os.getenv("CONSUMER_SECRET")
CALLBACK_URL = os.getenv("CALLBACK_URL")
OAUTH_SIGNATURE_METHOD = os.getenv("OAUTH_SIGNATURE_METHOD")
OAUTH_VERSION = os.getenv("OAUTH_VERSION")

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")