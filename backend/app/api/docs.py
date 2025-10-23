from pathlib import Path
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import PlainTextResponse

router = APIRouter(prefix="/api/docs", tags=["docs"])

def _project_root() -> Path:
  # Prefer working directory (Docker runs from /app). Fallback to walking up from this file.
  for cand in [Path.cwd(), Path('/workspace')]:
    if (cand / 'README.md').exists():
      return cand
  return Path(__file__).resolve().parents[3]


@router.get("/text")
def get_doc_text(name: str = Query(..., description="Doc key: gigs or readme")):
    base = _project_root()
    if name == "gigs":
        path = base / "docs" / "gigs.md"
    elif name == "readme":
        path = base / "README.md"
    else:
        raise HTTPException(status_code=404, detail="Unknown doc name")
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Doc not found: {path}")
    try:
        return PlainTextResponse(path.read_text(encoding="utf-8"))
    except Exception as exc:  # pylint: disable=broad-except
        raise HTTPException(status_code=500, detail=str(exc))
