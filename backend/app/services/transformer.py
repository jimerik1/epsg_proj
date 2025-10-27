from typing import List, Dict, Optional, Tuple, cast

from pathlib import Path

import math

import numpy as np
from pyproj import CRS, Transformer, Proj, datadir, network
from pyproj.transformer import TransformerGroup


# Ensure grid-backed operations can be resolved (downloads permitted when network
# access is available).
try:  # pragma: no cover - defensive only
    network.set_network_enabled(True)
except Exception:
    pass

_LOCAL_PROJ_DATA = Path(__file__).resolve().parents[2] / "proj_data"
if _LOCAL_PROJ_DATA.exists():  # pragma: no cover - path detection
    datadir.append_data_dir(str(_LOCAL_PROJ_DATA))


CUSTOM_CRS_ALIASES: Dict[str, str] = {
    "GIGS:OSGB36_3D": CRS.from_epsg(4277).to_3d().to_wkt(),
    "GIGS:AMERSFOORT_3D": CRS.from_epsg(4289).to_3d().to_wkt(),
    "GIGS:projCRS_A2": CRS.from_proj4(
        "+proj=tmerc +lat_0=49 +lon_0=-2 +k=0.9996012717 "
        "+x_0=400000 +y_0=-100000 +ellps=WGS84 +units=m +no_defs"
    ).to_wkt(),
    "GIGS:projCRS_A23": CRS.from_proj4(
        "+proj=utm +zone=31 +ellps=WGS84 +units=us-ft +no_defs"
    ).to_wkt(),
}

ALIAS_EQUIVALENTS: Dict[str, str] = {
    "GIGS:OSGB36_3D": "EPSG:4277",
    "GIGS:AMERSFOORT_3D": "EPSG:4289",
    "GIGS:projCRS_A2": "GIGS:projCRS_A2",
    "GIGS:projCRS_A23": "GIGS:projCRS_A23",
}


PATH_HINTS: Dict[Tuple[str, str], Dict[str, Optional[List[str]]]] = {
    # Grid-based Australian NTv2 transformation (AGD66 ↔ GDA94)
    ("EPSG:4202", "EPSG:4283"): {
        "preferred_ops": [
            "horizontal_shift_gtiff",
            "agd66 to gda94 (11)",
            "ntv2",
        ]
    },
    ("EPSG:4283", "EPSG:4202"): {
        "preferred_ops": [
            "horizontal_shift_gtiff",
            "agd66 to gda94 (11)",
            "ntv2",
        ]
    },
    ("EPSG:4326", "EPSG:27700"): {
        "preferred_ops": ["inverse of osgb36 to wgs 84 (6)"]
    },
    ("EPSG:27700", "EPSG:4326"): {
        "preferred_ops": ["osgb36 to wgs 84 (6)"]
    },
    ("EPSG:4979", "EPSG:27700"): {
        "preferred_ops": ["inverse of osgb36 to wgs 84 (6)"]
    },
    ("EPSG:27700", "EPSG:4979"): {
        "preferred_ops": ["osgb36 to wgs 84 (6)"]
    },
    # Amersfoort ↔ ETRS89 Molodensky-Badekas paths used in the chained transform
    ("EPSG:4289", "EPSG:4258"): {"preferred_ops": ["molodensky-badekas"]},
    ("EPSG:4258", "EPSG:4289"): {"preferred_ops": ["molodensky-badekas"]},
    ("GIGS:AMERSFOORT_3D", "EPSG:4937"): {"preferred_ops": ["molodensky-badekas"]},
    ("EPSG:4937", "GIGS:AMERSFOORT_3D"): {"preferred_ops": ["molodensky-badekas"]},
    ("EPSG:4258", "EPSG:4326"): {
        "preferred_ops": [
            "position vector",
            "etrs89 to wgs 84",
        ]
    },
    ("EPSG:4326", "EPSG:4258"): {
        "preferred_ops": [
            "position vector",
            "etrs89 to wgs 84",
        ]
    },
    ("EPSG:4277", "EPSG:4326"): {
        "preferred_ops": [
            "position vector",
            "osgb36 to wgs 84 (6)",
        ]
    },
    ("EPSG:4326", "EPSG:4277"): {
        "preferred_ops": [
            "position vector",
            "inverse of osgb36 to wgs 84 (6)",
        ]
    },
}


CHAINED_PATHS: Dict[Tuple[str, str], Dict[str, object]] = {
    # Molodensky-Badekas (9636) via ETRS89, then ETRS89 → WGS84
    ("EPSG:4289", "EPSG:4326"): {
        "sequence": ["EPSG:4289", "EPSG:4258", "EPSG:4326"],
    },
    ("EPSG:4326", "EPSG:4289"): {
        "sequence": ["EPSG:4326", "EPSG:4258", "EPSG:4289"],
    },
    # 3D variant used by GIGS datasets (Amersfoort 3D → ETRS89 3D → WGS 84)
    ("GIGS:AMERSFOORT_3D", "EPSG:4979"): {
        "sequence": ["GIGS:AMERSFOORT_3D", "EPSG:4937", "EPSG:4979"],
        "step_hints": {
            ("GIGS:AMERSFOORT_3D", "EPSG:4937"): {"preferred_ops": ["molodensky-badekas"]},
            ("EPSG:4937", "EPSG:4979"): {"preferred_ops": ["position vector"]},
        },
    },
    ("EPSG:4979", "GIGS:AMERSFOORT_3D"): {
        "sequence": ["EPSG:4979", "EPSG:4937", "GIGS:AMERSFOORT_3D"],
        "step_hints": {
            ("EPSG:4979", "EPSG:4937"): {"preferred_ops": ["position vector"]},
            ("EPSG:4937", "GIGS:AMERSFOORT_3D"): {"preferred_ops": ["molodensky-badekas"]},
        },
    },
    # Position Vector 3D conversions (OSGB36 3D ↔ WGS 84 3D) routed via 2D EPSG CRS.
    ("GIGS:OSGB36_3D", "EPSG:4979"): {
        "sequence": ["GIGS:OSGB36_3D", "EPSG:4277", "EPSG:4326", "EPSG:4979"],
        "step_hints": {
            ("GIGS:OSGB36_3D", "EPSG:4277"): {"preferred_ops": ["position vector"]},
            ("EPSG:4277", "EPSG:4326"): {"preferred_ops": ["position vector", "osgb36 to wgs 84 (6)"]},
            ("EPSG:4326", "EPSG:4979"): {"preferred_ops": ["position vector"]},
        },
    },
    ("EPSG:4979", "GIGS:OSGB36_3D"): {
        "sequence": ["EPSG:4979", "EPSG:4326", "EPSG:4277", "GIGS:OSGB36_3D"],
        "step_hints": {
            ("EPSG:4979", "EPSG:4326"): {"preferred_ops": ["position vector"]},
            ("EPSG:4326", "EPSG:4277"): {"preferred_ops": ["position vector", "inverse of osgb36 to wgs 84 (6)"]},
            ("EPSG:4277", "GIGS:OSGB36_3D"): {"preferred_ops": ["position vector"]},
        },
    },
}


class TransformationService:
    def __init__(self):
        self.transformer_cache: Dict[str, Transformer] = {}

    def _canonical_crs(self, crs_code: str) -> str:
        label = crs_code.strip()
        if label in CUSTOM_CRS_ALIASES:
            return label
        try:
            crs = CRS.from_user_input(label)
            authority = crs.to_authority()
            if authority:
                return f"{authority[0]}:{authority[1]}"
        except Exception:
            pass
        return label

    def _resolve_crs_input(self, crs_code: str) -> str:
        label = crs_code.strip()
        return CUSTOM_CRS_ALIASES.get(label, label)

    def _crs_from_input(self, crs_code: str) -> CRS:
        resolved = self._resolve_crs_input(crs_code)
        return CRS.from_user_input(resolved)

    @staticmethod
    def _values_finite(*values: Optional[float]) -> bool:
        for value in values:
            if value is None:
                continue
            if not math.isfinite(value):
                return False
        return True

    def _transformer_matches(self, transformer: Transformer, ops_lower: List[str]) -> bool:
        if not ops_lower:
            return True
        description = (transformer.description or "").lower()
        if any(term in description for term in ops_lower):
            return True
        for op in getattr(transformer, "operations", []) or []:
            for attr in ("name", "method_name"):
                value = getattr(op, attr, None)
                if isinstance(value, str) and any(term in value.lower() for term in ops_lower):
                    return True
            try:
                proj4 = op.to_proj4()  # type: ignore[attr-defined]
            except Exception:
                proj4 = None
            if isinstance(proj4, str) and any(term in proj4.lower() for term in ops_lower):
                return True
        return False

    def _collect_preferred_ops(self, preferred_ops: Optional[List[str]]) -> List[str]:
        if not preferred_ops:
            return []
        return [str(item).lower() for item in preferred_ops if item]

    def _candidate_transformers(
        self,
        resolved_source: str,
        resolved_target: str,
        *,
        path_id: Optional[int],
        ops_lower: List[str],
    ) -> List[Transformer]:
        try:
            group = TransformerGroup(
                resolved_source,
                resolved_target,
                always_xy=True,
                allow_superseded=True,
            )
            base_transformers = list(group.transformers)
        except Exception:
            base_transformers = []

        candidates: List[Transformer] = []

        def append(transformer: Transformer) -> None:
            if all(id(transformer) != id(existing) for existing in candidates):
                candidates.append(transformer)

        if path_id is not None and 0 <= path_id < len(base_transformers):
            append(base_transformers[path_id])

        if not candidates and ops_lower:
            for transformer in base_transformers:
                if self._transformer_matches(transformer, ops_lower):
                    append(transformer)

        for transformer in base_transformers:
            append(transformer)

        if not candidates:
            append(
                Transformer.from_crs(
                    resolved_source,
                    resolved_target,
                    always_xy=True,
                )
            )

        return candidates

    def _run_transform(
        self,
        source_crs: str,
        target_crs: str,
        x: float,
        y: float,
        z: Optional[float],
        *,
        path_id: Optional[int] = None,
        preferred_ops: Optional[List[str]] = None,
    ) -> Tuple[float, float, Optional[float], Optional[float]]:
        canonical_source = self._canonical_crs(source_crs)
        canonical_target = self._canonical_crs(target_crs)
        resolved_source = self._resolve_crs_input(source_crs)
        resolved_target = self._resolve_crs_input(target_crs)

        ops_lower = self._collect_preferred_ops(preferred_ops)
        cache_key = (
            f"{canonical_source}->{canonical_target}"
            f"#path={'auto' if path_id is None else path_id}"
            f"#ops={'|'.join(ops_lower) if ops_lower else 'default'}"
        )

        def attempt(transformer: Transformer) -> Tuple[float, float, Optional[float]]:
            x_out, y_out, z_out = self._apply_transform(transformer, x, y, z)
            if not self._values_finite(x_out, y_out, z_out):
                raise ValueError("Transformer produced non-finite output")
            return x_out, y_out, z_out

        cached = self.transformer_cache.get(cache_key)
        last_error: Optional[Exception] = None

        if cached is not None:
            try:
                x_out, y_out, z_out = attempt(cached)
                return x_out, y_out, z_out, cached.accuracy
            except Exception as exc:
                last_error = exc
                self.transformer_cache.pop(cache_key, None)

        candidates = self._candidate_transformers(
            resolved_source,
            resolved_target,
            path_id=path_id,
            ops_lower=ops_lower,
        )

        for transformer in candidates:
            try:
                x_out, y_out, z_out = attempt(transformer)
            except Exception as exc:
                last_error = exc
                continue
            self.transformer_cache[cache_key] = transformer
            return x_out, y_out, z_out, transformer.accuracy

        if last_error is not None:
            raise last_error
        raise RuntimeError("No suitable transformer available")

    def _build_transformer(
        self,
        source_crs: str,
        target_crs: str,
        path_id: Optional[int] = None,
        preferred_ops: Optional[List[str]] = None,
    ) -> Transformer:
        canonical_source = self._canonical_crs(source_crs)
        canonical_target = self._canonical_crs(target_crs)
        resolved_source = self._resolve_crs_input(source_crs)
        resolved_target = self._resolve_crs_input(target_crs)
        ops_lower = self._collect_preferred_ops(preferred_ops)
        cache_key = (
            f"{canonical_source}->{canonical_target}"
            f"#path={'auto' if path_id is None else path_id}"
            f"#ops={'|'.join(ops_lower) if ops_lower else 'default'}"
        )

        cached = self.transformer_cache.get(cache_key)
        if cached is not None:
            return cached

        candidates = self._candidate_transformers(
            resolved_source,
            resolved_target,
            path_id=path_id,
            ops_lower=ops_lower,
        )
        selected = candidates[0]

        self.transformer_cache[cache_key] = selected
        if path_id is None and not ops_lower:
            self.transformer_cache[f"{canonical_source}->{canonical_target}#default"] = selected
        return selected

    def get_transformer(self, source_crs: str, target_crs: str) -> Transformer:
        return self._build_transformer(source_crs, target_crs)

    def get_transformer_selected(
        self,
        source_crs: str,
        target_crs: str,
        path_id: Optional[int] = None,
        preferred_ops: Optional[List[str]] = None,
    ) -> Transformer:
        return self._build_transformer(
            source_crs,
            target_crs,
            path_id=path_id,
            preferred_ops=preferred_ops,
        )

    def _apply_transform(
        self,
        transformer: Transformer,
        x: float,
        y: float,
        z: Optional[float],
    ) -> Tuple[float, float, Optional[float]]:
        if z is not None:
            x_out, y_out, z_out = transformer.transform(x, y, z)
        else:
            x_out, y_out = transformer.transform(x, y)
            z_out = None
        return x_out, y_out, z_out

    def _format_response(
        self,
        source_crs: str,
        target_crs: str,
        x_out: float,
        y_out: float,
        z_out: Optional[float],
        accuracy: Optional[float],
    ) -> Dict:
        source = CRS.from_user_input(self._resolve_crs_input(source_crs))
        target = CRS.from_user_input(self._resolve_crs_input(target_crs))
        return {
            "x": x_out,
            "y": y_out,
            "z": z_out,
            "units_source": self._get_units(source),
            "units_target": self._get_units(target),
            "accuracy": accuracy,
        }

    def _transform_chain(
        self,
        source_crs: str,
        target_crs: str,
        canonical_source: str,
        canonical_target: str,
        x: float,
        y: float,
        z: Optional[float],
        chain_config: Dict[str, object],
    ) -> Dict:
        sequence = list(chain_config.get("sequence", []) or [])
        if not sequence:
            raise ValueError("Invalid chained transformation configuration")
        if sequence[0] != canonical_source:
            sequence[0] = canonical_source
        if sequence[-1] != canonical_target:
            sequence[-1] = canonical_target

        raw_hints = chain_config.get("step_hints", {})
        step_hints = cast(
            Dict[Tuple[str, str], Dict[str, Optional[List[str]]]],
            raw_hints if isinstance(raw_hints, dict) else {},
        )

        current_x, current_y, current_z = x, y, z
        accuracies: List[Optional[float]] = []

        for idx in range(len(sequence) - 1):
            step_source = sequence[idx]
            step_target = sequence[idx + 1]
            hint = step_hints.get((step_source, step_target)) or PATH_HINTS.get((step_source, step_target)) or {}

            alias_equiv_source = ALIAS_EQUIVALENTS.get(step_source)
            if alias_equiv_source and self._canonical_crs(alias_equiv_source) == self._canonical_crs(step_target):
                accuracies.append(accuracies[-1] if accuracies else None)
                continue

            alias_equiv = ALIAS_EQUIVALENTS.get(step_target)
            if alias_equiv and self._canonical_crs(step_source) == self._canonical_crs(alias_equiv):
                # Alias shares the same underlying CRS definition; treat as identity.
                accuracies.append(accuracies[-1] if accuracies else None)
                continue

            current_x, current_y, current_z, accuracy = self._run_transform(
                step_source,
                step_target,
                current_x,
                current_y,
                current_z,
                path_id=hint.get("path_id"),
                preferred_ops=hint.get("preferred_ops"),
            )
            accuracies.append(accuracy)

        accuracy = next((val for val in reversed(accuracies) if val is not None), None)
        return self._format_response(source_crs, target_crs, current_x, current_y, current_z, accuracy)

    def transform_point(
        self, source_crs: str, target_crs: str, x: float, y: float, z: Optional[float] = None
    ) -> Dict:
        canonical_source = self._canonical_crs(source_crs)
        canonical_target = self._canonical_crs(target_crs)

        chain = CHAINED_PATHS.get((canonical_source, canonical_target))
        if chain:
            return self._transform_chain(
                source_crs,
                target_crs,
                canonical_source,
                canonical_target,
                x,
                y,
                z,
                chain,
            )

        hint = PATH_HINTS.get((canonical_source, canonical_target)) or {}
        x_out, y_out, z_out, accuracy = self._run_transform(
            source_crs,
            target_crs,
            x,
            y,
            z,
            path_id=hint.get("path_id"),
            preferred_ops=hint.get("preferred_ops"),
        )
        return self._format_response(source_crs, target_crs, x_out, y_out, z_out, accuracy)

    def transform_point_with_selection(
        self,
        source_crs: str,
        target_crs: str,
        x: float,
        y: float,
        z: Optional[float] = None,
        path_id: Optional[int] = None,
        preferred_ops: Optional[List[str]] = None,
    ) -> Dict:
        x_out, y_out, z_out, accuracy = self._run_transform(
            source_crs,
            target_crs,
            x,
            y,
            z,
            path_id=path_id,
            preferred_ops=preferred_ops,
        )
        result = self._format_response(source_crs, target_crs, x_out, y_out, z_out, accuracy)
        result["path_id"] = path_id
        return result

    def get_all_transformation_paths(self, source_crs: str, target_crs: str) -> List[Dict]:
        group = TransformerGroup(
            self._resolve_crs_input(source_crs),
            self._resolve_crs_input(target_crs),
            always_xy=True,
            allow_superseded=True,
        )
        paths: List[Dict] = []
        for i, transformer in enumerate(group.transformers):
            ops_info: List[Dict[str, Optional[str]]] = []
            for op in getattr(transformer, "operations", []) or []:
                try:
                    ops_info.append(
                        {
                            "name": getattr(op, "name", None),
                            "method_name": getattr(op, "method_name", None),
                            "authority": getattr(op, "authority", None),
                            "code": getattr(op, "code", None) or getattr(op, "id", None),
                        }
                    )
                except Exception:
                    # Best-effort only; keep going if unknown object shape
                    ops_info.append({})
            paths.append(
                {
                    "path_id": i,
                    "description": transformer.description,
                    "accuracy": transformer.accuracy,
                    "accuracy_unit": "meter",
                    "operations": [op.to_proj4() for op in transformer.operations],
                    "operations_info": ops_info,
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
        crs = self._crs_from_input(crs_code)
        if crs.is_geographic:
            return {"lon": x, "lat": y}
        wgs84 = "EPSG:4326"
        inv = self.get_transformer(crs_code, wgs84)
        lon, lat = inv.transform(x, y)
        return {"lon": float(lon), "lat": float(lat)}

    def calculate_grid_convergence(self, crs_code: str, lon: float, lat: float) -> float:
        crs = CRS.from_user_input(self._resolve_crs_input(crs_code))
        if not crs.is_projected:
            raise ValueError("Grid convergence only applies to projected CRS")
        pj = Proj(crs)
        factors = pj.get_factors(lon, lat)
        return float(factors.meridian_convergence)

    def calculate_scale_factor(self, crs_code: str, lon: float, lat: float) -> Dict:
        crs = CRS.from_user_input(self._resolve_crs_input(crs_code))
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
        target_crs = self._crs_from_input(crs_code)
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
