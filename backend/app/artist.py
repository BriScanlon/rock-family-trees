import svgwrite
import random
import math

class Artist:
    def __init__(self, layout, output_path="artifacts/preview.svg"):
        self.layout = layout
        self.versions = layout.get("versions", {})
        self.members = layout.get("members", [])
        self.edges = layout.get("edges", [])
        self.output_path = output_path
        
        # Determine Canvas Size
        self.width = 3000 # Wider canvas for clusters
        max_y = 2000
        for v in self.versions.values():
            max_y = max(max_y, v['y'] + 400)
            self.width = max(self.width, v['x'] + v['width'] + 200)
            
        self.dwg = svgwrite.Drawing(self.output_path, profile='full', size=(f"{self.width}px", f"{max_y}px"))
        
        # Background: Parchment
        self.dwg.add(self.dwg.rect(insert=(0, 0), size=('100%', '100%'), fill='#f4f1ea'))

    def _draw_line(self, x1, y1, x2, y2, width=1, dashed=False):
        kwargs = {"stroke": "black", "fill": "none", "stroke_width": width}
        if dashed: kwargs["stroke_dasharray"] = "4,2"
        self.dwg.add(self.dwg.line(start=(x1, y1), end=(x2, y2), **kwargs))

    def _draw_elbow(self, x1, y1, x2, y2, note=None):
        """Vertical down -> Horizontal -> Vertical down"""
        mid_y = (y1 + y2) / 2
        
        path = f"M {x1} {y1} L {x1} {mid_y} L {x2} {mid_y} L {x2} {y2}"
        self.dwg.add(self.dwg.path(d=path, stroke="black", fill="none", stroke_width=1))
        
        if note and abs(x2 - x1) > 50:
            # Add note on the horizontal segment
            txt_x = (x1 + x2) / 2
            self.dwg.add(self.dwg.text(note, insert=(txt_x, mid_y - 3), 
                                       font_family="Georgia", font_style="italic", font_size="10", 
                                       text_anchor="middle", fill="black"))

    def draw_versions(self):
        for v in self.versions.values():
            vx, vy = v['x'], v['y']
            w = v['width']
            
            # Header: Band Name
            # Center text on the version box
            center_x = vx
            
            self.dwg.add(self.dwg.text(v['band_name'], 
                                       insert=(center_x, vy), 
                                       font_family="Impact, sans-serif", 
                                       font_size="24", 
                                       text_anchor="middle",
                                       fill='black'))
            
            # Sub-Header
            self.dwg.add(self.dwg.text(v['sublabel'], 
                                       insert=(center_x, vy + 15), 
                                       font_family="Arial Narrow, sans-serif", 
                                       font_size="12", 
                                       text_anchor="middle",
                                       fill='black'))

            # Horizontal Beam
            beam_y = v['beam_y']
            beam_start_x = vx - (w / 2)
            beam_end_x = vx + (w / 2)
            
            self.dwg.add(self.dwg.line(start=(beam_start_x, beam_y), 
                                       end=(beam_end_x, beam_y), 
                                       stroke="black", stroke_width=2))
            
            # Member Ticks
            # Find members for this version
            version_members = [m for m in self.members if m['version_id'] == v['id']]
            for m in version_members:
                # Tick from Beam down to just above member name
                # m['y'] is where the name starts. 
                # Let's drop the tick to m['y'] - 12 (approx top of text)
                self.dwg.add(self.dwg.line(start=(m['x'], beam_y), 
                                           end=(m['x'], m['y'] - 12), 
                                           stroke="black", stroke_width=1))

    def draw_members(self):
        for m in self.members:
            # Name (Bold)
            self.dwg.add(self.dwg.text(m['name'], 
                                       insert=(m['x'], m['y']), 
                                       font_family="Arial Narrow, sans-serif", 
                                       font_weight="bold",
                                       font_size="12", 
                                       text_anchor="middle",
                                       fill='black'))
            
            # Role (Regular) - clean up role string
            role = m['role'].split(',')[0].strip().lower()
            self.dwg.add(self.dwg.text(role, 
                                       insert=(m['x'], m['y'] + 10), 
                                       font_family="Arial Narrow, sans-serif", 
                                       font_size="10", 
                                       text_anchor="middle",
                                       fill='black'))

    def draw_connections(self):
        for edge in self.edges:
            if edge['type'] == 'continuity':
                # Simple line
                self._draw_line(edge['x1'], edge['y1'], edge['x2'], edge['y2'])
            
            elif edge['type'] == 'migration':
                self._draw_elbow(edge['x1'], edge['y1'], edge['x2'], edge['y2'], edge.get('note'))

    def draw_all(self):
        self.draw_versions()
        self.draw_members()
        self.draw_connections()

    def save(self):
        self.dwg.save()
        return self.output_path
