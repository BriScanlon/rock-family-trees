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
app = FastAPI(title="Rock Family Tree Generator API", version="1.2.1")

# Initialize harvester
harvester = Harvester()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

class SearchResult(BaseModel):
    id: str
    name: str
    type: Optional[str] = None
    disambiguation: Optional[str] = None

@app.get("/ping")
def ping():
    return {"status": "ok"}

class GenerationRequest(BaseModel):
    artist_id: str
    depth: int = 2
    detail_level: int = 5

class JobStatus(BaseModel):
    job_id: str
    status: str
    progress: int
    result_url: Optional[str] = None

# Remove mock database for jobs
# In production, use Redis or a database
# jobs = {}

@app.get("/")
def read_root():
    return {"message": "Welcome to the Rock Family Tree Generator API"}

@app.get("/search", response_model=List[SearchResult])
async def search_artist(q: str):
    print(f"Search request received for: {q}")
    try:
        results = harvester.search_artists(q)
        print(f"Found {len(results)} results")
        return results
    except Exception as e:
        print(f"Search error: {e}")
        return []

@app.get("/search/", response_model=List[SearchResult], include_in_schema=False)
async def search_artist_slash(q: str):
    return await search_artist(q)

@app.post("/generate", response_model=JobStatus)
async def generate_tree(request: GenerationRequest):
    task = process_tree.delay(None, request.artist_id, request.depth)
    return {"job_id": task.id, "status": "Processing", "progress": 0}

@app.get("/status/{job_id}", response_model=JobStatus)
async def get_status(job_id: str):
    try:
        task = process_tree.AsyncResult(job_id)
        # Checking .state can raise ValueError if metadata is corrupted
        try:
            state = task.state
        except (ValueError, KeyError) as e:
            print(f"Metadata error for task {job_id}: {e}")
            return {"job_id": job_id, "status": "Error", "progress": 0}

        if state == 'PENDING':
            return {"job_id": job_id, "status": "Pending", "progress": 0}
        elif task.state == 'PROGRESS':
            progress = 0
            if isinstance(task.info, dict):
                progress = task.info.get('progress', 0)
            return {"job_id": job_id, "status": "Processing", "progress": progress}
        elif task.state == 'SUCCESS':
            # task.result contains the return value of the task
            result = task.result
            if isinstance(result, dict) and result.get('status') == 'Error':
                return {"job_id": job_id, "status": "Error", "progress": 0}
            
            res_url = result.get('result_url') if isinstance(result, dict) else f"/download/{job_id}"
            return {"job_id": job_id, "status": "Completed", "progress": 100, "result_url": res_url}
        elif task.state == 'FAILURE':
            return {"job_id": job_id, "status": "Error", "progress": 0}
        else:
            return {"job_id": job_id, "status": task.state, "progress": 0}
    except Exception as e:
        print(f"Status check error: {e}")
        return {"job_id": job_id, "status": "Error", "progress": 0}

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
