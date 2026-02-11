from typing import List, Dict, Optional
import math
import statistics

class Cartographer:
    def __init__(self, graph, root_artist_id=None):
        self.graph = graph
        self.root_artist_id = root_artist_id
        
        # Global Settings
        self.MEMBER_WIDTH = 120
        self.YEAR_HEIGHT = 150
        self.HEADER_HEIGHT = 60
        self.TICK_HEIGHT = 20
        self.TEXT_STACK_HEIGHT = 50
        self.X_PADDING = 50 # Minimum gap between version boxes
        self.Y_PADDING = 50  # Minimum vertical gap if years overlap perfectly
        
        self.layout = {"versions": {}, "members": [], "edges": []}
        self.placed_boxes = [] # List of {x, y, w, h} for collision detection

    def _get_year_y(self, year):
        return (year - self.min_year) * self.YEAR_HEIGHT + 100

    def _check_collision(self, x, y, w, h):
        margin = 20
        for box in self.placed_boxes:
            # box is (bx, by, bw, bh)
            # Check overlap
            if not (x + w + margin < box['x'] or \
                    x > box['x'] + box['w'] + margin or \
                    y + h + margin < box['y'] or \
                    y > box['y'] + box['h'] + margin):
                return True
        return False

    def calculate_timeline(self):
        bands = self.graph.get("bands", {})
        if not bands: return

        # 1. Flatten into "Versions" (Lineups)
        all_versions = []
        all_years = []

        for b_id, band in bands.items():
            lineups = band.get('lineups', [])
            band_name = band.get('name', 'Unknown')
            
            for lineup in lineups:
                s_yr = lineup.get('start_year')
                e_yr = lineup.get('end_year')
                if not s_yr and not e_yr: s_yr = 1970 # Fallback
                s_yr = s_yr or e_yr or 1970
                e_yr = e_yr or s_yr # Point in time if single year
                
                all_years.extend([s_yr, e_yr])
                
                # Calculate Version Width
                num_members = len(lineup.get('members', []))
                width = max(num_members * self.MEMBER_WIDTH, 200) # Min width for title
                
                version_id = f"{b_id}_{lineup['number']}"
                
                all_versions.append({
                    "id": version_id,
                    "band_id": b_id,
                    "band_name": band_name,
                    "number": lineup['number'],
                    "start_year": s_yr,
                    "end_year": e_yr,
                    "width": width,
                    "members": lineup.get('members', [])
                })

        if not all_years: return
        self.min_year = min(all_years)
        
        # 2. Sort Versions
        # Sort by Start Year, then by Band Name (to keep bands together if same year)
        all_versions.sort(key=lambda v: (v['start_year'], v['band_name']))

        # 3. Place Versions (Clustering & Collision)
        # We need a map to track where the previous version of a band was placed
        band_x_history = {} 
        
        center_x = 1240 # Middle of A4

        for v in all_versions:
            v_height = self.HEADER_HEIGHT + self.TICK_HEIGHT + self.TEXT_STACK_HEIGHT + 20
            v_y = self._get_year_y(v['start_year'])
            
            # Determine Target X
            target_x = center_x
            
            # Heuristic A: Previous Lineup of same band
            if v['band_id'] in band_x_history:
                target_x = band_x_history[v['band_id']]
            else:
                # Heuristic B: Connectivity (Where did members come from?)
                # This is complex to query efficiently here without pre-processing edges.
                # For now, default to Center, or slightly offset based on hash to avoid stacking?
                # Let's just use Center and let collision resolution spread them out.
                pass

            # Collision Resolution (Spiral/Alternating Search)
            # Try target_x, then target_x + 200, target_x - 200, etc.
            placed = False
            shift = 0
            steps = 0
            
            while not placed and steps < 100:
                test_x = target_x + shift
                
                # Center the box on test_x
                box_left = test_x - (v['width'] / 2)
                
                if not self._check_collision(box_left, v_y, v['width'], v_height):
                    # Found a spot!
                    v['x'] = test_x
                    v['y'] = v_y
                    v['box_left'] = box_left
                    v['box_height'] = v_height
                    
                    self.placed_boxes.append({
                        'x': box_left, 'y': v_y, 
                        'w': v['width'], 'h': v_height
                    })
                    placed = True
                    
                    # Update history
                    band_x_history[v['band_id']] = test_x
                else:
                    # Increment shift (alternating)
                    steps += 1
                    dist = (steps + 1) // 2 * (v['width'] + self.X_PADDING)
                    shift = dist if steps % 2 != 0 else -dist

            if not placed:
                print(f"Warning: Could not place {v['band_name']} {v['number']}")
                v['x'] = target_x
                v['y'] = v_y
                v['box_left'] = target_x - (v['width'] / 2)

            # 4. Generate Internal Layout Elements
            # Header
            self.layout["versions"][v['id']] = {
                "id": v['id'],
                "band_name": v['band_name'].upper(),
                "sublabel": f"#{v['number']} ({int(v['start_year'])} - {int(v['end_year'])})",
                "x": v['x'],
                "y": v['y'],
                "width": v['width'],
                "beam_y": v['y'] + self.HEADER_HEIGHT
            }

            # Members
            num_m = len(v['members'])
            start_m_x = v['x'] - (num_m * self.MEMBER_WIDTH) / 2 + (self.MEMBER_WIDTH / 2)
            
            for idx, m in enumerate(v['members']):
                m_x = start_m_x + (idx * self.MEMBER_WIDTH)
                m_y = v['y'] + self.HEADER_HEIGHT + self.TICK_HEIGHT
                
                # Member Node
                self.layout["members"].append({
                    "id": f"{v['id']}_{m['artist_id']}",
                    "artist_id": m['artist_id'],
                    "version_id": v['id'],
                    "band_id": v['band_id'],
                    "name": m['artist_name'],
                    "role": m.get('role', ''),
                    "x": m_x,
                    "y": m_y,
                    "beam_y": v['y'] + self.HEADER_HEIGHT # Store for edge routing
                })

    def route_edges(self):
        # Map: ArtistID -> List of MemberNodes (sorted by time)
        artist_history = {}
        for m in self.layout["members"]:
            aid = m['artist_id']
            if aid not in artist_history: artist_history[aid] = []
            artist_history[aid].append(m)
            
        for aid, history in artist_history.items():
            # Sort by Y (Time)
            history.sort(key=lambda m: m['y'])
            
            for i in range(len(history) - 1):
                m1 = history[i]
                m2 = history[i+1]
                
                # Line Logic
                # From m1 Bottom -> m2 Beam Top (or m2 Top?)
                # Prompt: "Vertical Continuity... bottom of text in #1 to top of horizontal beam in #2"
                
                y_start = m1['y'] + 30 # Approx text height
                y_end = m2['beam_y']
                
                if m1['band_id'] == m2['band_id']:
                    # Continuity (Same Band)
                    # If X is same, straight line.
                    # If X differs (position swap), slanted line.
                    self.layout["edges"].append({
                        "type": "continuity",
                        "x1": m1['x'],
                        "y1": y_start,
                        "x2": m2['x'], # Target the member's X on the beam? 
                                       # Prompt says "to top of horizontal beam".
                                       # But visually, connecting to the specific member tick is better.
                                       # I will target m2['x'] at y_end.
                        "y2": y_end
                    })
                else:
                    # Migration (Different Band)
                    # "Vertical down... horizontal elbow... vertical to new band"
                    mid_y = (y_start + y_end) / 2
                    
                    self.layout["edges"].append({
                        "type": "migration",
                        "x1": m1['x'],
                        "y1": y_start,
                        "x2": m2['x'],
                        "y2": y_end,
                        "note": f"Joined {m2['role']}" # Simplified note
                    })

    def get_coordinates(self):
        return self.layout