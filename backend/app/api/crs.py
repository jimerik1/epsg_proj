from fastapi import APIRouter, HTTPException
from pyproj import CRS
from pyproj.database import query_crs_info
from pyproj.aoi import AreaOfInterest
from typing import Optional, List, Dict
from app.services.crs_parser import CustomCRSParser
from pydantic import BaseModel


class CustomXmlBody(BaseModel):
    xml: str

router = APIRouter(prefix="/api/crs", tags=["crs"])

@router.get("/info")
async def crs_info(code: str):
    """Return CRS metadata like name, datum, ellipsoid parameters, etc."""
    try:
        crs = CRS.from_string(code)
        # Base info
        info = {
            "code": code,
            "name": crs.name,
            "type": crs.type_name,
            "is_geographic": crs.is_geographic,
            "is_projected": crs.is_projected,
            "area_of_use": getattr(crs.area_of_use, "name", None),
        }

        # Datum and geodetic
        datum_name = None
        try:
            datum_name = getattr(crs.datum, "name", None)
        except Exception:
            datum_name = None
        info["datum_name"] = datum_name

        # Ellipsoid
        ell = None
        geo = getattr(crs, "geodetic_crs", None) or crs
        try:
            ell = getattr(geo, "ellipsoid", None)
        except Exception:
            ell = None
        if ell is not None:
            try:
                info["ellipsoid"] = {
                    "name": getattr(ell, "name", None),
                    "semi_major_m": getattr(ell, "semi_major_metre", None),
                    "semi_minor_m": getattr(ell, "semi_minor_metre", None),
                    "inverse_flattening": getattr(ell, "inverse_flattening", None),
                    "flattening": getattr(ell, "flattening", None),
                }
            except Exception:
                pass

        # Prime meridian
        try:
            pm = getattr(geo, "prime_meridian", None)
            if pm is not None:
                info["prime_meridian"] = {
                    "name": getattr(pm, "name", None),
                    "longitude": getattr(pm, "longitude", None),
                }
        except Exception:
            pass

        # Axis + units snapshot
        units = {}
        for axis in crs.axis_info:
            entry = {
                "name": axis.name,
                "abbrev": axis.abbrev,
                "direction": axis.direction,
                "unit_name": axis.unit_name,
                "unit_conv_factor": axis.unit_conversion_factor,
            }
            units[axis.direction] = entry
        info["axis"] = units

        return info
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


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
async def match_custom(body: CustomXmlBody):
    """Match a custom XML CRS definition to possible EPSG CRS candidates.
    Heuristic scoring based on UTM zone, projection method, datum and ellipsoid.
    """
    try:
        import re
        import xml.etree.ElementTree as ET
        from math import isfinite

        parser = CustomCRSParser()
        proj_str = parser.parse_xml_to_proj(body.xml)

        try:
            root = ET.fromstring(body.xml)
        except ET.ParseError:
            root = ET.fromstring(f"<root>{body.xml}</root>")
        s = root.find('CD_GEO_SYSTEM')
        z = root.find('CD_GEO_ZONE')
        d = root.find('CD_GEO_DATUM')
        e = root.find('CD_GEO_ELLIPSOID')

        zone_id = (z is not None and z.attrib.get('geo_zone_id')) or ''
        zone_num = None
        hemi_south = False
        m = re.search(r"UTM-?(\d+)([NS])?", zone_id or '', re.I)
        if m:
            try:
                zone_num = int(m.group(1))
            except Exception:
                zone_num = None
            hemi_south = (m.group(2) or '').upper() == 'S'

        system_id = ((z is not None and z.attrib.get('geo_system_id', '')) or (s is not None and s.attrib.get('geo_system_id', '')) or '')
        system_name = (s is not None and (s.attrib.get('geo_system_name') or s.attrib.get('geo_system_id'))) or ''
        is_utm = any('UTM' in (v or '') for v in [system_id, system_name, (zone_id or '')])

        datum_name = (d is not None and (d.attrib.get('datum_name') or d.attrib.get('geo_datum_id'))) or ''
        ell_name = (e is not None and (e.attrib.get('name') or e.attrib.get('geo_ellipsoid_id'))) or ''
        a = None
        try:
            a = float(e.attrib.get('semi_major')) if e is not None and e.attrib.get('semi_major') else None
        except Exception:
            a = None

        # Narrow candidate search
        search_term = None
        if is_utm and zone_num:
            search_term = f"UTM zone {zone_num}"

        infos = query_crs_info(auth_name="EPSG", pj_types=["PROJECTED_CRS"]) 
        # Lightweight name-based prefilter to reduce CRS instantiations
        name_l = lambda s: (s or '').lower()
        if is_utm:
            infos = [i for i in infos if 'utm' in name_l(i.name)]
        if zone_num:
            ztok = f"zone {zone_num}"
            infos = [i for i in infos if ztok in name_l(i.name)] or infos

        def score_epsg(info) -> Dict:
            s = 0
            details = {"code": info.code, "name": info.name}
            try:
                cand = CRS.from_epsg(info.code)
                details["crs_name"] = cand.name
                # Method and parameters
                conv = cand.to_json_dict().get('conversion') or {}
                method = (conv.get('method') or {}).get('name', '')
                params = conv.get('parameters') or []
                # UTM heuristic
                name_lower = (info.name or '').lower()
                if is_utm:
                    if 'utm' in name_lower:
                        s += 20
                    if zone_num and f"zone {zone_num}" in name_lower:
                        s += 50
                    if hemi_south and 'south' in name_lower:
                        s += 5
                    if (not hemi_south) and 'north' in name_lower:
                        s += 5
                # Transverse Mercator
                if 'Transverse Mercator' in method:
                    s += 15

                # Datum / ellipsoid names
                geo = getattr(cand, 'geodetic_crs', None) or cand
                cdn = getattr(getattr(cand, 'datum', None), 'name', '') or getattr(getattr(geo, 'datum', None), 'name', '') or ''
                ell = getattr(geo, 'ellipsoid', None)
                elln = getattr(ell, 'name', '') if ell else ''
                if datum_name and datum_name.split()[0].lower() in cdn.lower():
                    s += 20
                if ell_name and ell_name.split()[0].lower() in elln.lower():
                    s += 15
                if a and hasattr(ell, 'semi_major_metre'):
                    try:
                        if abs(float(ell.semi_major_metre) - a) < 2.0:  # within 2 m
                            s += 10
                    except Exception:
                        pass

                details.update({
                    "datum": cdn,
                    "ellipsoid": elln,
                    "method": method,
                })
            except Exception:
                pass
            return {"epsg_code": f"EPSG:{info.code}", "name": info.name, "score": s, "details": details}

        ranked = [score_epsg(i) for i in infos]
        ranked.sort(key=lambda x: x['score'], reverse=True)

        return {
            "proj_string": proj_str,
            "parsed": {
                "zone_id": zone_id,
                "zone_num": zone_num,
                "hemisphere_south": hemi_south,
                "datum_name": datum_name,
                "ellipsoid_name": ell_name,
                "semi_major": a,
                "system_id": system_id.strip() if isinstance(system_id, str) else system_id,
                "system_name": system_name,
            },
            "matches": ranked[:20],
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


def _extract_projection_parameters(crs: CRS) -> Dict:
    out: Dict[str, Dict] = {"method": None, "parameters": {}, "raw": []}
    try:
        j = crs.to_json_dict()
        conv = j.get("conversion") or {}
        method = (conv.get("method") or {}).get("name")
        out["method"] = method
        params = conv.get("parameters") or []
        name_map = {
            "False easting": "false_easting",
            "False northing": "false_northing",
            "Scale factor at natural origin": "scale_factor",
            "Scale factor at projection centre": "scale_factor",
            "Longitude of natural origin": "lon_origin",
            "Latitude of natural origin": "lat_origin",
            "Longitude of origin": "lon_origin",
            "Latitude of origin": "lat_origin",
            "Central meridian": "central_meridian",
            "Latitude of projection centre": "lat_origin",
        }
        for p in params:
            nm = p.get("name")
            val = p.get("value")
            unit = (p.get("unit") or {}).get("name") if isinstance(p.get("unit"), dict) else p.get("unit")
            out["raw"].append({"name": nm, "value": val, "unit": unit})
            key = name_map.get(nm)
            if key:
                out["parameters"][key] = {"value": val, "unit": unit}

        # Try to infer UTM zone from proj string if present
        try:
            proj4 = crs.to_proj4()
            if "+zone=" in proj4:
                import re
                m = re.search(r"\+zone=(\d+)", proj4)
                if m:
                    out["parameters"]["zone"] = {"value": int(m.group(1)), "unit": None}
            if "+south" in proj4:
                out["parameters"]["south"] = {"value": True, "unit": None}
        except Exception:
            pass
    except Exception:
        pass
    return out


@router.get("/parameters")
async def crs_parameters(code: str):
    try:
        crs = CRS.from_string(code)
        params = _extract_projection_parameters(crs)
        return params
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/parse-custom")
async def parse_custom(body: CustomXmlBody):
    try:
        parser = CustomCRSParser()
        proj = parser.parse_xml_to_proj(body.xml)
        # Extract known fields from the XML quickly for UI
        import xml.etree.ElementTree as ET
        try:
            root = ET.fromstring(body.xml)
        except ET.ParseError:
            root = ET.fromstring(f"<root>{body.xml}</root>")
        s = root.find('CD_GEO_SYSTEM')
        z = root.find('CD_GEO_ZONE')
        d = root.find('CD_GEO_DATUM')
        e = root.find('CD_GEO_ELLIPSOID')
        out = {"proj": proj, "system": {}, "zone": {}, "datum": {}, "ellipsoid": {}}
        if s is not None:
            out["system"] = s.attrib
        if z is not None:
            out["zone"] = z.attrib
        if d is not None:
            out["datum"] = d.attrib
        if e is not None:
            out["ellipsoid"] = e.attrib
        return out
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
