from celery import Celery
import os
from app.harvester import Harvester
from app.refiner import Refiner
from app.cartographer import Cartographer
from app.artist import Artist

redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
celery = Celery("tasks", broker=redis_url, backend=redis_url)

@celery.task(name="process_tree")
def process_tree(job_id, artist_id, depth):
    # 1. Harvest
    harvester = Harvester()
    raw_data = harvester.fetch_recursive(artist_id, max_depth=depth)
    
    # 2. Refine
    refiner = Refiner()
    graph = refiner.process_raw_data(raw_data)
    refiner.apply_significance_filter()
    
    # 3. Cartography
    cartographer = Cartographer(graph)
    cartographer.calculate_timeline()
    cartographer.assign_swimlanes()
    layout = cartographer.get_coordinates()
    
    # 4. Artist
    artist = Artist(layout, output_path=f"artifacts/{job_id}.svg")
    artist.draw_bands()
    artist.apply_pete_frame_style()
    output_file = artist.save()
    
    return {"status": "Completed", "result_url": f"/download/{job_id}"}
