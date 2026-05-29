import json
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
import psycopg
import yaml
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, Response
from fastapi.staticfiles import StaticFiles

JUDGE_URL = "http://localhost:8001"
ROOT = Path(__file__).parent.parent.parent
STATIC_DIR = Path(__file__).parent / "static"
CACHE_FILE = Path(__file__).parent / "questions_cache.json"

# slug → enriched question dict (metadata + html content)
_questions: dict[str, dict] = {}


def _db_url() -> str:
    cfg = yaml.safe_load((ROOT / "config.yaml").read_text())
    return cfg["database"]["url"]


def _row_to_question(row: tuple) -> dict:
    problem_id, slug, problem_name, difficulty, marks, accuracy, all_submissions, topics, companies, _, problem_url = row
    return {
        "id": str(problem_id),
        "slug": slug,
        "name": problem_name,
        "difficulty": difficulty or "Basic",
        "marks": marks or 0,
        "accuracy": f"{float(accuracy or 0):.2f}%",
        "all_submissions": all_submissions or 0,
        "topic_tags": list(topics or []),
        "company_tags": list(companies or []),
        "problem_url": problem_url or "",
    }


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 1. Pull all metadata rows from postgres
    async with await psycopg.AsyncConnection.connect(_db_url()) as conn:
        async with conn.cursor() as cur:
            await cur.execute("""
                SELECT problem_id, slug, problem_name, difficulty, marks, accuracy,
                       all_submissions, topics, companies, tags, problem_url
                FROM problem_meta
            """)
            rows = await cur.fetchall()

    questions = {row[1]: _row_to_question(row) for row in rows}
    print(f"Loaded {len(questions)} questions from postgres")

    # 2. Attach HTML content from cache (used until LaTeX revisions exist)
    if CACHE_FILE.exists():
        cache: dict = json.loads(CACHE_FILE.read_text())
        for slug, q in questions.items():
            entry = cache.get(slug)
            q["content"] = entry.get("content", "") if entry else ""
        print(f"Attached HTML content from cache ({CACHE_FILE.name})")

    _questions.update(questions)
    yield


app = FastAPI(lifespan=lifespan)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/", response_class=HTMLResponse)
async def index():
    return (STATIC_DIR / "index.html").read_text()


@app.get("/api/questions")
async def list_questions():
    return [
        {k: v for k, v in q.items() if k != "content"}
        for q in _questions.values()
    ]


@app.get("/api/questions/{slug}")
async def get_question(slug: str):
    if slug not in _questions:
        raise HTTPException(status_code=404, detail="Question not found")

    q = dict(_questions[slug])

    # Check for the latest authored LaTeX revision; prefer it over cached HTML
    async with await psycopg.AsyncConnection.connect(_db_url()) as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                SELECT latex FROM problem_latex
                WHERE problem_id = %s
                ORDER BY revision_number DESC
                LIMIT 1
                """,
                (int(q["id"]),),
            )
            row = await cur.fetchone()

    if row and row[0]:
        q["content"] = row[0]

    return q


@app.api_route("/api/judge/{path:path}", methods=["GET", "POST"])
async def judge_proxy(request: Request, path: str):
    try:
        async with httpx.AsyncClient(timeout=65) as client:
            resp = await client.request(
                method=request.method,
                url=f"{JUDGE_URL}/{path}",
                content=await request.body(),
                headers={"content-type": request.headers.get("content-type", "application/json")},
            )
        return Response(
            content=resp.content,
            status_code=resp.status_code,
            media_type=resp.headers.get("content-type", "application/json"),
        )
    except httpx.ConnectError:
        raise HTTPException(
            status_code=503,
            detail={"error": "judge_unavailable", "message": "Judge service is not running on :8001."},
        )
