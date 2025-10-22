# Transform Custom CRS

**Method**: `POST`  \n**URL**: `/api/transform/custom`

Transform with a custom CRS definition expressed in XML.

## Request
POST /api/transform/custom
{
  "custom_definition_xml": "<CD_GEO_SYSTEM ...>",
  "source_crs": "EPSG:4326",
  "position": {"lon": 2.2945, "lat": 48.8584}
}

## Response
{
  "x": 448249.30,
  "y": 5411932.60,
  "z": null,
  "units_source": {"horizontal": "degree"},
  "units_target": {"horizontal": "metre"},
  "accuracy": 0.1
}
