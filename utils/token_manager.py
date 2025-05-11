import json
import os
from typing import Dict, Optional
from pathlib import Path

class TokenManager:
    def __init__(self, token_file: str = "fatsecret_tokens.json"):
        self.token_file = Path(token_file)
        self.tokens = self._load_tokens()

    def _load_tokens(self):
        try:
            if self.token_file.exists():
                if self.token_file.stat().st_size == 0:  # Check if empty
                    return {}
                with open(self.token_file, 'r') as f:
                    return json.load(f)
            return {}
        except (json.JSONDecodeError, IOError):
            return {}  # Treat corrupt file as missing

    def save_tokens(self, tokens: Dict):
        with open(self.token_file, 'w') as f:
            json.dump(tokens, f)
        self.tokens = tokens

    def get_tokens(self) -> Optional[Dict]:
        return self.tokens if self.tokens else None

    def clear_tokens(self):
        if self.token_file.exists():
            os.remove(self.token_file)
        self.tokens = {}