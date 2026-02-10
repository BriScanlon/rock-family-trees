from celery import Celery
import os
import traceback
from app.harvester import Harvester
from app.refiner import Refiner
from app.cartographer import Cartographer
from app.artist import Artist
from dotenv import load_dotenv

load_dotenv()

redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
celery = Celery("tasks", broker=redis_url, backend=redis_url)

@celery.task(bind=True, name="process_tree")
def process_tree(self, job_id, artist_id, depth):
    # Standard task execution with NO complex Pydantic objects returned
    task_id = self.request.id
    try:
        os.makedirs("artifacts", exist_ok=True)
        print(f"Task {task_id}: Starting Harvest (Artist: {artist_id}, Depth: {depth})")
        
        # 1. Harvest
        self.update_state(state='PROGRESS', meta={'progress': 10})
        harvester = Harvester()
        raw_data = harvester.fetch_recursive(artist_id, max_depth=depth)
        
        # 2. Refine
        print(f"Task {task_id}: Refining {len(raw_data)} records")
        self.update_state(state='PROGRESS', meta={'progress': 40})
        refiner = Refiner()
        graph_obj = refiner.process_raw_data(raw_data)
        
        # Manually serialize the graph to avoid Pydantic issues in Cartographer/Artist
        graph = {
            "bands": {
                mbid: band.model_dump() 
                for mbid, band in graph_obj["bands"].items()
            }
        }
        
        # 3. Cartography
        print(f"Task {task_id}: Calculating Layout")
        self.update_state(state='PROGRESS', meta={'progress': 70})
        cartographer = Cartographer(graph)
        cartographer.calculate_timeline()
        cartographer.route_edges()
        layout = cartographer.get_coordinates()
        
        # 4. Artist
        print(f"Task {task_id}: Rendering SVG")
        self.update_state(state='PROGRESS', meta={'progress': 90})
        artist = Artist(layout, output_path=f"artifacts/{task_id}.svg")
        artist.draw_all()
        artist.save()
        
        print(f"Task {task_id}: Success")
        return {"status": "Completed", "progress": 100, "result_url": f"/download/{task_id}"}

    except Exception as e:
        print(f"Task {task_id}: FAILED -> {str(e)}")
        traceback.print_exc()
        # Return serializable error info
        return {"status": "Error", "progress": 0, "message": str(e)}