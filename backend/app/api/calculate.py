from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict
from app.services.transformer import TransformationService

router = APIRouter(prefix="/api/calculate", tags=["calculate"])


class FactorsRequest(BaseModel):
    crs: str
    lon: float
    lat: float


@router.post("/grid-convergence")
async def grid_convergence(req: FactorsRequest):
    try:
        service = TransformationService()
        val = service.calculate_grid_convergence(req.crs, req.lon, req.lat)
        return {"meridian_convergence": val}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/scale-factor")
async def scale_factor(req: FactorsRequest):
    try:
        service = TransformationService()
        factors = service.calculate_scale_factor(req.crs, req.lon, req.lat)
        return factors
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

