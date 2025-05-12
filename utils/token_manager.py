import json
import os
from pathlib import Path
from typing import Any


class TokenManager:
    def __init__(self, token_file: str = "fatsecret_tokens.json") -> None:
        self.token_file = Path(token_file)
        self.tokens = self._load_tokens()

    def _load_tokens(self) -> dict[str, Any]:
        try:
            if self.token_file.exists():
                if self.token_file.stat().st_size == 0:
                    return {}
                with open(self.token_file) as f:
                    return json.load(f)
            return {}
        except (OSError, json.JSONDecodeError):
            return {}

    def save_tokens(self, tokens: dict[str, Any]) -> None:
        with open(self.token_file, "w") as f:
            json.dump(tokens, f)
        self.tokens = tokens

    def get_tokens(self) -> dict[str, Any] | None:
        return self.tokens if self.tokens else None

    def clear_tokens(self) -> None:
        if self.token_file.exists():
            os.remove(self.token_file)
        self.tokens = {}
