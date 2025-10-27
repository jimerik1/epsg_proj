from typing import Optional, Dict

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from pyproj import CRS, Transformer
from app.services.transformer import TransformationService

router = APIRouter(prefix="/api/transform", tags=["transform"])


class VerticalTransformRequest(BaseModel):
    # Coordinate reference information
    source_crs: Optional[str] = None  # e.g., EPSG:4979 for ellipsoidal height
    source_vertical_crs: Optional[str] = None  # e.g., EPSG:5612
    target_vertical_crs: str  # required vertical CRS code

    # Position and measurement
    lon: float
    lat: float
    value: float  # input height/depth value

    # Conventions
    value_is_depth: bool = False  # if True, input value is +down depth
    output_as_depth: bool = False  # if True, output is +down depth


def _to_bool(val) -> bool:
    try:
        return bool(val)
    except Exception:
        return False


@router.post("/vertical")
def vertical_transform(req: VerticalTransformRequest) -> Dict:
    """Transform a vertical measurement at a given lon/lat between vertical CRSs.

    Two usage patterns:
    - Ellipsoidal -> vertical: set `source_crs` (e.g., EPSG:4979) and `target_vertical_crs`.
    - Vertical -> vertical: set `source_vertical_crs` and `target_vertical_crs`.

    Depth/height conventions:
    - If `value_is_depth` is true, the input is positive-down depth (internally converted to height).
    - If `output_as_depth` is true, returned value is positive-down depth.
    """
    try:
        lon = float(req.lon)
        lat = float(req.lat)
        val = float(req.value)
        if _to_bool(req.value_is_depth):
            val = -val

        service = TransformationService()

        if req.source_crs and req.target_vertical_crs and not req.source_vertical_crs:
            src = service._crs_from_input(req.source_crs)
            tgt = service._crs_from_input(req.target_vertical_crs)
            tr = Transformer.from_crs(src, tgt, always_xy=True)
            # Some transforms may return (lon, lat, z) or just z. Use try/except.
            try:
                z = tr.transform(lon, lat, val)[-1]
            except Exception:
                # Fallback: assume vertical-only result
                z = tr.transform(lon, lat, val)
            out = float(z)
        elif req.source_vertical_crs and req.target_vertical_crs:
            src = service._crs_from_input(req.source_vertical_crs)
            tgt = service._crs_from_input(req.target_vertical_crs)
            tr = Transformer.from_crs(src, tgt, always_xy=True)
            try:
                z = tr.transform(lon, lat, val)[-1]
            except Exception:
                z = tr.transform(lon, lat, val)
            out = float(z)
        else:
            raise HTTPException(status_code=400, detail="Provide either source_crs (ellipsoidal) or source_vertical_crs")

        if _to_bool(req.output_as_depth):
            out = -out

        return {
            "lon": lon,
            "lat": lat,
            "input_value": req.value,
            "output_value": out,
            "output_convention": "depth" if _to_bool(req.output_as_depth) else "height",
            "source": req.source_vertical_crs or req.source_crs,
            "target_vertical_crs": req.target_vertical_crs,
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
