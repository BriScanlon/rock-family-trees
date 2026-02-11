import unittest
from unittest.mock import MagicMock, patch
import sys
import os

# Add app to path if not already there
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from app.harvester import Harvester

class TestHarvesterLogic(unittest.TestCase):
    def setUp(self):
        # Patch musicbrainzngs
        self.mb_patcher = patch('app.harvester.musicbrainzngs')
        self.mock_mb = self.mb_patcher.start()
        
        # Patch Neo4jClient
        self.neo_patcher = patch('app.harvester.Neo4jClient')
        self.mock_neo_cls = self.neo_patcher.start()
        self.mock_db = self.mock_neo_cls.return_value
        
        self.harvester = Harvester()

    def tearDown(self):
        self.mb_patcher.stop()
        self.neo_patcher.stop()

    def test_fetch_recursive_cache_hit(self):
        # Scenario: Database already has depth >= required
        mbid = "band-123"
        required_depth = 2
        
        # Setup mock DB to return sufficient depth
        self.mock_db.get_explored_depth.return_value = 3
        
        # Setup mock DB to return a subgraph
        expected_subgraph = {"bands": {"band-123": {}}}
        self.mock_db.get_subgraph.return_value = expected_subgraph
        
        # Call fetch_recursive
        result = self.harvester.fetch_recursive(mbid, max_depth=required_depth)
        
        # Verify:
        # 1. get_explored_depth called
        self.mock_db.get_explored_depth.assert_called_with(mbid)
        # 2. _expand_recursive NOT called (because 3 >= 2)
        # We can't easily check internal method calls unless we spy on self.harvester,
        # but we can check if MB API was called.
        self.mock_mb.get_artist_by_id.assert_not_called()
        # 3. get_subgraph called
        self.mock_db.get_subgraph.assert_called_with(mbid, required_depth)
        # 4. Result matches
        self.assertEqual(result, expected_subgraph)

    def test_fetch_recursive_cache_miss(self):
        # Scenario: Database has insufficient depth
        mbid = "band-456"
        required_depth = 2
        
        # Setup mock DB
        self.mock_db.get_explored_depth.return_value = 1 # Too shallow
        self.mock_db.get_subgraph.return_value = {"bands": {}}
        
        # Setup mock MB API response for initial expansion
        # band-456 -> member-1 (Alice) -> member-of -> band-789
        
        # Mocking specific calls is tricky with the recursive loop, 
        # let's just ensure it calls get_artist_by_id at least once.
        self.mock_mb.get_artist_by_id.return_value = {
            'artist': {
                'id': 'band-456',
                'name': 'The Testers',
                'type': 'Group',
                'artist-relation-list': []
            }
        }
        
        self.harvester.fetch_recursive(mbid, max_depth=required_depth)
        
        # Verify:
        # 1. get_artist_by_id WAS called (expansion happened)
        self.assertTrue(self.mock_mb.get_artist_by_id.called)
        # 2. set_explored_depth WAS called with new depth
        self.mock_db.set_explored_depth.assert_called_with(mbid, required_depth)

    def test_sync_artist_to_neo4j(self):
        mbid = "band-xyz"
        
        # Mock MB response
        self.mock_mb.get_artist_by_id.return_value = {
            'artist': {
                'id': mbid,
                'name': 'XYZ Band',
                'type': 'Group',
                'life-span': {'begin': '1990', 'end': '2000'},
                'artist-relation-list': [
                    {
                        'type': 'member of band',
                        'begin': '1990',
                        'end': '1995',
                        'attributes': ['original'],
                        'artist': {'id': 'mem-1', 'name': 'Member One'}
                    }
                ]
            }
        }
        
        self.harvester.sync_artist_to_neo4j(mbid)
        
        # Verify DB calls
        self.mock_db.upsert_band.assert_called_with(mbid, 'XYZ Band', 1990, 2000)
        self.mock_db.upsert_membership.assert_called()
        
        # Check args for membership
        args, _ = self.mock_db.upsert_membership.call_args
        # args: artist_mbid, artist_name, band_mbid, rel_data
        self.assertEqual(args[0], 'mem-1')
        self.assertEqual(args[1], 'Member One')
        self.assertEqual(args[2], mbid)
        self.assertEqual(args[3]['role'], 'original')

if __name__ == '__main__':
    unittest.main()
