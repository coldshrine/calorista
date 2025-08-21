from __future__ import annotations

import json
import os
from pathlib import Path

from prefect import flow, get_run_logger
from prefect.blocks.system import Secret

from calorista.main import main as run_calorista


def _apply_env_from_prefect_blocks(logger):
    """
    Pull secrets from Prefect Blocks (if present):
      - 'fatsecret-env': JSON of environment variables
      - 'fatsecret-tokens': JSON of tokens written to auth_tokens/tokens.json
    """
    try:
        env_block = Secret.load("fatsecret-env")
        env_json = env_block.get()
        env_dict = json.loads(env_json)
        for k, v in env_dict.items():
            os.environ.setdefault(k, v)
        logger.info("Applied Prefect Secret 'fatsecret-env'")
    except Exception as e:
        logger.info(f"Secret 'fatsecret-env' not found/failed: {e}")

    try:
        tokens_block = Secret.load("fatsecret-tokens")
        tokens_json = tokens_block.get()
        tokens = json.loads(tokens_json)

        base_dir = Path(__file__).resolve().parents[1]
        token_file = base_dir / "auth_tokens" / "tokens.json"
        token_file.parent.mkdir(parents=True, exist_ok=True)
        token_file.write_text(json.dumps(tokens))
        logger.info(f"Wrote tokens to {token_file}")
    except Exception as e:
        logger.info(f"Secret 'fatsecret-tokens' not found/failed: {e}")


@flow(name="calorista-flow", retries=2, retry_delay_seconds=60)
def calorista_flow():
    """
    Prefect Flow: apply secrets and run your main logic once.
    """
    logger = get_run_logger()
    _apply_env_from_prefect_blocks(logger)
    run_calorista()


if __name__ == "__main__":
    calorista_flow()
