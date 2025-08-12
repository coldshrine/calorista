from prefect import flow, task
from prefect.blocks.system import Secret
import subprocess
import os
import json
import tempfile


def load_env_from_prefect():
    env_secret = Secret.load("fatsecret-env").get()
    return json.loads(env_secret)


def load_tokens_from_prefect():
    tokens_secret = Secret.load("fatsecret-tokens").get()
    tokens_data = json.loads(tokens_secret)

    tmp_file = tempfile.NamedTemporaryFile(mode="w", delete=False)
    json.dump(tokens_data, tmp_file)
    tmp_file.close()

    return tmp_file.name


@task
def fetch_fatsecret_data():
    env_data = load_env_from_prefect()
    tokens_path = load_tokens_from_prefect()

    task_env = {**os.environ, **env_data, "TOKENS_PATH": tokens_path}

    subprocess.run(
        ["python", "calorista/main.py"],
        env=task_env,
        check=True
    )


@task
def load_to_redis():
    env_data = load_env_from_prefect()

    task_env = {**os.environ, **env_data}

    subprocess.run(
        ["python", "calorista/load_historical_to_redis.py"],
        env=task_env,
        check=True
    )


@flow
def daily_fatsecret_sync():
    fetch_fatsecret_data()
    load_to_redis()


if __name__ == "__main__":
    daily_fatsecret_sync()
