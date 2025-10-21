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
- [ ] POST /api/transform/direct
- [ ] POST /api/transform/via
- [ ] POST /api/transform/custom
- [ ] POST /api/transform/trajectory

### Phase 4: Metadata & Analysis Endpoints
- [ ] GET /api/crs/units/{epsg_code}
- [ ] GET /api/transform/accuracy
- [ ] GET /api/transform/available-paths
- [ ] POST /api/crs/match
- [ ] POST /api/calculate/grid-convergence
- [ ] POST /api/calculate/scale-factor
- [ ] GET /api/crs/search

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

