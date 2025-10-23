import math

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional, Dict, Literal
from pyproj import CRS, Transformer, Geod

from app.services.transformer import TransformationService
from app.services.crs_parser import CustomCRSParser

router = APIRouter(prefix="/api/transform", tags=["transform"])


class TransformRequest(BaseModel):
    source_crs: str
    target_crs: str
    position: Dict[str, float]
    vertical_value: Optional[float] = None
    # Optional selection of a specific operation path
    path_id: Optional[int] = None
    preferred_ops: Optional[List[str]] = None


class TrajectoryRequest(BaseModel):
    source_crs: str
    target_crs: str
    trajectory_points: List[Dict]


class ViaRequest(BaseModel):
    path: List[str]
    position: Dict[str, float]
    vertical_value: Optional[float] = None
    # Optional per-segment TransformerGroup indices (len = len(path) - 1)
    segment_path_ids: Optional[List[Optional[int]]] = None
    segment_preferred_ops: Optional[List[Optional[List[str]]]] = None


class CustomTransformRequest(BaseModel):
    custom_definition_xml: str
    source_crs: str
    position: Dict[str, float]
    vertical_value: Optional[float] = None


class ReferencePosition(BaseModel):
    lon: Optional[float] = None
    lat: Optional[float] = None
    x: Optional[float] = None
    y: Optional[float] = None
    height: Optional[float] = 0.0


class OffsetVector(BaseModel):
    east: float
    north: float
    up: Optional[float] = 0.0


class LocalOffsetRequest(BaseModel):
    crs: str
    reference: ReferencePosition
    offset: OffsetVector


class TrajectoryPoint(BaseModel):
    md: Optional[float] = None
    tvd: float
    east: float
    north: float
    name: Optional[str] = None


class LocalTrajectoryRequest(BaseModel):
    crs: str
    reference: ReferencePosition
    points: List[TrajectoryPoint]
    mode: Literal['ecef', 'scale', 'both'] = 'both'


@router.post("/direct")
async def transform_direct(request: TransformRequest):
    try:
        service = TransformationService()

        x = request.position.get("x") or request.position.get("lon")
        y = request.position.get("y") or request.position.get("lat")
        z = request.vertical_value

        if request.path_id is not None or request.preferred_ops:
            result = service.transform_point_with_selection(
                request.source_crs,
                request.target_crs,
                x,
                y,
                z,
                path_id=request.path_id,
                preferred_ops=request.preferred_ops,
            )
        else:
            result = service.transform_point(
                request.source_crs, request.target_crs, x, y, z
            )

        target_crs = CRS.from_string(request.target_crs)

        response = {
            "map_position": {"x": result["x"], "y": result["y"]},
            "vertical_output": result.get("z"),
            "units_used": {
                "source": result["units_source"],
                "target": result["units_target"],
            },
            "transformation_accuracy": result["accuracy"],
        }

        if target_crs.is_projected:
            # For convergence/scale factor, inputs should be geographic lon/lat
            # Use inverse transform to geographic if needed
            try:
                lon, lat = service.to_geographic(request.target_crs, result["x"], result["y"]).values()
            except Exception:
                lon, lat = result["x"], result["y"]
            response["grid_convergence"] = service.calculate_grid_convergence(
                request.target_crs, lon, lat
            )
            response["scale_factor"] = service.calculate_scale_factor(
                request.target_crs, lon, lat
            )

        return response

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/trajectory")
async def transform_trajectory(request: TrajectoryRequest):
    try:
        service = TransformationService()
        transformed = service.transform_trajectory(
            request.source_crs, request.target_crs, request.trajectory_points
        )

        source_crs = CRS.from_string(request.source_crs)
        target_crs = CRS.from_string(request.target_crs)

        return {
            "transformed_trajectory": transformed,
            "units_used": {
                "source": service._get_units(source_crs),
                "target": service._get_units(target_crs),
            },
            "transformation_accuracy": service.get_transformer(
                request.source_crs, request.target_crs
            ).accuracy,
        }

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/accuracy")
async def get_transformation_accuracy(source_crs: str, target_crs: str):
    try:
        service = TransformationService()
        transformer = service.get_transformer(source_crs, target_crs)

        return {
            "source_crs": source_crs,
            "target_crs": target_crs,
            "horizontal_accuracy": transformer.accuracy,
            "accuracy_unit": "meter",
            "transformation_method": transformer.description,
            "operations": [op.to_proj4() for op in transformer.operations],
        }

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/available-paths")
async def get_available_paths(source_crs: str, target_crs: str):
    try:
        service = TransformationService()
        paths = service.get_all_transformation_paths(source_crs, target_crs)

        return {
            "source_crs": source_crs,
            "target_crs": target_crs,
            "transformation_paths": paths,
            "recommended_path_id": paths[0]["path_id"] if paths else None,
        }

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/available-paths-via")
async def get_available_paths_via(source_crs: str, via_crs: str, target_crs: str):
    """List available TransformerGroup paths for source→via and via→target."""
    try:
        service = TransformationService()
        leg1 = service.get_all_transformation_paths(source_crs, via_crs)
        leg2 = service.get_all_transformation_paths(via_crs, target_crs)
        return {
            "source_crs": source_crs,
            "via_crs": via_crs,
            "target_crs": target_crs,
            "leg1_paths": leg1,
            "leg2_paths": leg2,
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/suggest-vias")
async def suggest_vias(source_crs: str, target_crs: str):
    """Return a small, validated set of suggested via CRS codes between source and target.

    Strategy:
    - Include geodetic CRS (and 3D variants) for source and target if resolvable.
    - Include global pivots commonly useful for pipelines: EPSG:4326, EPSG:4978, EPSG:4979.
    - Validate that both source→candidate and candidate→target have at least one transformer.
    """
    try:
        service = TransformationService()
        suggestions = []
        seen = set()

        def add(code: str, reason: str):
            key = code.strip()
            if not key or key in seen:
                return
            # Validate there exists a path in both legs
            try:
                leg1 = service.get_all_transformation_paths(source_crs, key)
                leg2 = service.get_all_transformation_paths(key, target_crs)
            except Exception:
                return
            if not leg1 or not leg2:
                return
            suggestions.append({"code": key, "reason": reason})
            seen.add(key)

        # Geodetic CRS of source/target
        try:
            src = CRS.from_string(source_crs)
            src_geo = getattr(src, "geodetic_crs", None) or src
            add(src_geo.to_string(), "source geodetic")
            try:
                add(src_geo.to_3d().to_string(), "source geodetic 3D")
            except Exception:
                pass
        except Exception:
            pass
        try:
            tgt = CRS.from_string(target_crs)
            tgt_geo = getattr(tgt, "geodetic_crs", None) or tgt
            add(tgt_geo.to_string(), "target geodetic")
            try:
                add(tgt_geo.to_3d().to_string(), "target geodetic 3D")
            except Exception:
                pass
        except Exception:
            pass

        # Common pivots
        for code, reason in [("EPSG:4326", "WGS 84"), ("EPSG:4979", "WGS 84 3D"), ("EPSG:4978", "ECEF")]:
            add(code, reason)

        return {"source_crs": source_crs, "target_crs": target_crs, "suggestions": suggestions}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/via")
async def transform_via(request: ViaRequest):
    try:
        service = TransformationService()
        x = request.position.get("x") or request.position.get("lon")
        y = request.position.get("y") or request.position.get("lat")
        z = request.vertical_value

        total_accuracy = 0.0
        acc_known = True

        cur_x, cur_y, cur_z = x, y, z
        seg_ids = request.segment_path_ids or []
        seg_ops = request.segment_preferred_ops or []

        for i in range(len(request.path) - 1):
            src = request.path[i]
            dst = request.path[i + 1]
            chosen_id = seg_ids[i] if i < len(seg_ids) else None
            chosen_ops = seg_ops[i] if i < len(seg_ops) else None

            if chosen_id is not None or chosen_ops:
                out = service.transform_point_with_selection(
                    src,
                    dst,
                    cur_x,
                    cur_y,
                    cur_z,
                    path_id=chosen_id,
                    preferred_ops=chosen_ops,
                )
            else:
                out = service.transform_point(src, dst, cur_x, cur_y, cur_z)

            cur_x, cur_y, cur_z = out["x"], out["y"], out.get("z")
            if out.get("accuracy") is None:
                acc_known = False
            else:
                total_accuracy += float(out["accuracy"])  # naive aggregation

        return {
            "x": cur_x,
            "y": cur_y,
            "z": cur_z,
            "cumulative_accuracy": None if not acc_known else total_accuracy,
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/custom")
async def transform_custom(request: CustomTransformRequest):
    try:
        parser = CustomCRSParser()
        proj_str = parser.parse_xml_to_proj(request.custom_definition_xml)
        custom_crs = f"{proj_str}"
        service = TransformationService()

        x = request.position.get("x") or request.position.get("lon")
        y = request.position.get("y") or request.position.get("lat")
        z = request.vertical_value

        result = service.transform_point(custom_crs, request.source_crs, x, y, z)
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/local-offset")
async def transform_local_offset(request: LocalOffsetRequest):
    try:
        service = TransformationService()
        crs = CRS.from_string(request.crs)
        geodetic = getattr(crs, "geodetic_crs", None) or crs
        geodetic3d = geodetic
        try:
            geodetic3d = geodetic.to_3d()
        except Exception:
            pass

        ref_lon = request.reference.lon
        ref_lat = request.reference.lat
        ref_h = request.reference.height or 0.0

        transformer_proj_to_geo = Transformer.from_crs(crs, geodetic3d, always_xy=True)

        if ref_lon is None or ref_lat is None:
            if request.reference.x is None or request.reference.y is None:
                raise HTTPException(status_code=400, detail="Reference must include lon/lat or x/y")
            ref_lon, ref_lat, ref_h = transformer_proj_to_geo.transform(
                request.reference.x,
                request.reference.y,
                ref_h,
            )

        context = service.build_local_offset_context(request.crs, ref_lon, ref_lat, ref_h)
        units_info = service._get_units(crs)
        horizontal_factor = units_info.get("horizontal_factor") or 1.0
        meter_to_axis = 1.0 / horizontal_factor if horizontal_factor else 1.0

        if request.reference.x is not None and request.reference.y is not None:
            base_projected = {"x": request.reference.x, "y": request.reference.y}
        else:
            proj_coords = context["geo_to_target"].transform(ref_lon, ref_lat, ref_h)
            base_projected = {"x": proj_coords[0], "y": proj_coords[1]}

        precise = service.local_offset_via_ecef(
            request.crs,
            ref_lon,
            ref_lat,
            ref_h,
            request.offset.east,
            request.offset.north,
            request.offset.up or 0.0,
            context=context,
        )

        scales = None
        scale_result = None
        try:
            scales = service.calculate_scale_factor(request.crs, ref_lon, ref_lat)
            meridional = scales.get("meridional_scale")
            parallel = scales.get("parallel_scale")
            if meridional is not None and parallel is not None:
                grid_east_m = request.offset.east * parallel
                grid_north_m = request.offset.north * meridional
                dx = grid_east_m * meter_to_axis
                dy = grid_north_m * meter_to_axis
                new_x = base_projected["x"] + dx
                new_y = base_projected["y"] + dy
                lon_scale, lat_scale, h_scale = transformer_proj_to_geo.transform(
                    new_x,
                    new_y,
                    ref_h + (request.offset.up or 0.0),
                )
                geo_to_wgs = context.get("geo_to_wgs") or Transformer.from_crs(geodetic3d, CRS.from_epsg(4979), always_xy=True)
                scale_wgs = geo_to_wgs.transform(lon_scale, lat_scale, h_scale)
                scale_result = {
                    "projected": {"x": new_x, "y": new_y},
                    "geodetic": {"lon": lon_scale, "lat": lat_scale, "height": h_scale},
                    "wgs84": {"lon": scale_wgs[0], "lat": scale_wgs[1], "height": scale_wgs[2]},
                    "scales": scales,
                    "projected_units": {
                        "unit": units_info.get("horizontal"),
                        "meter_per_unit": horizontal_factor,
                    },
                }
        except Exception:
            scale_result = None

        precise_wgs = precise.get("wgs84")
        if precise_wgs is None:
            geo_to_wgs = context.get("geo_to_wgs") or Transformer.from_crs(geodetic3d, CRS.from_epsg(4979), always_xy=True)
            try:
                wgs = geo_to_wgs.transform(
                    precise["geodetic"]["lon"],
                    precise["geodetic"]["lat"],
                    precise["geodetic"].get("height", ref_h),
                )
                precise["wgs84"] = {"lon": wgs[0], "lat": wgs[1], "height": wgs[2]}
            except Exception:
                pass

        geo_to_wgs = context.get("geo_to_wgs") or Transformer.from_crs(geodetic3d, CRS.from_epsg(4979), always_xy=True)
        reference_wgs = geo_to_wgs.transform(ref_lon, ref_lat, ref_h)

        difference = None
        if precise and scale_result:
            dx_axis = precise["projected"]["x"] - scale_result["projected"]["x"]
            dy_axis = precise["projected"]["y"] - scale_result["projected"]["y"]
            difference = {
                "dx_axis": dx_axis,
                "dy_axis": dy_axis,
                "d_axis": math.hypot(dx_axis, dy_axis),
                "dx_m": dx_axis * horizontal_factor,
                "dy_m": dy_axis * horizontal_factor,
                "d_m": math.hypot(dx_axis * horizontal_factor, dy_axis * horizontal_factor),
                "unit": units_info.get("horizontal"),
                "meter_per_unit": horizontal_factor,
            }

        return {
            "crs": request.crs,
            "reference": {
                "geodetic": {"lon": ref_lon, "lat": ref_lat, "height": ref_h},
                "projected": base_projected,
                "wgs84": {"lon": reference_wgs[0], "lat": reference_wgs[1], "height": reference_wgs[2]},
                "projected_units": {
                    "unit": units_info.get("horizontal"),
                    "meter_per_unit": horizontal_factor,
                },
            },
            "offset": {
                "east": request.offset.east,
                "north": request.offset.north,
                "up": request.offset.up or 0.0,
            },
            "ecef_pipeline": precise,
            "scale_factor": scale_result,
            "difference": difference,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/local-trajectory")
async def transform_local_trajectory(request: LocalTrajectoryRequest):
    if not request.points:
        raise HTTPException(status_code=400, detail="Trajectory points list cannot be empty")

    try:
        service = TransformationService()
        crs = CRS.from_string(request.crs)
        geodetic = getattr(crs, "geodetic_crs", None) or crs
        geodetic3d = geodetic
        try:
            geodetic3d = geodetic.to_3d()
        except Exception:
            pass

        ref_lon = request.reference.lon
        ref_lat = request.reference.lat
        ref_h = request.reference.height or 0.0

        transformer_proj_to_geo = Transformer.from_crs(crs, geodetic3d, always_xy=True)

        if ref_lon is None or ref_lat is None:
            if request.reference.x is None or request.reference.y is None:
                raise HTTPException(status_code=400, detail="Reference must include lon/lat or x/y")
            ref_lon, ref_lat, ref_h = transformer_proj_to_geo.transform(
                request.reference.x,
                request.reference.y,
                ref_h,
            )

        context = service.build_local_offset_context(request.crs, ref_lon, ref_lat, ref_h)
        geo_to_target = context["geo_to_target"]
        geo_to_wgs = context.get("geo_to_wgs") or Transformer.from_crs(geodetic3d, CRS.from_epsg(4979), always_xy=True)
        units_info = service._get_units(crs)
        horizontal_factor = units_info.get("horizontal_factor") or 1.0
        meter_to_axis = 1.0 / horizontal_factor if horizontal_factor else 1.0

        if request.reference.x is not None and request.reference.y is not None:
            base_projected = {"x": request.reference.x, "y": request.reference.y}
        else:
            proj_coords = geo_to_target.transform(ref_lon, ref_lat, ref_h)
            base_projected = {"x": proj_coords[0], "y": proj_coords[1]}

        mode = request.mode
        include_ecef = mode in ("ecef", "both")
        include_scale = mode in ("scale", "both")

        scales = None
        if include_scale and crs.is_projected:
            try:
                scales = service.calculate_scale_factor(request.crs, ref_lon, ref_lat)
            except Exception:
                scales = None

        geod = Geod(ellps='WGS84')

        points_out: List[Dict] = []
        for idx, pt in enumerate(request.points):
            up = -(pt.tvd or 0.0)
            entry: Dict[str, Dict] = {
                "index": idx,
                "name": pt.name,
                "md": pt.md,
                "tvd": pt.tvd,
                "offset": {
                    "east": pt.east,
                    "north": pt.north,
                    "up": up,
                },
            }

            ecef_res = None
            if include_ecef:
                ecef_res = service.local_offset_via_ecef(
                    request.crs,
                    ref_lon,
                    ref_lat,
                    ref_h,
                    pt.east,
                    pt.north,
                    up,
                    context=context,
                )
                entry["ecef"] = ecef_res

            scale_res = None
            if include_scale and scales is not None:
                meridional = scales.get("meridional_scale")
                parallel = scales.get("parallel_scale")
                if meridional is not None and parallel is not None:
                    grid_east_m = pt.east * parallel
                    grid_north_m = pt.north * meridional
                    dx = grid_east_m * meter_to_axis
                    dy = grid_north_m * meter_to_axis
                    new_x = base_projected["x"] + dx
                    new_y = base_projected["y"] + dy
                    lon_scale, lat_scale, h_scale = transformer_proj_to_geo.transform(
                        new_x,
                        new_y,
                        ref_h + up,
                    )
                    wgs_scale = geo_to_wgs.transform(lon_scale, lat_scale, h_scale)
                    scale_res = {
                        "projected": {"x": new_x, "y": new_y},
                        "geodetic": {"lon": lon_scale, "lat": lat_scale, "height": h_scale},
                        "wgs84": {"lon": wgs_scale[0], "lat": wgs_scale[1], "height": wgs_scale[2]},
                        "scales": scales,
                        "projected_units": {
                            "unit": units_info.get("horizontal"),
                            "meter_per_unit": horizontal_factor,
                        },
                    }
                    entry["scale"] = scale_res

            if include_ecef and include_scale and ecef_res and scale_res:
                proj_diff = None
                if ecef_res.get("projected") and scale_res.get("projected"):
                    dx_axis = ecef_res["projected"]["x"] - scale_res["projected"]["x"]
                    dy_axis = ecef_res["projected"]["y"] - scale_res["projected"]["y"]
                    proj_diff = {
                        "dx_axis": dx_axis,
                        "dy_axis": dy_axis,
                        "d_axis": math.hypot(dx_axis, dy_axis),
                        "dx_m": dx_axis * horizontal_factor,
                        "dy_m": dy_axis * horizontal_factor,
                        "d_m": math.hypot(dx_axis * horizontal_factor, dy_axis * horizontal_factor),
                        "unit": units_info.get("horizontal"),
                        "meter_per_unit": horizontal_factor,
                    }
                geod_diff = None
                ecef_wgs = ecef_res.get("wgs84")
                scale_wgs = scale_res.get("wgs84")
                if ecef_wgs and scale_wgs:
                    _, _, dist = geod.inv(
                        ecef_wgs["lon"],
                        ecef_wgs["lat"],
                        scale_wgs["lon"],
                        scale_wgs["lat"],
                    )
                    geod_diff = {"distance": abs(dist)}
                entry["difference"] = {
                    "projected": proj_diff,
                    "geodesic": geod_diff,
                }

            points_out.append(entry)

        reference_wgs = geo_to_wgs.transform(ref_lon, ref_lat, ref_h)

        return {
            "crs": request.crs,
            "mode": mode,
            "reference": {
                "geodetic": {"lon": ref_lon, "lat": ref_lat, "height": ref_h},
                "projected": base_projected,
                "wgs84": {"lon": reference_wgs[0], "lat": reference_wgs[1], "height": reference_wgs[2]},
                "projected_units": {
                    "unit": units_info.get("horizontal"),
                    "meter_per_unit": horizontal_factor,
                },
            },
            "points": points_out,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
