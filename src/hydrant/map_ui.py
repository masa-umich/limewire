from nicegui import ui


class Map_UI:
    def __init__(self):
        self.map = ui.leaflet(center=(42.2808, -83.7430), zoom=12).classes("h-[80vh]")
        self.map.clear_layers()
        self.map.tile_layer(url_template="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}", options={'maxZoom': 18})
        self.marker: ui.leaflet.marker = None
    
    async def create_icon(self):
        js = '''
                L.divIcon({
                    className: 'blue-dot-icon',
                    html: "<div style='width:10px;height:10px;border-radius:50%%;background:#1976d2;border:2px solid white;box-shadow:0 0 2px #000;'></div>",
                    iconSize: [14, 14],
                    iconAnchor: [7, 7]
                })
            '''
        self.marker_icon = await ui.run_javascript(js, timeout=5)
    
    def update_marker(self, loc: tuple[float, float]):
        if self.marker is None:
            self.marker = self.map.marker(latlng=loc)
        else:
            self.marker.move(*loc)
        self.map.center = loc