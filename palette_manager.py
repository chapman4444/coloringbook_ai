import random
import json
from typing import List, Tuple, Optional, Dict
from PyQt5.QtGui import QColor

class PaletteManager:
    def __init__(self):
        self._palettes = []
        self._palette_names = []
        self._current_palette_index = 0
        self._current_color_index = 0
        self._mode = 'sequential'
        self._single_click_color = (255, 0, 0)
        self._zone_color_map: Dict[int, QColor] = {}

    def load_palette_from_list(self, rgb_list: List[Tuple[int, int, int]], name: Optional[str] = None):
        self._palettes.append(list(rgb_list))
        self._palette_names.append(name or f"Palette {len(self._palettes)}")

    def generate_random_palette(self, n: int, seed: Optional[int] = None):
        rnd = random.Random(seed)
        palette = [tuple(rnd.randint(0, 255) for _ in range(3)) for _ in range(n)]
        self.load_palette_from_list(palette, name=f"Random ({n})")

    def get_current_palette(self) -> List[Tuple[int, int, int]]:
        if self._palettes:
            return self._palettes[self._current_palette_index]
        return []

    def get_next_color(self) -> Tuple[int, int, int]:
        palette = self.get_current_palette()
        if not palette:
            return (128, 128, 128)
        if self._mode == 'sequential':
            color = palette[self._current_color_index % len(palette)]
            self._current_color_index += 1
            return color
        elif self._mode == 'random':
            return random.choice(palette)
        elif self._mode == 'single-click':
            return self._single_click_color
        return (128, 128, 128)

    def assign_next_color_to_zone(self, zone_id: int) -> QColor:
        rgb = self.get_next_color()
        qcolor = QColor(*rgb)
        self._zone_color_map[zone_id] = qcolor
        return qcolor

    def get_zone_color(self, zone_id: int) -> Optional[QColor]:
        return self._zone_color_map.get(zone_id, None)

    def get_all_zone_colors(self) -> Dict[int, QColor]:
        return dict(self._zone_color_map)

    def get_current_palette_qcolors(self) -> List[QColor]:
        return [QColor(*rgb) for rgb in self.get_current_palette()]
