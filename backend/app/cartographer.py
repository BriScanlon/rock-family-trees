from typing import List, Dict, Set
import math

class Cartographer:
    def __init__(self, graph):
        self.graph = graph
        self.layout = {"bands": {}, "edges": [], "members": []}
        self.YEAR_SCALE = 200 # Increased for readability
        self.MEMBER_WIDTH = 250 # Increased for readability
        self.BAND_SPACING_X = 150
        self.LANE_PADDING = 60
        self.MIN_MARGIN_Y = 300

    def calculate_timeline(self):
        bands_data = self.graph.get("bands", {})
        if not bands_data: return

        all_years = []
        band_ranges = []
        for b_id, b in bands_data.items():
            s_yr = b.get('start_year')
            e_yr = b.get('end_year')
            
            # Fallback for years if missing
            lineups = b.get('lineups', [])
            l_years = []
            for l in lineups:
                if l.get('start_year'): l_years.append(l.get('start_year'))
                if l.get('end_year'): l_years.append(l.get('end_year'))
            
            if not s_yr and l_years: s_yr = min(l_years)
            if not e_yr and l_years: e_yr = max(l_years)
            
            s_yr = s_yr or 1960
            e_yr = e_yr or (s_yr + 5)
            
            all_years.extend([s_yr, e_yr])
            band_ranges.append({
                'id': b_id,
                'start': s_yr,
                'end': e_yr,
                'max_members': max([len(l.get('members', [])) for l in lineups] or [1])
            })
        
        self.min_year = min(all_years) if all_years else 1960
        
        # Sort bands by start year
        band_ranges.sort(key=lambda x: x['start'])
        
        # 1. Lane Assignment (Packing bands into columns to save width)
        lanes = [] # List of lists of band_ranges
        for br in band_ranges:
            placed = False
            for lane in lanes:
                # Check if br overlaps with any band already in this lane
                # We add a small buffer (1 year) to prevent touching
                overlap = False
                for existing in lane:
                    if not (br['end'] + 1 < existing['start'] or existing['end'] + 1 < br['start']):
                        overlap = True
                        break
                if not overlap:
                    lane.append(br)
                    placed = True
                    break
            if not placed:
                lanes.append([br])

        # Calculate width for each lane
        lane_widths = []
        for lane in lanes:
            max_m = max(br['max_members'] for br in lane)
            lane_widths.append(max_m * self.MEMBER_WIDTH + (self.LANE_PADDING * 2))

        # 2. Assign Coordinates
        current_x = 200
        for lane_idx, lane in enumerate(lanes):
            lane_width = lane_widths[lane_idx]
            
            for br in lane:
                b_id = br['id']
                band = bands_data[b_id]
                
                b_y_start = (br['start'] - self.min_year) * self.YEAR_SCALE + self.MIN_MARGIN_Y
                
                self.layout["bands"][b_id] = {
                    "id": b_id,
                    "name": band['name'],
                    "x": current_x,
                    "width": lane_width,
                    "start_year": br['start'],
                    "y": b_y_start
                }
                
                # Assign columns for members
                member_cols = {}
                next_col = 0
                lineups = band.get('lineups', [])
                
                for l_idx, lineup in enumerate(lineups):
                    s_yr = lineup.get('start_year') or br['start']
                    e_yr = lineup.get('end_year') or (s_yr + 1)
                    y = (s_yr - self.min_year) * self.YEAR_SCALE + self.MIN_MARGIN_Y + 50
                    
                    active_member_ids = [m['artist_id'] for m in lineup['members']]
                    current_lineup_cols = {}
                    
                    # Carry over columns
                    for m in lineup['members']:
                        if m['artist_id'] in member_cols:
                            current_lineup_cols[m['artist_id']] = member_cols[m['artist_id']]
                    
                    # Assign new columns or reuse vacated ones
                    vacated_cols = []
                    if l_idx > 0:
                        prev_lineup = lineups[l_idx-1]
                        for pm in prev_lineup['members']:
                            if pm['artist_id'] not in active_member_ids:
                                vacated_cols.append(member_cols[pm['artist_id']])
                    vacated_cols.sort()
                    
                    for m in lineup['members']:
                        if m['artist_id'] not in current_lineup_cols:
                            if vacated_cols:
                                col = vacated_cols.pop(0)
                            else:
                                col = next_col
                                next_col += 1
                            member_cols[m['artist_id']] = col
                            current_lineup_cols[m['artist_id']] = col
                            # Mark replacements
                            if l_idx > 0:
                                # Find who was in this col in prev lineup
                                for pm in lineups[l_idx-1]['members']:
                                    if member_cols[pm['artist_id']] == col:
                                        m['is_replacement'] = True
                                        m['replaced_from'] = pm['artist_name']
                                        break

                    # Layout members
                    for m in lineup['members']:
                        col = current_lineup_cols[m['artist_id']]
                        m_x = current_x + self.LANE_PADDING + (col * self.MEMBER_WIDTH)
                        
                        self.layout["members"].append({
                            "id": f"{b_id}_{lineup['number']}_{m['artist_id']}",
                            "artist_id": m['artist_id'],
                            "band_id": b_id,
                            "lineup_num": lineup['number'],
                            "name": m['artist_name'],
                            "role": m.get('role', ''),
                            "x": m_x,
                            "y": y,
                            "start_year": s_yr,
                            "end_year": e_yr,
                            "is_replacement": m.get('is_replacement', False),
                            "replaced_from": m.get('replaced_from')
                        })
                    
                    # Lineup metadata
                    self.layout["bands"][b_id][f"lineup_{lineup['number']}"] = {
                        "y": y,
                        "x_start": current_x + self.LANE_PADDING,
                        "x_end": current_x + lane_width - self.LANE_PADDING
                    }
                    
            current_x += lane_width + self.BAND_SPACING_X

    def route_edges(self):
        # Vertical Continuity Lines
        members_by_artist_band = {}
        for m in self.layout["members"]:
            key = (m['artist_id'], m['band_id'])
            if key not in members_by_artist_band: members_by_artist_band[key] = []
            members_by_artist_band[key].append(m)
        
        for apps in members_by_artist_band.values():
            apps.sort(key=lambda x: x['start_year'])
            for i in range(len(apps) - 1):
                m1, m2 = apps[i], apps[i+1]
                if m1['x'] == m2['x']:
                    self.layout["edges"].append({
                        "type": "continuity",
                        "x": m1['x'],
                        "y1": m1['y'] + 20,
                        "y2": m2['y'] - 10
                    })

        # Migration Lines
        artist_apps = {}
        for m in self.layout["members"]:
            a_id = m['artist_id']
            if a_id not in artist_apps: artist_apps[a_id] = []
            artist_apps[a_id].append(m)
            
        for apps in artist_apps.values():
            apps.sort(key=lambda x: x['start_year'])
            for i in range(len(apps) - 1):
                m1, m2 = apps[i], apps[i+1]
                if m1['band_id'] != m2['band_id']:
                    self.layout["edges"].append({
                        "type": "migration",
                        "x1": m1['x'], "y1": m1['y'] + 30,
                        "x2": m2['x'], "y2": m2['y'] - 10,
                        "name": m1['name']
                    })

    def get_coordinates(self):
        return self.layout