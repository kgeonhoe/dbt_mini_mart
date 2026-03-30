from dagster import OpExecutionContext, job, op
from dagster_dbt import DbtCliResource

from .project import dbt_project


@op(required_resource_keys={"dbt"})
def dbt_build_op(context: OpExecutionContext):
    dbt: DbtCliResource = context.resources.dbt
    yield from dbt.cli(["build"], context=context).stream()


@op(required_resource_keys={"dbt"})
def dbt_source_freshness_op(context: OpExecutionContext):
    dbt: DbtCliResource = context.resources.dbt
    yield from dbt.cli(["source", "freshness"], context=context).stream()


@op(required_resource_keys={"dbt"})
def dbt_test_modified_op(context: OpExecutionContext):
    dbt: DbtCliResource = context.resources.dbt
    yield from dbt.cli(
        ["test", "--select", "state:modified+"], context=context
    ).stream()


@job(resource_defs={"dbt": DbtCliResource(project_dir=dbt_project)})
def dbt_build_job():
    dbt_build_op()


@job(resource_defs={"dbt": DbtCliResource(project_dir=dbt_project)})
def dbt_source_freshness_job():
    dbt_source_freshness_op()


@job(resource_defs={"dbt": DbtCliResource(project_dir=dbt_project)})
def dbt_test_modified_job():
    dbt_test_modified_op()
