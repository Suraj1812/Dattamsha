from datetime import datetime

from airflow import DAG
from airflow.operators.bash import BashOperator


default_args = {
    "owner": "dattamsha",
    "retries": 1,
}

with DAG(
    dag_id="dattamsha_hr_data_fabric",
    default_args=default_args,
    start_date=datetime(2026, 1, 1),
    schedule="0 */6 * * *",
    catchup=False,
    description="Ingest HR data and run transformations for intelligence layer",
) as dag:
    ingest_sample_data = BashOperator(
        task_id="ingest_sample_data",
        bash_command="python -m app.scripts.seed_data",
    )

    run_dbt_models = BashOperator(
        task_id="run_dbt_models",
        bash_command="dbt run --project-dir ./dbt --profiles-dir ./dbt",
    )

    ingest_sample_data >> run_dbt_models
