from pydantic import BaseModel
from typing import List, Dict, Optional
import collections

class MemberEdge(BaseModel):
    artist_id: str
    artist_name: str
    band_id: str
    start_year: Optional[float] = None
    end_year: Optional[float] = None
    role: Optional[str] = None

class Lineup(BaseModel):
    number: int
    start_year: Optional[float]
    end_year: Optional[float]
    members: List[MemberEdge]

class BandNode(BaseModel):
    id: str
    name: str
    start_year: Optional[float] = None
    end_year: Optional[float] = None
    all_members: List[MemberEdge] = []
    lineups: List[Lineup] = []

class Refiner:
    def __init__(self):
        self.bands: Dict[str, BandNode] = {}

    def process_raw_data(self, raw_data):
        if not raw_data:
            return None

        # 1. Identify Bands
        for mbid, data in raw_data.items():
            artist_info = data.get('artist', {})
            if artist_info.get('type') == 'Group':
                ls = artist_info.get('life-span', {})
                start = self._parse_year(ls.get('begin'))
                end = self._parse_year(ls.get('end'))
                self.bands[mbid] = BandNode(id=mbid, name=artist_info.get('name'), start_year=start, end_year=end)
        
        # 2. Collect All Member Relations
        for mbid, data in raw_data.items():
            artist_info = data.get('artist', {})
            rels = artist_info.get('artist-relation-list', [])
            for rel in rels:
                if rel.get('type') == 'member of band':
                    target = rel.get('artist', {})
                    if artist_info.get('type') == 'Group':
                        m_id, b_id, m_name = target.get('id'), mbid, target.get('name')
                    else:
                        m_id, b_id, m_name = mbid, target.get('id'), artist_info.get('name')
                    
                    if b_id in self.bands:
                        edge = MemberEdge(
                            artist_id=m_id, artist_name=m_name, band_id=b_id,
                            start_year=self._parse_year(rel.get('begin')),
                            end_year=self._parse_year(rel.get('end')),
                            role=self._parse_role(rel.get('attributes', []))
                        )
                        if not any(m.artist_id == m_id and m.start_year == edge.start_year for m in self.bands[b_id].all_members):
                            self.bands[b_id].all_members.append(edge)

        # 3. Partition into Lineups
        for b_id, band in self.bands.items():
            band.lineups = self._calculate_lineups(band)

        return {"bands": self.bands}

    def _parse_year(self, date_str):
        if not date_str or len(date_str) < 4: return None
        try: return float(date_str[:4])
        except: return None

    def _parse_role(self, attributes):
        parts = [a if isinstance(a, str) else a.get('attribute', '') for a in attributes]
        return ", ".join(filter(None, parts)) if parts else None

    def _calculate_lineups(self, band: BandNode):
        # Find all significant "change years"
        years = set()
        if band.start_year: years.add(band.start_year)
        if band.end_year: years.add(band.end_year)
        
        for m in band.all_members:
            if m.start_year: years.add(m.start_year)
            if m.end_year: years.add(m.end_year)
        
        sorted_years = sorted(list(years))
        if not sorted_years: return []

        lineups = []
        lineup_count = 1
        
        # Create epochs between years
        for i in range(len(sorted_years) - 1):
            s_yr = sorted_years[i]
            e_yr = sorted_years[i+1]
            mid_yr = s_yr + 0.5
            
            # Who was in the band during this epoch?
            active_members = []
            for m in band.all_members:
                m_start = m.start_year or band.start_year or 0
                m_end = m.end_year or band.end_year or 2025
                if m_start <= mid_yr <= m_end:
                    active_members.append(m)
            
            if not active_members: continue

            # Check if this lineup is the same as the previous one
            if lineups and [m.artist_id for m in lineups[-1].members] == [m.artist_id for m in active_members]:
                lineups[-1].end_year = e_yr
            else:
                lineups.append(Lineup(
                    number=lineup_count,
                    start_year=s_yr,
                    end_year=e_yr,
                    members=active_members
                ))
                lineup_count += 1
        
        return lineups
