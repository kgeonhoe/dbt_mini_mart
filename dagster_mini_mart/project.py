from pathlib import Path

from dagster_dbt import DbtProject

DAGSTER_DBT_PROJECT_DIR = Path(__file__).joinpath("..", "..").resolve()

dbt_project = DbtProject(
    project_dir=DAGSTER_DBT_PROJECT_DIR,
    target_path=DAGSTER_DBT_PROJECT_DIR / "target",
)
dbt_project.prepare_if_dev()
