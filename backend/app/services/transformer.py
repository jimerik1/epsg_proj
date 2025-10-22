from typing import List, Dict, Optional, Tuple

import math

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

    def _get_geodetic_crs(self, crs: CRS) -> CRS:
        try:
            geo = crs.geodetic_crs
        except Exception:
            geo = None
        if geo is None:
            return crs
        return geo

    def _ensure_3d(self, crs: CRS) -> CRS:
        try:
            if hasattr(crs, "is_geocentric") and crs.is_geocentric:
                return crs
        except Exception:
            pass
        try:
            return crs.to_3d()
        except Exception:
            return crs

    def _create_local_offset_context(
        self,
        crs_code: str,
        lon: float,
        lat: float,
        height: float,
    ) -> Dict:
        target_crs = CRS.from_string(crs_code)
        geodetic = self._get_geodetic_crs(target_crs)
        geodetic3d = self._ensure_3d(geodetic)

        ecef = CRS.from_epsg(4978)
        geo_to_ecef = Transformer.from_crs(geodetic3d, ecef, always_xy=True)
        ecef_to_geo = Transformer.from_crs(ecef, geodetic3d, always_xy=True)
        geo_to_target = Transformer.from_crs(geodetic3d, target_crs, always_xy=True)

        try:
            geo_to_wgs = Transformer.from_crs(geodetic3d, CRS.from_epsg(4979), always_xy=True)
        except Exception:
            geo_to_wgs = None

        origin_ecef = geo_to_ecef.transform(lon, lat, height)
        lon_rad = math.radians(lon)
        lat_rad = math.radians(lat)

        context = {
            "crs": target_crs,
            "geodetic": geodetic3d,
            "geo_to_ecef": geo_to_ecef,
            "ecef_to_geo": ecef_to_geo,
            "geo_to_target": geo_to_target,
            "geo_to_wgs": geo_to_wgs,
            "origin_ecef": origin_ecef,
            "sin_lon": math.sin(lon_rad),
            "cos_lon": math.cos(lon_rad),
            "sin_lat": math.sin(lat_rad),
            "cos_lat": math.cos(lat_rad),
            "origin_height": height,
        }
        return context

    def build_local_offset_context(
        self,
        crs_code: str,
        lon: float,
        lat: float,
        height: float,
    ) -> Dict:
        return self._create_local_offset_context(crs_code, lon, lat, height)

    def local_offset_via_ecef(
        self,
        crs_code: str,
        lon: float,
        lat: float,
        height: float,
        east: float,
        north: float,
        up: float,
        context: Optional[Dict] = None,
    ) -> Dict:
        ctx = context or self._create_local_offset_context(crs_code, lon, lat, height)

        sin_lon = ctx["sin_lon"]
        cos_lon = ctx["cos_lon"]
        sin_lat = ctx["sin_lat"]
        cos_lat = ctx["cos_lat"]

        delta_x = -sin_lon * east - sin_lat * cos_lon * north + cos_lat * cos_lon * up
        delta_y = cos_lon * east - sin_lat * sin_lon * north + cos_lat * sin_lon * up
        delta_z = cos_lat * north + sin_lat * up

        new_ecef = (
            ctx["origin_ecef"][0] + delta_x,
            ctx["origin_ecef"][1] + delta_y,
            ctx["origin_ecef"][2] + delta_z,
        )

        lon_new, lat_new, h_new = ctx["ecef_to_geo"].transform(*new_ecef)
        proj = ctx["geo_to_target"].transform(lon_new, lat_new, h_new)

        result = {
            "geodetic": {"lon": lon_new, "lat": lat_new, "height": h_new},
            "projected": {"x": proj[0], "y": proj[1]},
        }

        geo_to_wgs = ctx.get("geo_to_wgs")
        if geo_to_wgs is not None:
            try:
                wgs = geo_to_wgs.transform(lon_new, lat_new, h_new)
                result["wgs84"] = {"lon": wgs[0], "lat": wgs[1], "height": wgs[2]}
            except Exception:
                pass

        return result

    def local_offset_via_ecef_bulk(
        self,
        crs_code: str,
        lon: float,
        lat: float,
        height: float,
        offsets: List[Tuple[float, float, float]],
    ) -> List[Dict]:
        ctx = self._create_local_offset_context(crs_code, lon, lat, height)
        results = []
        for east, north, up in offsets:
            results.append(
                self.local_offset_via_ecef(
                    crs_code,
                    lon,
                    lat,
                    height,
                    east,
                    north,
                    up,
                    context=ctx,
                )
            )
        return results
