import xml.etree.ElementTree as ET
from typing import Dict, List


class CustomCRSParser:
    """Parse custom CRS XML definitions to PROJ strings"""

    def _parse_element(self, root: ET.Element, tag: str):
        el = root.find(tag)
        if el is None:
            return None
        return {k: v for k, v in el.attrib.items()}

    def parse_xml_to_proj(self, xml_string: str) -> str:
        # Ensure a single XML root: try parse, else wrap
        try:
            root = ET.fromstring(xml_string)
        except ET.ParseError:
            root = ET.fromstring(f"<root>{xml_string}</root>")

        geo_system = self._parse_element(root, 'CD_GEO_SYSTEM') or {}
        geo_zone = self._parse_element(root, 'CD_GEO_ZONE') or {}
        geo_datum = self._parse_element(root, 'CD_GEO_DATUM') or {}
        geo_ellipsoid = self._parse_element(root, 'CD_GEO_ELLIPSOID') or {}

        proj_parts: List[str] = []

        # Projection
        if geo_zone:
            geo_system_id = geo_system.get('geo_system_id', '')
            geo_zone_id = geo_zone.get('geo_zone_id', '')
            if 'UTM' in geo_system_id or 'UTM' in geo_zone_id:
                zone = geo_zone_id.replace('UTM-', '').replace('N', '').replace('S', '')
                if zone:
                    proj_parts.append(f"+proj=utm +zone={zone}")
                if 'S' in geo_zone_id:
                    proj_parts.append("+south")
            else:
                proj_parts.append("+proj=tmerc")
                proj_parts.append(f"+lat_0={geo_zone.get('lat_origin', 0)}")
                proj_parts.append(f"+lon_0={geo_zone.get('lon_origin', 0)}")
                proj_parts.append(f"+k_0={geo_zone.get('scale_factor', 1)}")
                proj_parts.append(f"+x_0={geo_zone.get('false_easting', 0)}")
                proj_parts.append(f"+y_0={geo_zone.get('false_northing', 0)}")

        # Ellipsoid
        if geo_ellipsoid:
            a = geo_ellipsoid.get('semi_major')
            e = geo_ellipsoid.get('first_eccentricity')
            if a:
                proj_parts.append(f"+a={a}")
            if e:
                proj_parts.append(f"+e={e}")

        # Datum shifts
        if geo_datum:
            x = geo_datum.get('x_shift', '0')
            y = geo_datum.get('y_shift', '0')
            z = geo_datum.get('z_shift', '0')
            proj_parts.append(f"+towgs84={x},{y},{z}")

        return " ".join(proj_parts).strip()

    # Optional future extensions
    def dict_to_proj(self, definition: Dict) -> str:
        parts = []
        for k, v in definition.items():
            parts.append(f"+{k}={v}")
        return " ".join(parts)
