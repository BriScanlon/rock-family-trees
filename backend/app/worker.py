from celery import Celery
import os
import traceback
from app.harvester import Harvester
from app.refiner import Refiner
from app.cartographer import Cartographer
from app.artist import Artist
from dotenv import load_dotenv

load_dotenv()

# Use RabbitMQ as the broker
rabbitmq_url = os.getenv("RABBITMQ_URL", "pyamqp://guest:guest@rftg-rabbitmq//")
celery = Celery("tasks", broker=rabbitmq_url, backend="rpc://") # RPC backend for results

@celery.task(bind=True, name="process_tree")
def process_tree(self, job_id, artist_id, depth):
    task_id = self.request.id
    try:
        os.makedirs("artifacts", exist_ok=True)
        print(f"Task {task_id}: Starting Graph-Aware Harvest (Artist: {artist_id}, Depth: {depth})")
        
        # 1. Harvest & Sync to Neo4j
        self.update_state(state='PROGRESS', meta={'progress': 10})
        harvester = Harvester()
        graph_data = harvester.fetch_recursive(artist_id, max_depth=depth)
        
        # 2. Refine (from Subgraph)
        print(f"Task {task_id}: Refining graph data")
        self.update_state(state='PROGRESS', meta={'progress': 40})
        refiner = Refiner()
        graph_obj = refiner.process_graph_data(graph_data)
        
        # Serialize for layout
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
        return {"status": "Error", "progress": 0, "message": str(e)}
