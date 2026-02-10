from typing import List, Dict, Set
import math

class Cartographer:
    def __init__(self, graph):
        self.graph = graph
        self.layout = {"bands": {}, "edges": [], "members": []}
        self.YEAR_SCALE = 100 # Vertical pixels per year
        self.MEMBER_WIDTH = 150
        self.BAND_SPACING_X = 100
        self.LANE_PADDING = 40

    def calculate_timeline(self):
        bands_data = self.graph.get("bands", {})
        if not bands_data: return

        all_years = []
        for b in bands_data.values():
            if b.get('start_year'): all_years.append(b['start_year'])
            for l in b.get('lineups', []):
                if l.get('start_year'): all_years.append(l['start_year'])
                if l.get('end_year'): all_years.append(l['end_year'])
        
        self.min_year = min(all_years) if all_years else 1960
        
        # 1. Assign X-lanes to bands
        # Sort bands by start year to determine order
        sorted_band_ids = sorted(bands_data.keys(), key=lambda bid: bands_data[bid].get('start_year') or 0)
        
        current_x = 100
        band_lanes = {} # mbid -> {x_start, width}

        for b_id in sorted_band_ids:
            band = bands_data[b_id]
            # Max members in any lineup determines width
            max_members = max([len(l.get('members', [])) for l in band.get('lineups', [])] or [1])
            width = max_members * self.MEMBER_WIDTH + (self.LANE_PADDING * 2)
            
            band_lanes[b_id] = {
                'x_start': current_x,
                'width': width,
                'name': band['name']
            }
            
            # Calculate band-level layout info
            self.layout["bands"][b_id] = {
                "id": b_id,
                "name": band['name'],
                "x": current_x,
                "width": width,
                "start_year": band.get('start_year') or self.min_year,
                "y": ( (band.get('start_year') or self.min_year) - self.min_year) * self.YEAR_SCALE + 150
            }
            
            # 2. Assign columns to members within the band
            member_cols = {} # artist_id -> column_index
            next_col = 0
            
            lineups = band.get('lineups', [])
            for l_idx, lineup in enumerate(lineups):
                s_yr = lineup.get('start_year') or self.min_year
                e_yr = lineup.get('end_year') or (s_yr + 1)
                y = (s_yr - self.min_year) * self.YEAR_SCALE + 200
                
                # Assign columns for this lineup
                active_member_ids = [m['artist_id'] for m in lineup['members']]
                
                # Strategy: If member already has a column, keep it.
                # If member is new, try to take a column that was just vacated (replacement).
                # Otherwise, take a new column.
                
                lineup_member_coords = []
                
                # Track which columns are used in this lineup
                current_lineup_cols = {}
                
                # First pass: members who already have a column
                for m in lineup['members']:
                    if m['artist_id'] in member_cols:
                        col = member_cols[m['artist_id']]
                        current_lineup_cols[m['artist_id']] = col
                
                # Second pass: new members
                # Find vacated columns from the previous lineup
                vacated_cols = []
                replacements = {} # col -> prev_member_name
                if l_idx > 0:
                    prev_lineup = lineups[l_idx-1]
                    prev_member_ids = [m['artist_id'] for m in prev_lineup['members']]
                    for pm_id in prev_member_ids:
                        if pm_id not in active_member_ids:
                            col = member_cols[pm_id]
                            vacated_cols.append(col)
                            # Find the member name for this col in prev lineup
                            for pm in prev_lineup['members']:
                                if pm['artist_id'] == pm_id:
                                    replacements[col] = pm['artist_name']
                                    break
                
                vacated_cols.sort()
                
                for m in lineup['members']:
                    if m['artist_id'] not in current_lineup_cols:
                        is_replacement = False
                        prev_name = None
                        if vacated_cols:
                            col = vacated_cols.pop(0)
                            is_replacement = True
                            prev_name = replacements.get(col)
                        else:
                            col = next_col
                            next_col += 1
                        
                        member_cols[m['artist_id']] = col
                        current_lineup_cols[m['artist_id']] = col
                        
                        m['is_replacement'] = is_replacement
                        m['replaced_from'] = prev_name

                # Create member layout nodes
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
                
                # Add lineup metadata for horizontal rules
                l_id = f"{b_id}_#{lineup['number']}"
                self.layout["bands"][b_id][f"lineup_{lineup['number']}"] = {
                    "y": y,
                    "x_start": current_x + self.LANE_PADDING,
                    "x_end": current_x + width - self.LANE_PADDING
                }

            current_x += width + self.BAND_SPACING_X

    def route_edges(self):
        # 1. Vertical Continuity Lines (same member, same band, consecutive lineups)
        members_by_artist_band = {}
        for m in self.layout["members"]:
            key = (m['artist_id'], m['band_id'])
            if key not in members_by_artist_band: members_by_artist_band[key] = []
            members_by_artist_band[key].append(m)
        
        for key, apps in members_by_artist_band.items():
            apps.sort(key=lambda x: x['start_year'])
            for i in range(len(apps) - 1):
                m1, m2 = apps[i], apps[i+1]
                # If they are in the same column (which they should be by our algorithm)
                if m1['x'] == m2['x']:
                    self.layout["edges"].append({
                        "type": "continuity",
                        "x": m1['x'],
                        "y1": m1['y'] + 10, # Start below name
                        "y2": m2['y'] - 5   # End above next appearance
                    })

        # 2. Migration Lines (member moving between bands)
        # Find all appearances of each artist
        artist_apps = {}
        for m in self.layout["members"]:
            a_id = m['artist_id']
            if a_id not in artist_apps: artist_apps[a_id] = []
            artist_apps[a_id].append(m)
            
        for a_id, apps in artist_apps.items():
            apps.sort(key=lambda x: x['start_year'])
            for i in range(len(apps) - 1):
                m1, m2 = apps[i], apps[i+1]
                if m1['band_id'] != m2['band_id']:
                    self.layout["edges"].append({
                        "type": "migration",
                        "x1": m1['x'],
                        "y1": m1['y'] + 20,
                        "x2": m2['x'],
                        "y2": m2['y'] - 5,
                        "name": m1['name']
                    })

    def get_coordinates(self):
        return self.layout
