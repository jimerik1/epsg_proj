import os
from pathlib import Path
from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
import subprocess
import shutil

router = APIRouter(prefix="/api/gigs", tags=["gigs"])


def _report_dir() -> Path:
    base = os.getenv("GIGS_REPORT_DIR", "tests/gigs")
    return Path(base)


def _project_root() -> Path:
    """Locate repository root by searching for README.md from cwd and from this file upwards."""
    contenders = [Path.cwd(), Path("/workspace"), Path(__file__).resolve()] + list(Path(__file__).resolve().parents)
    for base in contenders:
        for candidate in [base] + list(base.parents):
            if (candidate / "README.md").exists():
                return candidate
    # Fallback to cwd
    return Path.cwd()


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
        base = _project_root()
        runner = base / "tests" / "gigs" / "run_manual.py"
        if not runner.exists():
            raise HTTPException(status_code=500, detail=f"Runner not found at {runner}")
        result = subprocess.run(
            ["python3", str(runner)],
            cwd=str(base),
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            raise HTTPException(status_code=500, detail=f"Runner failed: {result.stderr}\n{result.stdout}")
        # Copy artifacts from repo to report dir
        src_dir = base / "tests" / "gigs"
        dst_dir = _report_dir()
        try:
            dst_dir.mkdir(parents=True, exist_ok=True)
        except Exception:
            pass
        for fname in ("gigs_manual_report.json", "gigs_manual_report.html"):
            src = src_dir / fname
            if src.exists():
                try:
                    shutil.copyfile(src, dst_dir / fname)
                except Exception:
                    # If copy fails, fall back to reading from src
                    pass

        # Return the refreshed JSON
        json_path = (dst_dir / "gigs_manual_report.json")
        if not json_path.exists():
            # Fallback: try reading directly from the repo artifacts
            json_path = src_dir / "gigs_manual_report.json"
            if not json_path.exists():
                raise HTTPException(status_code=500, detail="Runner completed but JSON report not found")
        try:
            data = json_path.read_text(encoding="utf-8")
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc))
        return JSONResponse(content=__import__("json").loads(data))
    except HTTPException:
        raise
    except Exception as exc:  # pylint: disable=broad-except
        raise HTTPException(status_code=500, detail=str(exc))
