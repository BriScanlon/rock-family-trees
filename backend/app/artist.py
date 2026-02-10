import svgwrite

class Artist:
    def __init__(self, layout, output_path="artifacts/preview.svg"):
        self.layout = layout
        self.bands = layout.get("bands", {})
        self.members = layout.get("members", [])
        self.edges = layout.get("edges", [])
        self.output_path = output_path
        
        # Calculate canvas size
        max_x = 2000
        max_y = 2000
        for b in self.bands.values():
            max_x = max(max_x, b['x'] + b['width'] + 500)
        for m in self.members:
            max_y = max(max_y, m['y'] + 500)
            
        self.dwg = svgwrite.Drawing(self.output_path, profile='full', size=(f"{max_x}px", f"{max_y}px"))
        # Background: aged paper
        self.dwg.add(self.dwg.rect(insert=(0, 0), size=('100%', '100%'), fill='#f4f1ea'))

    def draw_lineups(self):
        # Draw Band Titles
        for b_id, b in self.bands.items():
            # Band Name: Impact, All Caps
            self.dwg.add(self.dwg.text(b['name'].upper(), 
                                       insert=(b['x'] + 40, b['y'] - 60), 
                                       font_family="Impact, Charcoal, sans-serif", 
                                       font_size="42", 
                                       fill='black'))
            
            # Find all lineups for this band to draw horizontal rules
            for key, val in b.items():
                if key.startswith("lineup_"):
                    # 2px horizontal rule above member names
                    self.dwg.add(self.dwg.line(start=(val['x_start'], val['y'] - 25), 
                                               end=(val['x_end'], val['y'] - 25), 
                                               stroke='black', stroke_width=2))
                    
                    # Optional: Lineup number or dates
                    # self.dwg.add(self.dwg.text(f"Lineup {key.split('_')[1]}", 
                    #                           insert=(val['x_start'], val['y'] - 35),
                    #                           font_family="Arial Narrow, sans-serif",
                    #                           font_size="10", font_style="italic"))

        # Draw Members
        for m in self.members:
            display_name = m['name']
            if m.get('is_replacement') and m.get('replaced_from'):
                display_name = f"{m['replaced_from']} \u2192 {m['name']}"

            # Name: Bold
            self.dwg.add(self.dwg.text(display_name, 
                                       insert=(m['x'], m['y']), 
                                       font_family="Arial Narrow, Arial, sans-serif", 
                                       font_size="14", 
                                       font_weight="bold",
                                       fill='black'))
            # Role: Regular
            if m.get('role'):
                role_text = f" ({m['role']})"
                self.dwg.add(self.dwg.text(role_text, 
                                           insert=(m['x'], m['y'] + 16), 
                                           font_family="Arial Narrow, Arial, sans-serif", 
                                           font_size="11", 
                                           fill='black'))
            
            # Dates: Smaller italicized
            date_text = f"{int(m['start_year'])} - {int(m['end_year'])}"
            self.dwg.add(self.dwg.text(date_text, 
                                       insert=(m['x'], m['y'] - 5), 
                                       font_family="Arial Narrow, Arial, sans-serif", 
                                       font_size="9", 
                                       font_style="italic",
                                       fill='#333'))

    def draw_connections(self):
        for edge in self.edges:
            if edge['type'] == 'continuity':
                # 1px vertical lineage lines
                # Draw from bottom of one member block to top of next
                self.dwg.add(self.dwg.line(start=(edge['x'] + 5, edge['y1']), 
                                           end=(edge['x'] + 5, edge['y2']), 
                                           stroke='black', stroke_width=1))
            
            elif edge['type'] == 'migration':
                # Curved migration lines
                x1, y1, x2, y2 = edge['x1'], edge['y1'], edge['x2'], edge['y2']
                mid_y = (y1 + y2) / 2
                path = f"M {x1+5} {y1} C {x1+5} {mid_y}, {x2+5} {mid_y}, {x2+5} {y2}"
                self.dwg.add(self.dwg.path(d=path, stroke='black', fill='none', stroke_width=1, stroke_dasharray="4,2"))

        def draw_all(self):

            self.draw_lineups()

            self.draw_connections()

    

        def save(self):

            self.dwg.save()

            return self.output_path

    