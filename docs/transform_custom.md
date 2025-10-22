# Transform Custom CRS

**Method**: `POST`
**URL**: `/api/transform/custom`

Transform with a custom CRS definition expressed in XML.

## Request

### Example: Geographic input into custom CRS
Use lon/lat when the upstream CRS is geographic.

```http
POST /api/transform/custom
Content-Type: application/json
```

```json
{
  "custom_definition_xml": "<CD_GEO_SYSTEM ...>",
  "source_crs": "EPSG:4326",
  "position": {"lon": 2.2945, "lat": 48.8584}
}
```

### Example: Projected input into custom CRS
Provide `x`/`y` when the source CRS is projected (for example, a grid defined in the XML snippet).

```http
POST /api/transform/custom
Content-Type: application/json
```

```json
{
  "custom_definition_xml": "<CD_GEO_SYSTEM ...>",
  "source_crs": "EPSG:23031",
  "position": {"x": 448249.35, "y": 5411932.67}
}
```

## Response
```json
{
  "x": 448249.30,
  "y": 5411932.60,
  "z": null,
  "units_source": {"horizontal": "degree"},
  "units_target": {"horizontal": "metre"},
  "accuracy": 0.1
}
```
