from dagster import Definitions
from dagster_dbt import DbtCliResource

from .alerts import routed_failure_sensor
from .assets import dbt_mini_mart_dbt_assets
from .dlt_assets import dlt_raw_ingest
from .jobs import dbt_build_job, dbt_source_freshness_job, dbt_test_modified_job
from .project import dbt_project

defs = Definitions(
    assets=[dlt_raw_ingest, dbt_mini_mart_dbt_assets],
    jobs=[
        dbt_build_job,
        dbt_source_freshness_job,
        dbt_test_modified_job,
    ],
    sensors=[
        routed_failure_sensor,
    ],
    resources={
        "dbt": DbtCliResource(project_dir=dbt_project),
    },
)
