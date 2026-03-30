from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dagster import DagsterRunStatus, get_dagster_logger, run_status_sensor

ALERT_CONFIG_PATH = Path(__file__).resolve().parent / "alert_routing.json"


def _load_alert_config() -> dict[str, Any]:
    with ALERT_CONFIG_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


def _get_route_for_job(job_name: str) -> tuple[str, dict[str, Any]] | None:
    config = _load_alert_config()
    routes: dict[str, dict[str, Any]] = config.get("routes", {})
    for route_name, route_conf in routes.items():
        jobs = route_conf.get("jobs", [])
        if job_name in jobs:
            return route_name, route_conf
    return None


def _build_payload(job_name: str, run_id: str, status: str) -> dict[str, str]:
    return {
        "job_name": job_name,
        "run_id": run_id,
        "status": status,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "dagster_run_url": "",
    }


def _dispatch_alert(
    route_name: str, route_conf: dict[str, Any], payload: dict[str, str]
) -> None:
    logger = get_dagster_logger()
    # Channel mode is intentionally log-only until Slack/Teams/Webhook is finalized.
    logger.warning(
        "[ALERT][%s] target=%s payload=%s",
        route_name,
        route_conf.get("target", ""),
        payload,
    )


@run_status_sensor(run_status=DagsterRunStatus.FAILURE)
def routed_failure_sensor(context) -> None:
    dagster_run = context.dagster_run
    route = _get_route_for_job(dagster_run.job_name)
    if route is None:
        return

    route_name, route_conf = route
    payload = _build_payload(
        job_name=dagster_run.job_name,
        run_id=dagster_run.run_id,
        status="FAILURE",
    )
    _dispatch_alert(route_name, route_conf, payload)
