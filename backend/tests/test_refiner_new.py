import unittest
from app.refiner import Refiner

class TestRefinerNew(unittest.TestCase):
    def test_process_graph_data(self):
        # Mock data as if returned by Neo4jClient.get_subgraph
        mock_graph_data = {
            "bands": {
                "band-1": {
                    "id": "band-1",
                    "name": "The Testers",
                    "start_year": 1990,
                    "end_year": 2000,
                    "all_members": [
                        {
                            "artist_id": "a1",
                            "artist_name": "Alice",
                            "role": "Vocals",
                            "start_year": 1990,
                            "end_year": 1995,
                            "position": 0
                        },
                        {
                            "artist_id": "a2",
                            "artist_name": "Bob",
                            "role": "Guitar",
                            "start_year": 1990,
                            "end_year": 2000,
                            "position": 1
                        },
                        {
                            "artist_id": "a3",
                            "artist_name": "Charlie",
                            "role": "Vocals",
                            "start_year": 1995,
                            "end_year": 2000,
                            "position": 0
                        }
                    ]
                }
            }
        }

        refiner = Refiner()
        result = refiner.process_graph_data(mock_graph_data)
        
        self.assertIsNotNone(result)
        self.assertIn("bands", result)
        self.assertIn("band-1", result["bands"])
        
        band = result["bands"]["band-1"]
        self.assertEqual(band.name, "The Testers")
        self.assertEqual(len(band.all_members), 3)
        
        # Check Lineups
        # Expected:
        # Lineup 1: 1990-1995 (Alice, Bob)
        # Lineup 2: 1995-2000 (Bob, Charlie)
        # Depending on how logic handles exact boundary years.
        # Refiner logic:
        # years = {1990, 1995, 2000} -> sorted [1990, 1995, 2000]
        # Intervals:
        # 1. 1990-1995. Mid=1992.5. Alice(1990-1995) includes 1992.5? Yes. Bob(1990-2000) yes.
        # 2. 1995-2000. Mid=1997.5. Alice(1990-1995) no. Bob yes. Charlie(1995-2000) yes.
        
        self.assertTrue(len(band.lineups) >= 2, f"Expected at least 2 lineups, got {len(band.lineups)}")
        
        l1 = band.lineups[0]
        l1_names = sorted([m.artist_name for m in l1.members])
        self.assertEqual(l1_names, ["Alice", "Bob"])
        
        l2 = band.lineups[1]
        l2_names = sorted([m.artist_name for m in l2.members])
        self.assertEqual(l2_names, ["Bob", "Charlie"])

if __name__ == "__main__":
    unittest.main()
