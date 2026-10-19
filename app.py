import os
from pathlib import Path

import uvicorn
from fastapi import APIRouter, FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

BASE_DIR = Path(__file__).parent
STATIC_DIR = BASE_DIR / "static"

app = FastAPI(title="Catalog Dashboard")

# ---------- API ----------
api = APIRouter(prefix="/api")


@api.get("/health")
def health():
    return {"status": "ok", "service": "catalog-dashboard"}


app.include_router(api)

# ---------- Serve React build ----------
if (STATIC_DIR / "assets").exists():
    app.mount("/assets", StaticFiles(directory=STATIC_DIR / "assets"), name="assets")


@app.get("/{full_path:path}")
def spa(full_path: str):
    index = STATIC_DIR / "index.html"
    if index.exists():
        return FileResponse(index)
    return {"message": "Frontend not built yet. Run: cd frontend && npm run build"}


if __name__ == "__main__":
    # Databricks Apps provides the port via DATABRICKS_APP_PORT
    port = int(os.getenv("DATABRICKS_APP_PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port)
