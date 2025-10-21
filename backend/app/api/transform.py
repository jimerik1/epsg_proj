from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional, Dict
from pyproj import CRS

from app.services.transformer import TransformationService
from app.services.crs_parser import CustomCRSParser

router = APIRouter(prefix="/api/transform", tags=["transform"])


class TransformRequest(BaseModel):
    source_crs: str
    target_crs: str
    position: Dict[str, float]
    vertical_value: Optional[float] = None


class TrajectoryRequest(BaseModel):
    source_crs: str
    target_crs: str
    trajectory_points: List[Dict]


class ViaRequest(BaseModel):
    path: List[str]
    position: Dict[str, float]
    vertical_value: Optional[float] = None


class CustomTransformRequest(BaseModel):
    custom_definition_xml: str
    source_crs: str
    position: Dict[str, float]
    vertical_value: Optional[float] = None


@router.post("/direct")
async def transform_direct(request: TransformRequest):
    try:
        service = TransformationService()

        x = request.position.get("x") or request.position.get("lon")
        y = request.position.get("y") or request.position.get("lat")
        z = request.vertical_value

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
        for i in range(len(request.path) - 1):
            src = request.path[i]
            dst = request.path[i + 1]
            out = service.transform_point(src, dst, cur_x, cur_y, cur_z)
            cur_x, cur_y, cur_z = out["x"], out["y"], out.get("z")
            if out["accuracy"] is None:
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

