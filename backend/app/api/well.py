from typing import Optional, Dict, Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from pyproj import CRS, Transformer

from .vertical import vertical_transform, VerticalTransformRequest

router = APIRouter(prefix="/api/transform", tags=["transform"])


class WellPointRequest(BaseModel):
    source_type: Literal["geographic", "projected"]
    source_crs: str
    lon: Optional[float] = None
    lat: Optional[float] = None
    easting: Optional[float] = None
    northing: Optional[float] = None

    target_projected_crs: str
    target_vertical_crs: Optional[str] = None

    tvd_value: Optional[float] = None
    tvd_is_depth: bool = True
    output_tvd_signed: bool = True  # return signed TVD (negative depth)


@router.post("/well-point")
def well_point(req: WellPointRequest) -> Dict:
    try:
        # Horizontal
        proj_out = {"crs": req.target_projected_crs, "x": None, "y": None}
        if req.source_type == "projected":
            if req.easting is None or req.northing is None:
                raise HTTPException(status_code=400, detail="easting/northing required for projected source")
            if CRS.from_string(req.source_crs) == CRS.from_string(req.target_projected_crs):
                x, y = float(req.easting), float(req.northing)
            else:
                tr = Transformer.from_crs(req.source_crs, req.target_projected_crs, always_xy=True)
                x, y = tr.transform(float(req.easting), float(req.northing))[:2]
            proj_out["x"], proj_out["y"] = x, y
            # lon/lat for vertical
            tr_inv = Transformer.from_crs(req.source_crs, "EPSG:4326", always_xy=True)
            v_lon, v_lat = tr_inv.transform(float(req.easting), float(req.northing))[:2]
        else:
            if req.lon is None or req.lat is None:
                raise HTTPException(status_code=400, detail="lon/lat required for geographic source")
            tr = Transformer.from_crs(req.source_crs, req.target_projected_crs, always_xy=True)
            x, y = tr.transform(float(req.lon), float(req.lat))[:2]
            proj_out["x"], proj_out["y"] = x, y
            v_lon, v_lat = float(req.lon), float(req.lat)

        result: Dict = {"projected": proj_out}

        # Vertical (optional)
        if req.tvd_value is not None and req.target_vertical_crs:
            v_req = VerticalTransformRequest(
                source_crs="EPSG:4979",
                source_vertical_crs=None,
                target_vertical_crs=req.target_vertical_crs,
                lon=v_lon,
                lat=v_lat,
                value=float(req.tvd_value),
                value_is_depth=bool(req.tvd_is_depth),
                output_as_depth=True,  # endpoint returns +down depth
            )
            try:
                v_out = vertical_transform(v_req)  # call internal function
                # Convert to signed TVD if requested
                tvd_depth = float(v_out.get("output_value"))
                signed_tvd = -tvd_depth if req.output_tvd_signed else tvd_depth
                result["vertical"] = {
                    "crs": req.target_vertical_crs,
                    "tvd": signed_tvd,
                    "convention": "signed_tvd" if req.output_tvd_signed else "depth",
                }
            except HTTPException as exc:
                # expose as part of response but don't fail
                result["vertical_error"] = exc.detail
            except Exception as exc:  # noqa
                result["vertical_error"] = str(exc)

        return result
    except HTTPException:
        raise
    except Exception as exc:  # noqa
        raise HTTPException(status_code=500, detail=str(exc))


class WellBatchRequest(BaseModel):
    points: list[WellPointRequest]


@router.post("/well-batch")
def well_batch(req: WellBatchRequest) -> Dict:
    results = []
    for p in req.points:
        try:
            results.append(well_point(p))
        except HTTPException as exc:
            results.append({"error": exc.detail})
        except Exception as exc:  # noqa
            results.append({"error": str(exc)})
    return {"results": results}

