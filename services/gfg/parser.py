import json
import re
from pathlib import Path

CACHE_FILE = Path(__file__).parent / "questions_cache.json"

_NEXT_DATA_RE = re.compile(
    r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>',
    re.DOTALL,
)


def parse_question(path: Path) -> dict | None:
    try:
        raw = json.loads(path.read_text())
        m = _NEXT_DATA_RE.search(raw["html"])
        if not m:
            return None
        nd = json.loads(m.group(1))
        prob = (
            nd["props"]["pageProps"]["initialState"]["problemData"]["allData"]["probData"]
        )
        tags = prob.get("tags", {})
        return {
            "id": prob.get("id"),
            "name": prob.get("problem_name", ""),
            "slug": prob.get("slug", ""),
            "difficulty": prob.get("difficulty", ""),
            "marks": prob.get("marks", 0),
            "accuracy": prob.get("accuracy", ""),
            "all_submissions": prob.get("all_submissions", 0),
            "company_tags": tags.get("company_tags", []),
            "topic_tags": tags.get("topic_tags", []),
            "problem_url": raw.get("problem_url", ""),
            "content": prob.get("problem_question", ""),
        }
    except Exception:
        return None
