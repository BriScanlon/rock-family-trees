import os

from celery import Celery
from dotenv import load_dotenv

from app.jobs import run_job

load_dotenv()

rabbitmq_url = os.getenv("RABBITMQ_URL", "pyamqp://guest:guest@rftg-rabbitmq//")
celery = Celery("tasks", broker=rabbitmq_url)
celery.conf.update(task_ignore_result=True, worker_prefetch_multiplier=1, task_acks_late=True)


@celery.task(name="process_tree")
def process_tree(job_id, artist_id, options):
    result = run_job(job_id, artist_id, options)
    if result.get("status") != "Error" and not artist_id.startswith("demo:"):
        enrich_family.delay(artist_id, options)  # the rest of the family, for its next poster
    return result


@celery.task(name="enrich_family")
def enrich_family(artist_id, options):
    """Notes and events for every band in the family, read after its poster
    (background: it waits whenever a poster is being made)."""
    from app.content import enrich
    from app.pipeline import Options
    return enrich(artist_id, Options(**(options or {})))
