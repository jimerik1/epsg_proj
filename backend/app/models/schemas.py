from pydantic import BaseModel
from typing import Optional, Dict, List


class Position(BaseModel):
    x: Optional[float] = None
    y: Optional[float] = None
    lon: Optional[float] = None
    lat: Optional[float] = None


class TransformPayload(BaseModel):
    source_crs: str
    target_crs: str
    position: Position
    vertical_value: Optional[float] = None


class TrajectoryPoint(BaseModel):
    id: Optional[str] = None
    x: float
    y: float
    z: Optional[float] = None


class TrajectoryPayload(BaseModel):
    source_crs: str
    target_crs: str
    trajectory_points: List[TrajectoryPoint]

