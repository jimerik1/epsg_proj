from pathlib import Path
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import PlainTextResponse

router = APIRouter(prefix="/api/docs", tags=["docs"])

BASE = Path(__file__).resolve().parents[3]  # repo root (/app)


@router.get("/text")
def get_doc_text(name: str = Query(..., description="Doc key: gigs or readme")):
    if name == "gigs":
        path = BASE / "docs" / "gigs.md"
    elif name == "readme":
        path = BASE / "README.md"
    else:
        raise HTTPException(status_code=404, detail="Unknown doc name")
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Doc not found: {path}")
    try:
        return PlainTextResponse(path.read_text(encoding="utf-8"))
    except Exception as exc:  # pylint: disable=broad-except
        raise HTTPException(status_code=500, detail=str(exc))

