from __future__ import annotations

import os
from contextlib import contextmanager

import psycopg2
from psycopg2.extras import RealDictCursor
from flask import Flask, render_template, request

app = Flask(__name__)


@contextmanager
def database():
    conn = psycopg2.connect(host=os.getenv("DB_HOST", "localhost"),
                            dbname=os.getenv("DB_NAME", "notebooks"),
                            user=os.getenv("DB_USER", "notebooks"),
                            password=os.getenv("DB_PASSWORD", ""),
                            cursor_factory=RealDictCursor)
    try:
        yield conn
    finally:
        conn.close()


@app.get("/health")
def health():
    with database() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 AS ok")
            return {"status": "ok", "database": cur.fetchone()["ok"]}


@app.get("/")
def home():
    source = request.args.get("source", "")[:30]
    brand = request.args.get("brand", "")[:30]
    search = request.args.get("search", "")[:80]
    min_price = request.args.get("min_price", "")
    max_price = request.args.get("max_price", "")
    try:
        low = max(0, int(min_price)) if min_price else None
        high = min(1000000, int(max_price)) if max_price else None
    except ValueError:
        low = high = None
    blank = {"offers": 0, "models": 0, "sources": 0, "minimum": None, "average": None}
    with database() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT to_regclass('public.notebook_offers') AS table_name")
            if cur.fetchone()["table_name"] is None:
                return render_template("index.html", ready=False, kpi=blank, offers=[], brands=[],
                                       comparisons=[], runs=[], sources=[], brand_options=[],
                                       source=source, brand=brand, search=search, min_price=min_price,
                                       max_price=max_price)
            where = ["1=1"]
            args = []
            if source:
                where.append("o.source = %s")
                args.append(source)
            if brand:
                where.append("p.brand = %s")
                args.append(brand)
            if search:
                where.append("(o.product_name ILIKE %s OR o.model_key ILIKE %s)")
                args.extend([f"%{search}%", f"%{search}%"])
            if low is not None:
                where.append("o.price_baht >= %s")
                args.append(low)
            if high is not None:
                where.append("o.price_baht <= %s")
                args.append(high)
            base = " FROM notebook_offers o JOIN notebook_products p ON o.model_key=p.model_key WHERE " + " AND ".join(where)
            cur.execute("SELECT COUNT(*) AS offers, COUNT(DISTINCT o.model_key) AS models, "
                        "COUNT(DISTINCT o.source) AS sources, MIN(o.price_baht) AS minimum, "
                        "ROUND(AVG(o.price_baht)) AS average" + base, args)
            kpi = cur.fetchone()
            cur.execute("SELECT o.source, o.model_key, p.brand, o.product_name, o.price_baht, "
                        "o.product_url, o.fetched_at" + base + " ORDER BY o.price_baht ASC LIMIT 100", args)
            offers = cur.fetchall()
            cur.execute("SELECT p.brand AS label, COUNT(*) AS count" + base +
                        " GROUP BY p.brand ORDER BY count DESC LIMIT 10", args)
            brands = cur.fetchall()
            cur.execute("""SELECT model_key, MIN(product_name) AS product_name,
                          COUNT(DISTINCT source) AS source_count, MIN(price_baht) AS cheapest,
                          MAX(price_baht) AS highest, MAX(price_baht)-MIN(price_baht) AS gap
                          FROM notebook_offers GROUP BY model_key
                          HAVING COUNT(DISTINCT source) >= 2
                          ORDER BY gap DESC LIMIT 12""")
            comparisons = cur.fetchall()
            cur.execute("SELECT DISTINCT source FROM notebook_offers ORDER BY source")
            sources = [r["source"] for r in cur.fetchall()]
            cur.execute("SELECT DISTINCT brand FROM notebook_products ORDER BY brand")
            brand_options = [r["brand"] for r in cur.fetchall()]
            cur.execute("SELECT run_key, finished_at, status, raw_counts, accepted_count, "
                        "model_count, source_errors, message FROM notebook_pipeline_runs "
                        "ORDER BY finished_at DESC LIMIT 5")
            runs = cur.fetchall()
    max_count = max([r["count"] for r in brands], default=1)
    return render_template("index.html", ready=True, kpi=kpi, offers=offers, brands=brands,
                           max_count=max_count, comparisons=comparisons, runs=runs,
                           sources=sources, brand_options=brand_options, source=source, brand=brand,
                           search=search, min_price=min_price, max_price=max_price)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8502)
