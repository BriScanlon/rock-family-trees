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
    position: Optional[int] = None

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

    def process_graph_data(self, graph_data):
        """
        Processes data returned from Neo4j (via Harvester/GraphDB)
        """
        if not graph_data or "bands" not in graph_data:
            return None

        for b_id, b_data in graph_data["bands"].items():
            all_members = []
            for m in b_data.get("all_members", []):
                all_members.append(MemberEdge(
                    artist_id=m["artist_id"],
                    artist_name=m["artist_name"],
                    band_id=b_id,
                    start_year=m["start_year"],
                    end_year=m["end_year"],
                    role=m["role"],
                    position=m.get("position")
                ))
            
            self.bands[b_id] = BandNode(
                id=b_id,
                name=b_data["name"],
                start_year=b_data["start_year"],
                end_year=b_data["end_year"],
                all_members=all_members
            )
        
        # Partition into lineups
        for b_id, band in self.bands.items():
            band.lineups = self._calculate_lineups(band)

        return {"bands": self.bands}

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
        
        for i in range(len(sorted_years) - 1):
            s_yr = sorted_years[i]
            e_yr = sorted_years[i+1]
            mid_yr = s_yr + 0.5
            
            active_members = []
            for m in band.all_members:
                m_start = m.start_year or band.start_year or 0
                m_end = m.end_year or band.end_year or 2026
                if m_start <= mid_yr <= m_end:
                    active_members.append(m)
            
            if not active_members: continue

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