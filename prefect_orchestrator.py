from prefect import flow, task
import subprocess

@task
def fetch_fatsecret_data():
    subprocess.run(
        ["python", "calorista/main.py"],  # fetch + save JSON locally
        check=True
    )

@task
def load_to_redis():
    subprocess.run(
        ["python", "calorista/load_historical_to_redis.py"],  # load JSON to Redis
        check=True
    )

@flow
def daily_fatsecret_sync():
    fetch_fatsecret_data()
    load_to_redis()

if __name__ == "__main__":
    daily_fatsecret_sync()
