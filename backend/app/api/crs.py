from fastapi import APIRouter, HTTPException
from pyproj import CRS
from pyproj.database import query_crs_info
from pyproj.aoi import AreaOfInterest
from typing import Optional, List, Dict
from app.services.crs_parser import CustomCRSParser

router = APIRouter(prefix="/api/crs", tags=["crs"])


@router.get("/units/{epsg_code}")
async def get_units(epsg_code: str):
    try:
        crs = CRS.from_string(epsg_code)
        units = {}
        for axis in crs.axis_info:
            if axis.direction in ["east", "north"]:
                units["horizontal"] = axis.unit_name
                units["horizontal_factor"] = axis.unit_conversion_factor
            elif axis.direction == "up":
                units["vertical"] = axis.unit_name
                units["vertical_factor"] = axis.unit_conversion_factor
        return {"epsg_code": epsg_code, "units": units}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/search")
async def search_crs(text: Optional[str] = None,
                     area_of_interest: Optional[str] = None,
                     crs_type: Optional[str] = None):
    try:
        pj_types = None
        if crs_type:
            pj_types = [crs_type]

        aoi = None
        if area_of_interest:
            # Expect "west,south,east,north"
            west, south, east, north = map(float, area_of_interest.split(","))
            aoi = AreaOfInterest(west_lon_degree=west, south_lat_degree=south,
                                 east_lon_degree=east, north_lat_degree=north)

        results = query_crs_info(auth_name="EPSG", 
                                 area_of_interest=aoi,
                                 pj_types=pj_types,
                                 search_term=text)
        return [{"code": r.code, "name": r.name, "type": r.type_name} for r in results]
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/match")
async def match_custom(definition_xml: str):
    """Match a custom XML CRS definition to possible EPSG CRS candidates."""
    try:
        parser = CustomCRSParser()
        proj_str = parser.parse_xml_to_proj(definition_xml)
        # naive approach: return top handful of similarly named or type CRS
        results = query_crs_info(auth_name="EPSG")
        # just return a subset to avoid heavy compare; sorting by name similarity length
        candidates: List[Dict] = []
        for r in results[:200]:
            candidates.append({"epsg_code": f"EPSG:{r.code}", "name": r.name})
        return {"proj_string": proj_str, "candidates_sample": candidates}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
