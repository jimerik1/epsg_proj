# CRS Transformation Platform with PyProj - Development Specification

## Project Overview
Build a cloud-ready coordinate reference system (CRS) transformation platform for directional drilling and anti-collision calculations. The system will use PyProj (Python wrapper for PROJ 9.x) to handle complex coordinate transformations, custom CRS definitions, vertical datums, and provide transformation accuracy information. The platform must be dockerized and runnable with a single `docker-compose up --build` command.

## Project Structure
```
crs-transformation-platform/
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   ├── __init__.py
│   │   │   ├── transform.py        # Transformation endpoints
│   │   │   ├── crs.py             # CRS info/search endpoints
│   │   │   └── calculate.py       # Grid convergence/scale factor
│   │   ├── services/
│   │   │   ├── __init__.py
│   │   │   ├── transformer.py     # Core transformation logic
│   │   │   ├── crs_parser.py      # Custom CRS definition parser
│   │   │   ├── accuracy.py        # Accuracy calculations
│   │   │   └── cache.py           # Redis caching
│   │   ├── models/
│   │   │   ├── __init__.py
│   │   │   └── schemas.py         # Pydantic models
│   │   └── main.py                # FastAPI app
│   ├── tests/
│   │   └── test_transformations.py
│   ├── requirements.txt
│   ├── Dockerfile
│   └── .env.example
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── TransformPanel.jsx
│   │   │   ├── MapView.jsx
│   │   │   ├── CRSSelector.jsx
│   │   │   ├── CustomCRSEditor.jsx
│   │   │   ├── AccuracyDisplay.jsx
│   │   │   └── TrajectoryInput.jsx
│   │   ├── services/
│   │   │   └── api.js
│   │   ├── App.jsx
│   │   └── index.js
│   ├── public/
│   │   └── index.html
│   ├── package.json
│   └── Dockerfile
├── docker-compose.yml
├── .gitignore
├── .dockerignore
├── README.md
└── TODO.md
```

## Task List (TODO.md format)

### Phase 1: Environment Setup
- [ ] Initialize project structure with all directories
- [ ] Create Docker configuration for backend (Python 3.11 + PyProj)
- [ ] Create Docker configuration for frontend (Node.js + React)
- [ ] Set up docker-compose.yml with hot-reload for development
- [ ] Configure .gitignore and .dockerignore files
- [ ] Create requirements.txt with pyproj, fastapi, uvicorn, redis, pydantic, numpy
- [ ] Test Docker setup with `docker-compose up --build`

### Phase 2: Backend Core Services with PyProj
- [ ] Initialize FastAPI application with CORS middleware
- [ ] Create PyProj transformer service class
- [ ] Implement TransformerGroup for finding all transformation paths
- [ ] Create CRS unit detection using pyproj.CRS.axis_info
- [ ] Implement vertical/compound CRS support
- [ ] Build custom CRS parser for XML-style definitions to PROJ string
- [ ] Create grid convergence calculator using get_factors()
- [ ] Create scale factor calculator
- [ ] Implement transformation accuracy extractor
- [ ] Set up Redis caching for transformation results
- [ ] Configure PROJ_NETWORK=ON for automatic grid download

### Phase 3: Core Transformation Endpoints
```python
# Implementation structure for each endpoint
```
- [ ] POST /api/transform/direct
  - Use Transformer.from_crs() with always_xy=True
  - Handle both geographic and projected inputs
  - Support vertical transformations with compound CRS
- [ ] POST /api/transform/via
  - Chain multiple Transformer objects
  - Track cumulative accuracy
- [ ] POST /api/transform/custom
  - Parse custom definition to PROJ string
  - Create CRS.from_proj4() or CRS.from_wkt()
- [ ] POST /api/transform/trajectory
  - Use transformer.itransform() for batch processing
  - Optimize with numpy arrays

### Phase 4: Metadata & Analysis Endpoints
- [ ] GET /api/crs/units/{epsg_code}
  - Use CRS.axis_info for unit extraction
  - Include unit conversion factors
- [ ] GET /api/transform/accuracy
  - Extract from Transformer.accuracy attribute
  - Handle multi-step accuracy aggregation
- [ ] GET /api/transform/available-paths
  - Use TransformerGroup to get all paths
  - Sort by accuracy (None means unknown, not infinite)
- [ ] POST /api/crs/match
  - Compare custom CRS parameters with pyproj.database.query_crs_info()
  - Calculate confidence scores
- [ ] POST /api/calculate/grid-convergence
  - Use Proj.get_factors() for projected CRS
  - Return meridian_convergence
- [ ] POST /api/calculate/scale-factor
  - Use Proj.get_factors() for projected CRS
  - Return meridional_scale and parallel_scale
- [ ] GET /api/crs/search
  - Use query_crs_info() with filters
  - Support area_of_interest parameter

### Phase 5: Custom CRS Definition Handler
- [ ] Parse XML format (CD_GEO_SYSTEM, CD_GEO_ZONE, CD_GEO_DATUM, CD_GEO_ELLIPSOID)
- [ ] Convert to PROJ string format
- [ ] Support vertical datum in custom definitions
- [ ] Validate using CRS.from_proj4() or CRS.from_wkt()
- [ ] Cache parsed definitions in Redis

### Phase 6: Frontend Demo GUI
- [ ] Set up React application with Material-UI or Ant Design
- [ ] Create main layout with input/output panels
- [ ] Implement CRS selector with EPSG search
- [ ] Add custom CRS definition editor with XML syntax
- [ ] Create position input (DD, DMS, projected coordinates)
- [ ] Add trajectory input component for batch transformations
- [ ] Integrate Leaflet map with position markers
- [ ] Display transformation results with units
- [ ] Show accuracy information and available paths
- [ ] Display grid convergence and scale factor
- [ ] Add export functionality (CSV, JSON)

### Phase 7: Testing & Error Handling
- [ ] Write pytest tests for all transformations
- [ ] Test known transformation pairs (WGS84/UTM, ED50/WGS84, etc.)
- [ ] Test vertical transformations with known points
- [ ] Add error handling for invalid CRS codes
- [ ] Handle transformation failures gracefully
- [ ] Test custom CRS definitions

## Detailed API Implementation with PyProj

### Core Backend Implementation (main.py)
```python
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pyproj import CRS, Transformer, TransformerGroup
from pyproj.database import query_crs_info
from pyproj.aoi import AreaOfInterest
from pyproj.exceptions import CRSError
import redis
import json
from typing import List, Optional
import numpy as np

app = FastAPI(title="CRS Transformation Platform")

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Redis connection
redis_client = redis.Redis(host='redis', port=6379, decode_responses=True)
```

### Transformation Service (services/transformer.py)
```python
from pyproj import CRS, Transformer, TransformerGroup
from typing import List, Dict, Tuple, Optional
import numpy as np

class TransformationService:
    def __init__(self):
        self.transformer_cache = {}
    
    def get_transformer(self, source_crs: str, target_crs: str) -> Transformer:
        """Get or create a transformer with caching"""
        cache_key = f"{source_crs}_{target_crs}"
        if cache_key not in self.transformer_cache:
            self.transformer_cache[cache_key] = Transformer.from_crs(
                source_crs, target_crs, always_xy=True
            )
        return self.transformer_cache[cache_key]
    
    def transform_point(self, source_crs: str, target_crs: str, 
                       x: float, y: float, z: Optional[float] = None) -> Dict:
        """Transform a single point with metadata"""
        transformer = self.get_transformer(source_crs, target_crs)
        
        if z is not None:
            x_out, y_out, z_out = transformer.transform(x, y, z)
        else:
            x_out, y_out = transformer.transform(x, y)
            z_out = None
        
        # Get units
        source = CRS.from_string(source_crs)
        target = CRS.from_string(target_crs)
        
        return {
            "x": x_out,
            "y": y_out,
            "z": z_out,
            "units_source": self._get_units(source),
            "units_target": self._get_units(target),
            "accuracy": transformer.accuracy
        }
    
    def get_all_transformation_paths(self, source_crs: str, target_crs: str) -> List[Dict]:
        """Get all available transformation paths with accuracy"""
        group = TransformerGroup(source_crs, target_crs, always_xy=True)
        paths = []
        
        for i, transformer in enumerate(group.transformers):
            paths.append({
                "path_id": i,
                "description": transformer.description,
                "accuracy": transformer.accuracy,
                "operations": [op.to_proj4() for op in transformer.operations],
                "is_best_available": i == 0  # First is best by default
            })
        
        return sorted(paths, key=lambda x: x["accuracy"] if x["accuracy"] else float('inf'))
    
    def transform_trajectory(self, source_crs: str, target_crs: str, 
                           points: List[Dict]) -> List[Dict]:
        """Efficiently transform multiple points"""
        transformer = self.get_transformer(source_crs, target_crs)
        
        # Convert to numpy arrays for efficiency
        coords = np.array([[p['x'], p['y'], p.get('z', 0)] for p in points])
        
        # Transform all points at once
        if 'z' in points[0]:
            transformed = np.array(list(transformer.itransform(coords)))
        else:
            coords_2d = coords[:, :2]
            transformed_2d = np.array(list(transformer.itransform(coords_2d)))
            transformed = np.column_stack([transformed_2d, np.zeros(len(points))])
        
        # Format results
        results = []
        for i, (x, y, z) in enumerate(transformed):
            results.append({
                "id": points[i].get('id', i),
                "x": x,
                "y": y,
                "z": z if 'z' in points[i] else None,
                "original": points[i]
            })
        
        return results
    
    def calculate_grid_convergence(self, crs_code: str, lon: float, lat: float) -> float:
        """Calculate grid convergence at a point"""
        crs = CRS.from_string(crs_code)
        if not crs.is_projected:
            raise ValueError("Grid convergence only applies to projected CRS")
        
        factors = crs.get_factors(lon, lat)
        return factors.meridian_convergence
    
    def calculate_scale_factor(self, crs_code: str, lon: float, lat: float) -> Dict:
        """Calculate scale factors at a point"""
        crs = CRS.from_string(crs_code)
        if not crs.is_projected:
            raise ValueError("Scale factor only applies to projected CRS")
        
        factors = crs.get_factors(lon, lat)
        return {
            "meridional_scale": factors.meridional_scale,
            "parallel_scale": factors.parallel_scale,
            "areal_scale": factors.areal_scale
        }
    
    def _get_units(self, crs: CRS) -> Dict:
        """Extract unit information from CRS"""
        units = {}
        for axis in crs.axis_info:
            if axis.direction in ['east', 'north']:
                units['horizontal'] = axis.unit_name
                units['horizontal_factor'] = axis.unit_conversion_factor
            elif axis.direction == 'up':
                units['vertical'] = axis.unit_name
                units['vertical_factor'] = axis.unit_conversion_factor
        return units
```

### Custom CRS Parser (services/crs_parser.py)
```python
import xml.etree.ElementTree as ET
from typing import Dict

class CustomCRSParser:
    """Parse custom CRS XML definitions to PROJ strings"""
    
    def parse_xml_to_proj(self, xml_string: str) -> str:
        """Convert XML CRS definition to PROJ string"""
        root = ET.fromstring(xml_string)
        
        # Extract components
        geo_system = self._parse_element(root, 'CD_GEO_SYSTEM')
        geo_zone = self._parse_element(root, 'CD_GEO_ZONE')
        geo_datum = self._parse_element(root, 'CD_GEO_DATUM')
        geo_ellipsoid = self._parse_element(root, 'CD_GEO_ELLIPSOID')
        
        # Build PROJ string
        proj_parts = []
        
        # Projection
        if geo_zone:
            if 'UTM' in geo_system.get('geo_system_id', ''):
                zone = geo_zone.get('geo_zone_id', '').replace('UTM-', '').replace('N', '')
                proj_parts.append(f"+proj=utm +zone={zone}")
                if 'S' in geo_zone.get('geo_zone_id', ''):
                    proj_parts.append("+south")
            else:
                # Handle other projections
                proj_parts.append(f"+proj=tmerc")
                proj_parts.append(f"+lat_0={geo_zone.get('lat_origin', 0)}")
                proj_parts.append(f"+lon_0={geo_zone.get('lon_origin', 0)}")
                proj_parts.append(f"+k_0={geo_zone.get('scale_factor', 1)}")
                proj_parts.append(f"+x_0={geo_zone.get('false_easting', 0)}")
                proj_parts.append(f"+y_0={geo_zone.get('false_northing', 0)}")
        
        # Ellipsoid
        if geo_ellipsoid:
            a = geo_ellipsoid.get('semi_major')
            e = geo_ellipsoid.get('first_eccentricity')
            proj_parts.append(f"+a={a}")
            proj_parts.append(f"+e={e}")
        
        # Datum shifts
        if geo_datum:
            proj_parts.append(f"+towgs84={geo_datum.get('x_shift',0)},{geo_datum.get('y_shift',0)},{geo_datum.get('z_shift',0)}")
        
        return " ".join(proj_parts)
    
    def match_to_epsg(self, custom_definition: Dict) -> List[Dict]:
        """Find matching EPSG codes for custom definition"""
        # Convert to PROJ string first
        proj_string = self.dict_to_proj(custom_definition)
        custom_crs = CRS.from_proj4(proj_string)
        
        # Query similar CRS
        results = query_crs_info(
            auth_name="EPSG",
            pj_types=["PROJECTED_CRS", "GEOGRAPHIC_CRS", "COMPOUND_CRS"]
        )
        
        matches = []
        for crs_info in results:
            try:
                epsg_crs = CRS.from_epsg(crs_info.code)
                if self._compare_crs(custom_crs, epsg_crs):
                    matches.append({
                        "epsg_code": f"EPSG:{crs_info.code}",
                        "name": crs_info.name,
                        "confidence": self._calculate_confidence(custom_crs, epsg_crs)
                    })
            except:
                continue
        
        return sorted(matches, key=lambda x: x['confidence'], reverse=True)
```

### API Endpoints (api/transform.py)
```python
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional, Dict

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

@router.post("/direct")
async def transform_direct(request: TransformRequest):
    """Direct coordinate transformation"""
    try:
        service = TransformationService()
        
        # Determine input type
        x = request.position.get('x') or request.position.get('lon')
        y = request.position.get('y') or request.position.get('lat')
        z = request.vertical_value
        
        result = service.transform_point(
            request.source_crs, 
            request.target_crs,
            x, y, z
        )
        
        # Add geographic/projected positions
        source_crs = CRS.from_string(request.source_crs)
        target_crs = CRS.from_string(request.target_crs)
        
        response = {
            "map_position": {"x": result["x"], "y": result["y"]},
            "vertical_output": result.get("z"),
            "units_used": {
                "source": result["units_source"],
                "target": result["units_target"]
            },
            "transformation_accuracy": result["accuracy"]
        }
        
        # Calculate grid convergence and scale factor if projected
        if target_crs.is_projected:
            response["grid_convergence"] = service.calculate_grid_convergence(
                request.target_crs, result["x"], result["y"]
            )
            response["scale_factor"] = service.calculate_scale_factor(
                request.target_crs, result["x"], result["y"]
            )
        
        return response
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/trajectory")
async def transform_trajectory(request: TrajectoryRequest):
    """Batch transformation for well trajectories"""
    try:
        service = TransformationService()
        transformed = service.transform_trajectory(
            request.source_crs,
            request.target_crs,
            request.trajectory_points
        )
        
        # Get units
        source_crs = CRS.from_string(request.source_crs)
        target_crs = CRS.from_string(request.target_crs)
        
        return {
            "transformed_trajectory": transformed,
            "units_used": {
                "source": service._get_units(source_crs),
                "target": service._get_units(target_crs)
            },
            "transformation_accuracy": service.get_transformer(
                request.source_crs, request.target_crs
            ).accuracy
        }
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/accuracy")
async def get_transformation_accuracy(source_crs: str, target_crs: str):
    """Get transformation accuracy information"""
    try:
        service = TransformationService()
        transformer = service.get_transformer(source_crs, target_crs)
        
        return {
            "source_crs": source_crs,
            "target_crs": target_crs,
            "horizontal_accuracy": transformer.accuracy,
            "accuracy_unit": "meter",
            "transformation_method": transformer.description,
            "operations": [op.to_proj4() for op in transformer.operations]
        }
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/available-paths")
async def get_available_paths(source_crs: str, target_crs: str):
    """Get all available transformation paths with accuracy"""
    try:
        service = TransformationService()
        paths = service.get_all_transformation_paths(source_crs, target_crs)
        
        return {
            "source_crs": source_crs,
            "target_crs": target_crs,
            "transformation_paths": paths,
            "recommended_path_id": 0 if paths else None
        }
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
```

### Docker Configuration

#### Backend Dockerfile
```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies for PROJ
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Enable PROJ network for grid downloads
ENV PROJ_NETWORK=ON
ENV PROJ_DATA_DIR=/app/proj_data

# Copy application
COPY . .

EXPOSE 3001

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "3001", "--reload"]
```

#### requirements.txt
```
fastapi==0.104.1
uvicorn[standard]==0.24.0
pyproj==3.6.1
redis==5.0.1
pydantic==2.5.0
numpy==1.26.2
python-multipart==0.0.6
```

#### docker-compose.yml
```yaml
version: '3.8'

services:
  backend:
    build: ./backend
    ports:
      - "3001:3001"
    environment:
      - PROJ_NETWORK=ON
      - PYTHONUNBUFFERED=1
    volumes:
      - ./backend:/app
      - proj-data:/app/proj_data
    depends_on:
      - redis
    networks:
      - crs-network

  frontend:
    build: ./frontend
    ports:
      - "3000:3000"
    environment:
      - REACT_APP_API_URL=http://localhost:3001
    volumes:
      - ./frontend:/app
      - /app/node_modules
    depends_on:
      - backend
    networks:
      - crs-network

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    networks:
      - crs-network
    volumes:
      - redis-data:/data

networks:
  crs-network:
    driver: bridge

volumes:
  proj-data:
  redis-data:
```

#### .gitignore
```
# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
env/
venv/
.env

# Node
node_modules/
npm-debug.log
yarn-error.log
.pnp/
.pnp.js

# IDEs
.vscode/
.idea/
*.swp
*.swo

# OS
.DS_Store
Thumbs.db

# Docker
.dockerignore

# Data
proj_data/
*.tif
*.gtx
```

## Implementation Instructions

1. **Create project structure** - Start with all directories and Docker files
2. **Set up backend with PyProj** - Focus on getting basic transformations working first
3. **Implement transformation accuracy** - Use TransformerGroup for all paths
4. **Add unit detection** - Extract from CRS.axis_info
5. **Build custom CRS parser** - XML to PROJ string conversion
6. **Create all API endpoints** - Test each with curl/Postman
7. **Add Redis caching** - Cache transformers and results
8. **Build frontend** - Start simple, add features incrementally
9. **Test with real data** - Use known transformation pairs
10. **Verify Docker setup** - Must work with `docker-compose up --build`

## Success Criteria
- Transformations match commercial software within stated accuracy
- All transformation paths discovered and ranked by accuracy
- Units properly detected for all EPSG codes
- Vertical transformations work correctly
- Custom CRS definitions parsed and matched to EPSG
- Grid convergence and scale factors calculated accurately
- Single command Docker deployment
- Frontend displays all information clearly

## Testing Data
Include these test cases:
- WGS84 to UTM Zone 31N (EPSG:4326 → EPSG:32631)
- ED50 to WGS84 (EPSG:23031 → EPSG:4326)
- NAD83 to WGS84 with vertical (EPSG:4269+5703 → EPSG:4979)
- Custom UTM definition matching to EPSG:32631
