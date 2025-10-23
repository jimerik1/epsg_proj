from typing import List, Dict, Optional

from fastapi import APIRouter, HTTPException
from pyproj.transformer import TransformerGroup
from pyproj.datadir import get_data_dir
import os
import subprocess

router = APIRouter(prefix="/api/transform", tags=["transform"])


def _extract_grids(op_str: str) -> List[str]:
    # crude parse for grids=, nadgrids=, geoidgrids=
    grids: List[str] = []
    for key in ("grids=", "nadgrids=", "geoidgrids="):
        if key in op_str:
            frag = op_str.split(key, 1)[1]
            val = frag.split()[0].split(',')[0]
            for part in val.split(';'):
                part = part.strip()
                if part and part not in grids and part != "@null":
                    grids.append(part)
    return grids


def _grid_present(name: str) -> bool:
    # Search PROJ data dirs for the basename
    base = os.path.basename(name)
    candidates = [os.environ.get("PROJ_DATA"), os.environ.get("PROJ_LIB"), get_data_dir()]
    for d in candidates:
        if not d:
            continue
        try:
            for root, _, files in os.walk(d):
                if base in files:
                    return True
        except Exception:
            continue
    return False


@router.get("/required-grids")
def required_grids(source_crs: str, target_crs: str) -> Dict:
    try:
        group = TransformerGroup(source_crs, target_crs, always_xy=True)
        out: List[Dict[str, Optional[str]]] = []
        for idx, tr in enumerate(group.transformers):
            grids: List[str] = []
            try:
                for op in getattr(tr, "operations", []) or []:
                    try:
                        s = op.to_proj4()
                    except Exception:
                        s = str(op)
                    grids.extend(_extract_grids(s))
            except Exception:
                pass
            uniq = []
            for g in grids:
                if g not in uniq:
                    uniq.append(g)
            out.append({
                "path_id": idx,
                "description": tr.description,
                "accuracy": tr.accuracy,
                "grids": [{"name": g, "present": _grid_present(g)} for g in uniq],
            })
        return {"source_crs": source_crs, "target_crs": target_crs, "paths": out}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/prefetch-grids")
def prefetch_grids(names: Dict[str, list]):
    """Try to download grids from PROJ CDN into PROJ_DATA using projsync.

    Body: {"names": ["uk_os_OSTN15_NTv2_OSGBtoETRS.gsb", "uk_os_OSGM15_GB.tif"]}
    """
    grids = names.get("names") if isinstance(names, dict) else None
    if not grids or not isinstance(grids, list):
        raise HTTPException(status_code=400, detail="Provide a JSON body with 'names': [..]")

    dest = os.environ.get("PROJ_DATA") or get_data_dir()
    if not dest:
        raise HTTPException(status_code=500, detail="PROJ data directory not found")
    downloaded = []
    errors = []
    for g in grids:
        try:
            result = subprocess.run(
                ["projsync", "-s", "https://cdn.proj.org", "-r", g, "-d", dest],
                capture_output=True,
                text=True,
            )
            if result.returncode == 0:
                downloaded.append(g)
            else:
                errors.append({"name": g, "error": result.stderr or result.stdout})
        except FileNotFoundError:
            errors.append({"name": g, "error": "projsync not available in backend image"})
        except Exception as exc:
            errors.append({"name": g, "error": str(exc)})
    return {"dest": dest, "downloaded": downloaded, "errors": errors}
