from __future__ import annotations

from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.routes import router as api_router

app = FastAPI(
    title="ChemMat Studio",
    description="One-stop Chemistry & Materials Science Experimental Data Processing Workbench",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)

FRONTEND_DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"
if (FRONTEND_DIST / "assets").exists():
    app.mount("/assets", StaticFiles(directory=str(FRONTEND_DIST / "assets")), name="assets")


@app.get("/{full_path:path}")
def serve_spa(full_path: str) -> FileResponse:
    if full_path.startswith("api"):
        raise HTTPException(status_code=404, detail="API endpoint not found")
    if FRONTEND_DIST.exists():
        target = FRONTEND_DIST / full_path
        if full_path and target.exists() and target.is_file():
            return FileResponse(str(target))
        index_file = FRONTEND_DIST / "index.html"
        if index_file.exists():
            return FileResponse(str(index_file))
    raise HTTPException(status_code=404, detail="Frontend bundle not built yet (run npm run build in frontend/).")
