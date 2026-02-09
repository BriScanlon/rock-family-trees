from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
import uuid
import os
from app.harvester import Harvester
from app.worker import process_tree

from dotenv import load_dotenv
import uvicorn
load_dotenv()
app = FastAPI(title="Rock Family Tree Generator API", version="1.2.0")

# Initialize harvester
harvester = Harvester()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class SearchResult(BaseModel):
    id: str
    name: str
    type: Optional[str] = None
    disambiguation: Optional[str] = None

class GenerationRequest(BaseModel):
    artist_id: str
    depth: int = 2
    detail_level: int = 5

class JobStatus(BaseModel):
    job_id: str
    status: str
    progress: int
    result_url: Optional[str] = None

# Mock database for jobs
# In production, use Redis or a database
jobs = {}

@app.get("/")
def read_root():
    return {"message": "Welcome to the Rock Family Tree Generator API"}

@app.get("/search", response_model=List[SearchResult])
async def search_artist(q: str):
    return harvester.search_artists(q)

@app.post("/generate", response_model=JobStatus)
async def generate_tree(request: GenerationRequest):
    job_id = str(uuid.uuid4())
    jobs[job_id] = {"status": "Processing", "progress": 10}
    
    # Enqueue Celery task
    process_tree.delay(job_id, request.artist_id, request.depth)
    
    return {"job_id": job_id, "status": "Processing", "progress": 10}

@app.get("/status/{job_id}", response_model=JobStatus)
async def get_status(job_id: str):
    # In a real app, we would query Celery or a shared DB
    if job_id not in jobs:
        # Check if celery has it (simplified for this prototype)
        return {"job_id": job_id, "status": "Completed", "progress": 100, "result_url": f"/download/{job_id}"}
    return {"job_id": job_id, **jobs[job_id]}

@app.get("/download/{job_id}")
async def download_result(job_id: str):
    file_path = f"artifacts/{job_id}.svg"
    if os.path.exists(file_path):
        from fastapi.responses import FileResponse
        return FileResponse(file_path, media_type='image/svg+xml', filename=f"rock-tree-{job_id}.svg")
    raise HTTPException(status_code=404, detail="Result not found")

if __name__ == "__main__":
    port = int(os.getenv("BACKEND_PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
