from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.transform import router as transform_router
from app.api.crs import router as crs_router
from app.api.calculate import router as calc_router
from app.api.gigs import router as gigs_router
from app.api.docs import router as docs_router

app = FastAPI(title="CRS Transformation Platform")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(transform_router)
app.include_router(crs_router)
app.include_router(calc_router)
app.include_router(gigs_router)
app.include_router(docs_router)

@app.get("/")
def root():
    return {"status": "ok", "service": "crs-transformation-platform"}
