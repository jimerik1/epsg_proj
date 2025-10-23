import os
from pathlib import Path
from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
import subprocess

router = APIRouter(prefix="/api/gigs", tags=["gigs"])


def _report_dir() -> Path:
    base = os.getenv("GIGS_REPORT_DIR", "tests/gigs")
    return Path(base)


@router.get("/report")
def get_gigs_report():
    dir_path = _report_dir()
    json_path = dir_path / "gigs_manual_report.json"
    if not json_path.exists():
        raise HTTPException(status_code=404, detail=f"Report JSON not found at {json_path}")
    try:
        data = json_path.read_text(encoding="utf-8")
        return JSONResponse(content=__import__("json").loads(data))
    except Exception as exc:  # pylint: disable=broad-except
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/report/html")
def get_gigs_report_html():
    dir_path = _report_dir()
    html_path = dir_path / "gigs_manual_report.html"
    if not html_path.exists():
        raise HTTPException(status_code=404, detail=f"Report HTML not found at {html_path}")
    try:
        html = html_path.read_text(encoding="utf-8")
        return HTMLResponse(content=html)
    except Exception as exc:  # pylint: disable=broad-except
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/run")
def run_gigs_manual():
    """Execute the manual GIGS runner to regenerate HTML + JSON reports.

    Intended for development; runs synchronously and returns the new JSON.
    """
    try:
        # Execute the manual runner from project root (/app)
        result = subprocess.run(
            ["python3", "tests/gigs/run_manual.py"],
            cwd=str(Path(__file__).resolve().parents[3]),
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            raise HTTPException(status_code=500, detail=f"Runner failed: {result.stderr}\n{result.stdout}")
        # Return the refreshed JSON
        dir_path = _report_dir()
        json_path = dir_path / "gigs_manual_report.json"
        if not json_path.exists():
            raise HTTPException(status_code=500, detail="Runner completed but JSON report not found")
        data = json_path.read_text(encoding="utf-8")
        return JSONResponse(content=__import__("json").loads(data))
    except HTTPException:
        raise
    except Exception as exc:  # pylint: disable=broad-except
        raise HTTPException(status_code=500, detail=str(exc))
