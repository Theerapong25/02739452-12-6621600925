"""Three-source notebook price ETL for the 02739452 practical examination."""
from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path

from airflow.decorators import dag, task, task_group
from airflow.exceptions import AirflowFailException
from airflow.operators.empty import EmptyOperator

from pipeline import DATA_DIR, load_postgres, merge_files, quality_result, write_run_status
from scraper import SOURCES, fetch_source

LOG = logging.getLogger(__name__)


@dag(
    dag_id="notebook_price_comparison",
    schedule=None,
    start_date=datetime(2026, 1, 1),
    catchup=False,
    max_active_runs=1,
    tags=["exam", "web-scraping", "notebook"],
    default_args={"retries": 1, "retry_delay": timedelta(minutes=2)},
)
def notebook_price_comparison():
    @task
    def prepare_run(**context):
        run_id = context["dag_run"].run_id
        run_key = hashlib.sha256(run_id.encode()).hexdigest()[:16]
        (DATA_DIR / run_key).mkdir(parents=True, exist_ok=True)
        return run_key

    @task
    def extract(source: str, run_key: str):
        try:
            rows, meta = fetch_source(source)
            filename = DATA_DIR / run_key / f"{source}.json"
            filename.write_text(json.dumps([x.to_dict() for x in rows], ensure_ascii=False), encoding="utf-8")
            LOG.info("EXTRACT %s: %s listings across %s page(s); HTTP %s",
                     source, len(rows), len(meta["pages"]),
                     [page["http_status"] for page in meta["pages"]])
            return {"source": source, "ok": True, "count": len(rows), "file": str(filename), "meta": meta}
        except Exception as exc:
            # A single source failure does not stop the remaining sources.
            LOG.exception("EXTRACT %s FAILED: %s", source, exc)
            return {"source": source, "ok": False, "count": 0, "error": str(exc)}

    @task_group(group_id="extract_sources")
    def extract_sources(run_key):
        return [extract.override(task_id=source)(source, run_key) for source in SOURCES]

    @task
    def transform(results, run_key):
        merged = merge_files(results, run_key)
        LOG.info("TRANSFORM: %s offers, %s unique models, source counts: %s",
                 merged["count"], merged["model_count"], merged["source_counts"])
        return merged

    @task.branch
    def quality_gate(merged):
        passed, message = quality_result(merged)
        LOG.info("QUALITY %s: %s", "PASS" if passed else "FAIL", message)
        return "load_postgres" if passed else "quality_failed"

    @task
    def load_postgres_task(merged, run_key):
        result = load_postgres(run_key, merged)
        LOG.info("LOAD SUCCESS: %s persisted offers, %s models", result["confirmed"], result["models"])
        return result

    @task(task_id="quality_failed")
    def record_failure(merged, run_key):
        _, message = quality_result(merged)
        write_run_status(run_key, merged, "QUALITY_FAILED", message)
        LOG.error("QUALITY FAILED: %s", message)
        raise AirflowFailException(message)

    @task(trigger_rule="all_done")
    def notify_status(merged):
        LOG.info("PIPELINE STATUS: %s accepted offers; %s models; source outcomes: %s",
                 merged["count"], merged["model_count"],
                 [{"source": r["source"], "ok": r["ok"], "count": r["count"]} for r in merged["source_results"]])

    run_key = prepare_run()
    results = extract_sources(run_key)
    merged = transform(results, run_key)
    gate = quality_gate(merged)
    loaded = load_postgres_task.override(task_id="load_postgres")(merged, run_key)
    failed = record_failure(merged, run_key)
    gate >> [loaded, failed]
    [loaded, failed] >> notify_status(merged)


notebook_price_comparison()
