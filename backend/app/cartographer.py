from typing import List, Dict, Optional
import math

class Cartographer:
    def __init__(self, graph, root_artist_id=None):
        self.graph = graph
        self.root_artist_id = root_artist_id
        
        # A4 Grid Settings
        self.CANVAS_WIDTH = 2480
        self.GRID_COLS = 5
        self.COL_WIDTH = self.CANVAS_WIDTH // self.GRID_COLS
        self.ROW_HEIGHT = 300
        self.MEMBER_WIDTH = 90 # Tighter packing for A4 columns
        
        self.layout = {"versions": {}, "members": [], "edges": []}

    def calculate_timeline(self):
        bands = self.graph.get("bands", {})
        if not bands: return

        # 1. Flatten into Versions
        all_versions = []
        for b_id, band in bands.items():
            lineups = band.get('lineups', [])
            band_name = band.get('name', 'Unknown')
            
            for lineup in lineups:
                s_yr = lineup.get('start_year') or 1970
                e_yr = lineup.get('end_year') or s_yr
                
                version_id = f"{b_id}_{lineup['number']}"
                all_versions.append({
                    "id": version_id,
                    "band_id": b_id,
                    "band_name": band_name,
                    "number": lineup['number'],
                    "start_year": s_yr,
                    "end_year": e_yr,
                    "members": lineup.get('members', [])
                })

        # 2. Sort by Year
        all_versions.sort(key=lambda v: (v['start_year'], v['band_name']))

        # 3. Grid Assignment
        for idx, v in enumerate(all_versions):
            col = idx % self.GRID_COLS
            row = idx // self.GRID_COLS
            
            v_x = col * self.COL_WIDTH + 20 # Left Padding
            v_y = row * self.ROW_HEIGHT + 20 # Top Padding
            v_width = self.COL_WIDTH - 40
            
            beam_y = v_y + 60 # Header space
            
            self.layout["versions"][v['id']] = {
                "id": v['id'],
                "band_name": v['band_name'].upper(),
                "sublabel": f"#{v['number']} ({int(v['start_year'])} - {int(v['end_year'])})",
                "x": v_x,
                "y": v_y,
                "width": v_width,
                "beam_y": beam_y
            }
            
            # 4. Place Members (Left Aligned)
            for m_idx, m in enumerate(v['members']):
                # Wrap members if too many? For now, linear horizontal.
                m_x = v_x + (m_idx * self.MEMBER_WIDTH)
                m_y = beam_y + 20 # Drop down from beam
                
                self.layout["members"].append({
                    "id": f"{v['id']}_{m['artist_id']}",
                    "artist_id": m['artist_id'],
                    "version_id": v['id'],
                    "band_id": v['band_id'],
                    "name": m['artist_name'],
                    "role": m.get('role', ''),
                    "x": m_x,
                    "y": m_y,
                    "beam_y": beam_y
                })

        self.CANVAS_HEIGHT = ((len(all_versions) // self.GRID_COLS) + 1) * self.ROW_HEIGHT

    def route_edges(self):
        # 1. Map Artist History
        artist_history = {}
        for m in self.layout["members"]:
            aid = m['artist_id']
            if aid not in artist_history: artist_history[aid] = []
            artist_history[aid].append(m)
            
        for aid, history in artist_history.items():
            # Ensure strictly chronological order by row/index essentially
            # (Assuming self.layout['members'] creation order roughly follows sort)
            # Better to sort by Y coordinate
            history.sort(key=lambda m: (m['y'], m['x']))
            
            for i in range(len(history) - 1):
                m1 = history[i]
                m2 = history[i+1]
                
                y_start = m1['y'] + 30 # Bottom of text
                y_end = m2['beam_y']
                
                if m1['band_id'] == m2['band_id']:
                    # Continuity
                    self.layout["edges"].append({
                        "type": "continuity",
                        "x1": m1['x'], "y1": y_start,
                        "x2": m2['x'], "y2": y_end
                    })
                else:
                    # Migration
                    role_str = m2.get('role') or ""
                    role_clean = role_str.split(',')[0]
                    self.layout["edges"].append({
                        "type": "migration",
                        "x1": m1['x'], "y1": y_start,
                        "x2": m2['x'], "y2": y_end,
                        "note": f"To {role_clean}" if role_clean else "Joined"
                    })

    def get_coordinates(self):
        return self.layout