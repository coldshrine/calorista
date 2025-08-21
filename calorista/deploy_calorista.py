from prefect import flow
from prefect.client.schemas.schedules import CronSchedule
from calorista.flow import calorista_flow

REPO = "https://github.com/coldshrine/calorista.git"
ENTRYPOINT = "calorista/flow.py:calorista_flow"



if __name__ == "__main__":
    flow.from_source(
        source=REPO,
        entrypoint=ENTRYPOINT,
    ).deploy(
        name="calorista-hourly",
        work_pool_name="calorista-managed",
        schedule=CronSchedule(cron="0 * * * *", timezone="Europe/Kiev"),
        job_variables={
            "pip_packages": [
                "python-dotenv",
                "redis",
                "pytz",
            ]
        },
    )
