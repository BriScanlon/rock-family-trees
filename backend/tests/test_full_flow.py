import unittest
import os
import shutil
from app.refiner import Refiner
from app.cartographer import Cartographer
from app.artist import Artist

class TestFullFlow(unittest.TestCase):
    def setUp(self):
        # Create artifacts directory for test
        os.makedirs("artifacts_test", exist_ok=True)
        
    def tearDown(self):
        # Cleanup
        if os.path.exists("artifacts_test"):
            shutil.rmtree("artifacts_test")

    def test_full_generation_flow_joy_division(self):
        print("\nTesting Full Generation Flow (Joy Division -> New Order)...")
        
        # 1. Mock Graph Data (as returned by Neo4jClient.get_subgraph)
        graph_data = {
            "bands": {
                "mbid-jd": {
                    "id": "mbid-jd",
                    "name": "Joy Division",
                    "start_year": 1976,
                    "end_year": 1980,
                    "all_members": [
                        {"artist_id": "Ian", "artist_name": "Ian Curtis", "role": "Vocals", "start_year": 1976, "end_year": 1980, "position": 0},
                        {"artist_id": "Bernard", "artist_name": "Bernard Sumner", "role": "Guitar", "start_year": 1976, "end_year": 1980, "position": 1},
                        {"artist_id": "Hooky", "artist_name": "Peter Hook", "role": "Bass", "start_year": 1976, "end_year": 1980, "position": 2},
                        {"artist_id": "Steve", "artist_name": "Stephen Morris", "role": "Drums", "start_year": 1976, "end_year": 1980, "position": 3}
                    ]
                },
                "mbid-no": {
                    "id": "mbid-no",
                    "name": "New Order",
                    "start_year": 1980,
                    "end_year": 2023,
                    "all_members": [
                        {"artist_id": "Bernard", "artist_name": "Bernard Sumner", "role": "Vocals/Guitar", "start_year": 1980, "end_year": 2023, "position": 0},
                        {"artist_id": "Hooky", "artist_name": "Peter Hook", "role": "Bass", "start_year": 1980, "end_year": 2007, "position": 1},
                        {"artist_id": "Steve", "artist_name": "Stephen Morris", "role": "Drums", "start_year": 1980, "end_year": 2023, "position": 2},
                        {"artist_id": "Gillian", "artist_name": "Gillian Gilbert", "role": "Keys", "start_year": 1980, "end_year": 2001, "position": 3},
                        {"artist_id": "Gillian", "artist_name": "Gillian Gilbert", "role": "Keys", "start_year": 2011, "end_year": 2023, "position": 3}
                    ]
                }
            }
        }
        
        # 2. Refine
        refiner = Refiner()
        graph_obj = refiner.process_graph_data(graph_data)
        
        self.assertIn("mbid-jd", graph_obj["bands"])
        self.assertIn("mbid-no", graph_obj["bands"])
        
        # 3. Serialize for Cartographer
        graph = {
            "bands": {
                mbid: band.model_dump() 
                for mbid, band in graph_obj["bands"].items()
            }
        }
        
        # 4. Cartographer
        cartographer = Cartographer(graph)
        cartographer.calculate_timeline()
        cartographer.route_edges()
        layout = cartographer.get_coordinates()
        
        # Verify basic layout properties
        self.assertIn("versions", layout)
        # Check that we have versions derived from our bands
        # Keys are now composite, e.g. "mbid-jd_1"
        self.assertTrue(any("mbid-jd" in k for k in layout["versions"]), "Should contain Joy Division versions")
        self.assertTrue(any("mbid-no" in k for k in layout["versions"]), "Should contain New Order versions")
        
        # 5. Artist (SVG Generation)
        output_path = "artifacts_test/test_flow.svg"
        artist = Artist(layout, output_path=output_path)
        artist.draw_all()
        artist.save()
        
        self.assertTrue(os.path.exists(output_path), "SVG file should be generated")
        file_size = os.path.getsize(output_path)
        self.assertGreater(file_size, 100, "SVG file should not be empty")
        print(f"SVG generated successfully: {output_path} ({file_size} bytes)")

if __name__ == "__main__":
    unittest.main()
