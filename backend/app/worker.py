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
    return run_job(job_id, artist_id, options)
