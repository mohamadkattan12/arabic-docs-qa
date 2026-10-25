import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException

from api.config import settings

router = APIRouter()


@router.get("/eval/latest")
def latest_eval() -> Any:
    results = sorted(Path(settings.eval_results_dir).glob("*.json"))
    if not results:
        raise HTTPException(404, "No evaluation results yet. Run: uv run python -m eval.run")
    return json.loads(results[-1].read_text(encoding="utf-8"))
