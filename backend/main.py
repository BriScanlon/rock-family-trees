import os
import uuid
from concurrent.futures import ThreadPoolExecutor
from typing import List, Optional

import uvicorn
from dotenv import load_dotenv
from fastapi import APIRouter, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field

load_dotenv()

from app import jobs  # noqa: E402
from app.fixtures import SAMPLES, search_samples  # noqa: E402
from app.musicbrainz import MusicBrainzClient  # noqa: E402
from app.pipeline import ARTIFACT_DIR  # noqa: E402

# "celery" hands jobs to the RabbitMQ worker; "inline" runs them in this process
# so the app works with nothing but `uvicorn main:app`.
TASK_MODE = os.getenv("TASK_MODE", "celery" if os.getenv("RABBITMQ_URL") else "inline")
_executor = ThreadPoolExecutor(max_workers=int(os.getenv("INLINE_WORKERS", "2")))

app = FastAPI(title="Rock Family Tree Generator API", version="2.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
api = APIRouter()


class SearchResult(BaseModel):
    id: str
    name: str
    type: Optional[str] = None
    disambiguation: Optional[str] = None
    country: Optional[str] = None
    years: Optional[str] = None


class GenerationRequest(BaseModel):
    artist_id: str
    depth: int = Field(2, ge=1, le=4)
    max_bands: int = Field(24, ge=1, le=60)
    title: Optional[str] = Field(None, max_length=120)
    subtitle: Optional[str] = Field(None, max_length=200)
    paper: str = Field("auto", pattern="^(auto|A0|A1|A2|A3|A4|none)$")
    hand_drawn: bool = False
    coloured_lines: bool = False
    aged_paper: bool = False
    lettering: str = Field("auto", pattern="^(auto|classic|heavy)$")
    timeline: bool = False
    refresh: bool = False
    detail_level: Optional[int] = None  # accepted for backwards compatibility; unused


class JobStatus(BaseModel):
    job_id: str
    status: str
    progress: int
    message: Optional[str] = None
    result_url: Optional[str] = None
    title: Optional[str] = None
    stats: Optional[dict] = None


@api.get("/ping")
def ping():
    return {"status": "ok", "task_mode": TASK_MODE}


@api.get("/samples")
def samples():
    return [{"id": s["id"], "name": s["name"], "description": s["description"],
             "default_depth": s["default_depth"]} for s in SAMPLES.values()]


@api.get("/search", response_model=List[SearchResult])
def search_artist(q: str):
    q = q.strip()
    if not q:
        return []
    results = search_samples(q)
    try:
        results += MusicBrainzClient().search_artists(q)
    except Exception as e:  # network down, rate limited, etc.
        print(f"Search error: {e}")
        if not results:
            return JSONResponse(status_code=502, content={"detail": f"MusicBrainz search failed: {e}"})
    return results


@api.post("/generate", response_model=JobStatus)
def generate_tree(request: GenerationRequest):
    job_id = uuid.uuid4().hex
    options = request.model_dump(exclude={"artist_id", "detail_level"})
    jobs.write_status(job_id, status="Pending", progress=0, message="Queued", artist_id=request.artist_id)
    if TASK_MODE == "celery":
        from app.worker import process_tree
        process_tree.delay(job_id, request.artist_id, options)
    else:
        _executor.submit(jobs.run_job, job_id, request.artist_id, options)
    return {"job_id": job_id, "status": "Pending", "progress": 0, "message": "Queued"}


@api.get("/status/{job_id}", response_model=JobStatus)
def get_status(job_id: str):
    status = jobs.read_status(job_id)
    if status is None:
        raise HTTPException(status_code=404, detail="Unknown job")
    fields = {k: v for k, v in status.items() if k in JobStatus.model_fields and v is not None}
    return JobStatus(**{**fields, "job_id": job_id})


def _artifact(job_id, ext):
    safe = "".join(c for c in job_id if c.isalnum() or c in "-_")
    path = os.path.join(ARTIFACT_DIR, f"{safe}.{ext}")
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Result not found")
    return path, safe


@api.get("/download/{job_id}")
def download_result(job_id: str, attachment: bool = False):
    path, safe = _artifact(job_id, "svg")
    return FileResponse(path, media_type="image/svg+xml", filename=f"rock-family-tree-{safe}.svg",
                        content_disposition_type="attachment" if attachment else "inline")


@api.get("/tree/{job_id}")
def tree_data(job_id: str):
    path, _ = _artifact(job_id, "json")
    return FileResponse(path, media_type="application/json")


app.include_router(api)
app.include_router(api, prefix="/api", include_in_schema=False)

# Serve a production build of the frontend if one has been copied in.
_static = os.getenv("FRONTEND_DIST", "static")
if os.path.isdir(_static):
    from fastapi.staticfiles import StaticFiles
    app.mount("/", StaticFiles(directory=_static, html=True), name="frontend")
else:
    @app.get("/")
    def read_root():
        return {"message": "Welcome to the Rock Family Tree Generator API"}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("BACKEND_PORT", 8000)))
