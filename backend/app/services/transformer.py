from typing import List, Dict, Optional, Tuple

import numpy as np
from pyproj import CRS, Transformer, Proj
from pyproj.transformer import TransformerGroup


class TransformationService:
    def __init__(self):
        self.transformer_cache: Dict[str, Transformer] = {}

    def get_transformer(self, source_crs: str, target_crs: str) -> Transformer:
        key = f"{source_crs}->{target_crs}"
        tr = self.transformer_cache.get(key)
        if tr is None:
            tr = Transformer.from_crs(source_crs, target_crs, always_xy=True)
            self.transformer_cache[key] = tr
        return tr

    def transform_point(
        self, source_crs: str, target_crs: str, x: float, y: float, z: Optional[float] = None
    ) -> Dict:
        transformer = self.get_transformer(source_crs, target_crs)
        if z is not None:
            x_out, y_out, z_out = transformer.transform(x, y, z)
        else:
            x_out, y_out = transformer.transform(x, y)
            z_out = None

        source = CRS.from_string(source_crs)
        target = CRS.from_string(target_crs)

        return {
            "x": x_out,
            "y": y_out,
            "z": z_out,
            "units_source": self._get_units(source),
            "units_target": self._get_units(target),
            "accuracy": transformer.accuracy,
        }

    def get_all_transformation_paths(self, source_crs: str, target_crs: str) -> List[Dict]:
        group = TransformerGroup(source_crs, target_crs, always_xy=True)
        paths: List[Dict] = []
        for i, transformer in enumerate(group.transformers):
            paths.append(
                {
                    "path_id": i,
                    "description": transformer.description,
                    "accuracy": transformer.accuracy,
                    "operations": [op.to_proj4() for op in transformer.operations],
                    "is_best_available": i == 0,
                }
            )
        # Sort by numeric accuracy; None means unknown and sorts last
        return sorted(
            paths, key=lambda x: x["accuracy"] if x["accuracy"] is not None else float("inf")
        )

    def transform_trajectory(
        self, source_crs: str, target_crs: str, points: List[Dict]
    ) -> List[Dict]:
        transformer = self.get_transformer(source_crs, target_crs)
        has_z = "z" in points[0]

        if has_z:
            coords = np.array([[p["x"], p["y"], p.get("z", 0.0)] for p in points], dtype=float)
            transformed = np.array(list(transformer.itransform(coords)))
            out_iter = transformed
        else:
            coords = np.array([[p["x"], p["y"]] for p in points], dtype=float)
            transformed_2d = np.array(list(transformer.itransform(coords)))
            out_iter = np.column_stack([transformed_2d, np.zeros(len(points))])

        results: List[Dict] = []
        for i, (tx, ty, tz) in enumerate(out_iter):
            results.append(
                {
                    "id": points[i].get("id", i),
                    "x": float(tx),
                    "y": float(ty),
                    "z": float(tz) if has_z else None,
                    "original": points[i],
                }
            )
        return results

    def to_geographic(self, crs_code: str, x: float, y: float) -> Dict[str, float]:
        crs = CRS.from_string(crs_code)
        if crs.is_geographic:
            return {"lon": x, "lat": y}
        wgs84 = "EPSG:4326"
        inv = self.get_transformer(crs_code, wgs84)
        lon, lat = inv.transform(x, y)
        return {"lon": float(lon), "lat": float(lat)}

    def calculate_grid_convergence(self, crs_code: str, lon: float, lat: float) -> float:
        crs = CRS.from_string(crs_code)
        if not crs.is_projected:
            raise ValueError("Grid convergence only applies to projected CRS")
        pj = Proj(crs)
        factors = pj.get_factors(lon, lat)
        return float(factors.meridian_convergence)

    def calculate_scale_factor(self, crs_code: str, lon: float, lat: float) -> Dict:
        crs = CRS.from_string(crs_code)
        if not crs.is_projected:
            raise ValueError("Scale factor only applies to projected CRS")
        pj = Proj(crs)
        factors = pj.get_factors(lon, lat)
        return {
            "meridional_scale": float(getattr(factors, "meridional_scale", np.nan)),
            "parallel_scale": float(getattr(factors, "parallel_scale", np.nan)),
            "areal_scale": float(getattr(factors, "areal_scale", np.nan)),
        }

    def _get_units(self, crs: CRS) -> Dict:
        units: Dict[str, float] = {}
        for axis in crs.axis_info:
            if axis.direction in ["east", "north"]:
                units["horizontal"] = axis.unit_name
                units["horizontal_factor"] = axis.unit_conversion_factor
            elif axis.direction == "up":
                units["vertical"] = axis.unit_name
                units["vertical_factor"] = axis.unit_conversion_factor
        return units
