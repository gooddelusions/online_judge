"""Populate problem_meta from services/gfg/questions_cache.json.

Run after db/setup.sh and after applying db/schema.sql:
    psql $DATABASE_URL -f db/schema.sql
    python db/seed.py
"""

import json
import sys
from pathlib import Path

import psycopg
import yaml

ROOT = Path(__file__).parent.parent
CACHE_PATH = ROOT / "services/gfg/questions_cache.json"
CONFIG_PATH = ROOT / "config.yaml"


def load_db_url() -> str:
    cfg = yaml.safe_load(CONFIG_PATH.read_text())
    return cfg["database"]["url"]


def parse_accuracy(raw) -> float | None:
    if not raw:
        return None
    try:
        return float(str(raw).rstrip("%"))
    except ValueError:
        return None


def build_rows(cache: dict) -> list[tuple]:
    rows = []
    for problem in cache.values():
        if problem.get("id") is None:
            continue
        difficulty = problem.get("difficulty") or None
        rows.append((
            int(problem["id"]),
            problem["slug"],
            problem["name"],
            difficulty,
            int(problem["marks"]) if problem.get("marks") else None,
            parse_accuracy(problem.get("accuracy")),
            int(problem["all_submissions"]) if problem.get("all_submissions") else None,
            list(problem.get("topic_tags") or []),
            list(problem.get("company_tags") or []),
            [],                         # tags — reserved for custom tagging
            problem.get("problem_url"),
        ))
    return rows


def main() -> None:
    db_url = load_db_url()
    cache = json.loads(CACHE_PATH.read_text())
    rows = build_rows(cache)

    print(f"Seeding {len(rows)} problems into problem_meta …")

    with psycopg.connect(db_url) as conn:
        with conn.cursor() as cur:
            cur.executemany(
                """
                INSERT INTO problem_meta
                    (problem_id, slug, problem_name, difficulty, marks, accuracy,
                     all_submissions, topics, companies, tags, problem_url)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (problem_id) DO NOTHING
                """,
                rows,
            )
        conn.commit()

    print(f"Done. {len(rows)} rows inserted (duplicates skipped).")


if __name__ == "__main__":
    main()
