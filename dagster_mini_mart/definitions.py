from dagster import Definitions
from dagster_dbt import DbtCliResource

from .assets import dbt_mini_mart_dbt_assets
from .project import dbt_project

defs = Definitions(
    assets=[dbt_mini_mart_dbt_assets],
    resources={
        "dbt": DbtCliResource(project_dir=dbt_project),
    },
)
