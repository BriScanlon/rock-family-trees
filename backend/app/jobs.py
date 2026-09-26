"""Job status kept as small JSON files next to the artifacts, so the API and
the Celery worker (separate containers sharing a volume) agree on progress
without depending on a Celery result backend."""
import json
import os
import time
import traceback

from app.pipeline import ARTIFACT_DIR, generate


def _path(job_id):
    safe = "".join(c for c in job_id if c.isalnum() or c in "-_")
    return os.path.join(ARTIFACT_DIR, f"{safe}.status.json")


def write_status(job_id, **fields):
    os.makedirs(ARTIFACT_DIR, exist_ok=True)
    current = read_status(job_id) or {"job_id": job_id, "created": time.time()}
    current.update(fields, updated=time.time())
    tmp = _path(job_id) + ".tmp"
    with open(tmp, "w") as f:
        json.dump(current, f)
    os.replace(tmp, _path(job_id))
    return current


def read_status(job_id):
    try:
        with open(_path(job_id)) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def run_job(job_id, artist_id, options):
    write_status(job_id, status="Processing", progress=1, message="Starting")
    try:
        result = generate(
            artist_id, job_id, options,
            progress=lambda pct, msg: write_status(job_id, status="Processing", progress=pct, message=msg),
        )
        write_status(job_id, status="Completed", progress=100, message="Done", **result)
        return result
    except Exception as e:
        traceback.print_exc()
        write_status(job_id, status="Error", progress=0, message=str(e) or e.__class__.__name__)
        return {"status": "Error", "message": str(e)}
