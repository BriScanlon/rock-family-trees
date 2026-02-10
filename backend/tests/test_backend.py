import sys
import os
import unittest

# Add app to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from app.harvester import Harvester
from app.refiner import Refiner
from app.cartographer import Cartographer
from app.artist import Artist

class TestBackend(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.harvester = Harvester(cache_path="cache/test_cache.sqlite")
        cls.joy_division_mbid = "9a58fda3-f4ed-4080-a3a5-f457aac9fcdd"

    def test_refiner_lineups(self):
        print("\nTesting Lineup Detection...")
        raw_data = self.harvester.fetch_recursive(self.joy_division_mbid, max_depth=1)
        refiner = Refiner()
        graph = refiner.process_raw_data(raw_data)
        
        # Joy Division should have at least one lineup
        jd = graph["bands"][self.joy_division_mbid]
        self.assertTrue(len(jd.lineups) > 0)
        print(f"Detected {len(jd.lineups)} lineups for Joy Division")
        for l in jd.lineups:
            print(f"  Lineup #{l.number}: {l.start_year}-{l.end_year} ({len(l.members)} members)")

    def test_full_generation_flow(self):
        print("\nTesting Full Generation Flow...")
        raw_data = self.harvester.fetch_recursive(self.joy_division_mbid, max_depth=1)
        refiner = Refiner()
        graph_obj = refiner.process_raw_data(raw_data)
        
        # Serialize
        graph = {
            "bands": {
                mbid: band.model_dump() 
                for mbid, band in graph_obj["bands"].items()
            }
        }
        
        cartographer = Cartographer(graph)
        cartographer.calculate_timeline()
        cartographer.route_edges()
        layout = cartographer.get_coordinates()
        
        artist = Artist(layout, output_path="artifacts/test_pete_frame.svg")
        artist.draw_lineups()
        artist.save()
        
        self.assertTrue(os.path.exists("artifacts/test_pete_frame.svg"))
        print("Pete Frame style SVG generated successfully")

if __name__ == '__main__':
    unittest.main()
