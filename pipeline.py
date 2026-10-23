"""Normalize notebook offers and persist them to PostgreSQL."""
from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

import psycopg2
from psycopg2.extras import execute_values

from scraper import Listing

DATA_DIR = Path(os.getenv("PIPELINE_DATA_DIR", "/opt/airflow/data"))
MIN_PRICE = 15000
MAX_PRICE = 40000
MIN_RECORDS = 100
BRANDS = ("ACER", "ASUS", "LENOVO", "HP", "DELL", "MSI", "GIGABYTE", "HUAWEI", "MICROSOFT", "APPLE")
MODEL_RE = re.compile(r"\b[A-Z]{1,6}\d{1,4}(?:[-/][A-Z0-9]{2,}){1,5}\b", re.I)


def db_connect():
    return psycopg2.connect(host=os.getenv("DB_HOST", "localhost"),
                            dbname=os.getenv("DB_NAME", "notebooks"),
                            user=os.getenv("DB_USER", "notebooks"),
                            password=os.getenv("DB_PASSWORD", ""))


def normalize(item: dict) -> dict | None:
    price = item.get("price_baht")
    if not isinstance(price, int) or not MIN_PRICE <= price <= MAX_PRICE:
        return None
    name = re.sub(r"\s+", " ", item["name"]).strip()
    upper = name.upper()
    brand = next((brand for brand in BRANDS if re.search(rf"\b{brand}\b", upper)), "OTHER")
    matches = MODEL_RE.findall(upper)
    model = matches[0].upper() if matches else ""
    model = re.sub(r"/T\d{3,4}$", "", model)
    if not model:
        # Weak fallback: retain a source-specific identity to prevent false model matches.
        model = f"{item['source'].upper()}-{item['source_id'].upper()}"
    item = dict(item)
    item["name"] = name
    item["brand"] = brand
    item["model_key"] = brand + ":" + model
    item["price_baht"] = price
    return item


def merge_files(source_results: list[dict], run_key: str) -> dict:
    files = [r["file"] for r in source_results if r.get("ok") and r.get("file")]
    offers = {}
    for filename in files:
        raw = json.loads(Path(filename).read_text(encoding="utf-8"))
        for item in raw:
            clean = normalize(item)
            if clean is None:
                continue
            key = (clean["source"], clean["source_id"])
            offers[key] = clean
    source_counts = {}
    for clean in offers.values():
        source_counts[clean["source"]] = source_counts.get(clean["source"], 0) + 1
    output = DATA_DIR / run_key / "clean.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(list(offers.values()), ensure_ascii=False), encoding="utf-8")
    return {"file": str(output), "count": len(offers), "source_counts": source_counts,
            "source_results": source_results, "model_count": len({x["model_key"] for x in offers.values()})}


SCHEMA = """
CREATE TABLE IF NOT EXISTS notebook_products (
  model_key TEXT PRIMARY KEY,
  brand TEXT NOT NULL,
  sample_name TEXT NOT NULL,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS notebook_offers (
  source TEXT NOT NULL,
  source_id TEXT NOT NULL,
  model_key TEXT NOT NULL REFERENCES notebook_products(model_key),
  product_name TEXT NOT NULL,
  price_baht INTEGER NOT NULL CHECK (price_baht > 0),
  product_url TEXT NOT NULL,
  description TEXT,
  fetched_at TIMESTAMPTZ NOT NULL,
  PRIMARY KEY (source, source_id)
);
CREATE INDEX IF NOT EXISTS ix_offers_price ON notebook_offers(price_baht);
CREATE INDEX IF NOT EXISTS ix_offers_model ON notebook_offers(model_key);
CREATE TABLE IF NOT EXISTS notebook_pipeline_runs (
  run_key TEXT PRIMARY KEY,
  finished_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  status TEXT NOT NULL,
  raw_counts JSONB NOT NULL,
  accepted_count INTEGER NOT NULL,
  model_count INTEGER NOT NULL,
  source_errors JSONB NOT NULL,
  message TEXT NOT NULL
);
"""


def initialize(cur):
    cur.execute(SCHEMA)


def write_run_status(run_key: str, merged: dict, status: str, message: str) -> None:
    results = merged["source_results"]
    counts = {r["source"]: r.get("count", 0) for r in results}
    errors = {r["source"]: r.get("error", "") for r in results if not r.get("ok")}
    with db_connect() as conn:
        with conn.cursor() as cur:
            initialize(cur)
            cur.execute("""INSERT INTO notebook_pipeline_runs
                (run_key,status,raw_counts,accepted_count,model_count,source_errors,message)
                VALUES (%s,%s,%s::jsonb,%s,%s,%s::jsonb,%s)
                ON CONFLICT (run_key) DO UPDATE SET finished_at=now(),status=EXCLUDED.status,
                raw_counts=EXCLUDED.raw_counts, accepted_count=EXCLUDED.accepted_count,
                model_count=EXCLUDED.model_count,source_errors=EXCLUDED.source_errors,
                message=EXCLUDED.message""",
                (run_key, status, json.dumps(counts), merged["count"], merged["model_count"],
                 json.dumps(errors), message))


def load_postgres(run_key: str, merged: dict) -> dict:
    offers = json.loads(Path(merged["file"]).read_text(encoding="utf-8"))
    product_map = {}
    for item in offers:
        product_map[item["model_key"]] = (item["model_key"], item["brand"], item["name"])
    with db_connect() as conn:
        with conn.cursor() as cur:
            initialize(cur)
            execute_values(cur, """INSERT INTO notebook_products (model_key,brand,sample_name) VALUES %s
                ON CONFLICT (model_key) DO UPDATE SET brand=EXCLUDED.brand,
                sample_name=EXCLUDED.sample_name, updated_at=now()""", list(product_map.values()))
            execute_values(cur, """INSERT INTO notebook_offers
                (source,source_id,model_key,product_name,price_baht,product_url,description,fetched_at)
                VALUES %s ON CONFLICT (source,source_id) DO UPDATE SET
                model_key=EXCLUDED.model_key,product_name=EXCLUDED.product_name,
                price_baht=EXCLUDED.price_baht,product_url=EXCLUDED.product_url,
                description=EXCLUDED.description,fetched_at=EXCLUDED.fetched_at""",
                [(x["source"], x["source_id"], x["model_key"], x["name"], x["price_baht"],
                  x["product_url"], x["description"], x["fetched_at"]) for x in offers])
            keys = [(x["source"], x["source_id"]) for x in offers]
            cur.execute("SELECT count(*) FROM notebook_offers WHERE (source,source_id) IN %s",
                        (tuple(keys),))
            confirmed = cur.fetchone()[0]
            if confirmed != len(offers):
                raise ValueError(f"PostgreSQL validation failed: {confirmed} vs {len(offers)}")
            # A successful scrape is a complete snapshot for that source.
            for source in merged["source_counts"]:
                current_ids = [x["source_id"] for x in offers if x["source"] == source]
                cur.execute("DELETE FROM notebook_offers WHERE source = %s AND NOT (source_id = ANY(%s))",
                            (source, current_ids))
            cur.execute("DELETE FROM notebook_products p WHERE NOT EXISTS "
                        "(SELECT 1 FROM notebook_offers o WHERE o.model_key = p.model_key)")
    write_run_status(run_key, merged, "SUCCESS", f"Saved {len(offers)} offers from {len(merged['source_counts'])} sources")
    return {"confirmed": confirmed, "models": merged["model_count"]}


def quality_result(merged: dict) -> tuple[bool, str]:
    count = merged["count"]
    sources = len(merged["source_counts"])
    if count < MIN_RECORDS:
        return False, f"Only {count} accepted offers; at least {MIN_RECORDS} required"
    if sources < 2:
        return False, f"Only {sources} source(s) available; at least 2 required"
    return True, f"{count} offers from {sources} sources passed quality checks"
