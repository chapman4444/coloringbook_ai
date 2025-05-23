# segmentation.py
# Core Python
import os
import json
import numpy as np
from PIL import Image
from skimage.filters import threshold_sauvola, threshold_otsu
from skimage.morphology import closing, disk, remove_small_objects, remove_small_holes
from skimage.measure import label, regionprops
from skimage.segmentation import clear_border
from scipy.ndimage import binary_dilation, distance_transform_edt
from shapely.ops import unary_union, polygonize
from shapely.geometry import LineString
from svgpathtools import svg2paths
from collections import Counter
import tkinter as tk
from tkinter import ttk, simpledialog, messagebox


class SegmentationSettingsDialog(tk.Toplevel):
    def __init__(self, master, seg_params, defaults, on_apply_callback):
        super().__init__(master)
        self.title("Segmentation Settings")
        self.seg_params = seg_params
        self.defaults = defaults
        self.on_apply = on_apply_callback
        self.user_presets = self._load_presets()

        self.var_mode = tk.StringVar(value=self.seg_params.get('preset_name', 'Custom'))
        self.var_method = tk.StringVar(value=self.seg_params.get('method'))
        self.var_window = tk.IntVar(value=self.seg_params.get('window_size'))
        self.var_k = tk.DoubleVar(value=self.seg_params.get('k'))
        self.var_disk = tk.IntVar(value=self.seg_params.get('morph_disk'))
        self.var_min = tk.IntVar(value=self.seg_params.get('min_size'))
        self.var_hole = tk.IntVar(value=self.seg_params.get('hole_threshold'))
        self.var_merge = tk.DoubleVar(value=self.seg_params.get('merge_ratio'))
        self.var_clear = tk.BooleanVar(value=self.seg_params.get('clear_border', True))
        self.var_invert = tk.BooleanVar(value=self.seg_params.get('invert_mask', True))

        self._build_ui()
        self._update_fields_from_mode()


    def _build_ui(self):
        frm = tk.Frame(self)
        frm.pack(padx=10, pady=10)

        presets = ["Default", "Option 1", "Option 2"] + list(self.user_presets.keys()) + ["Custom"]
        tk.Label(frm, text="Presets:").grid(row=0, column=0, sticky='w')
        preset_menu = ttk.OptionMenu(frm, self.var_mode, self.var_mode.get(), *presets, command=self._update_fields_from_mode)
        preset_menu.grid(row=0, column=1, sticky='ew')

        menu_btn = tk.Menubutton(frm, text="⋮", relief=tk.RAISED)
        menu_btn.grid(row=0, column=2)
        menu = tk.Menu(menu_btn, tearoff=0)
        menu.add_command(label="Save Preset", command=self._save_preset)
        menu.add_command(label="Delete Preset", command=self._delete_preset)
        menu_btn.config(menu=menu)

        self._add_option(frm, "Threshold Method", self.var_method, ['Sauvola', 'Otsu'])
        self._add_slider(frm, "Window Size", self.var_window, 15, 255, 2)
        self._add_slider(frm, "Sauvola k", self.var_k, 0.01, 1.0, 0.01)
        self._add_slider(frm, "Morph Disk", self.var_disk, 1, 10, 1)
        self._add_slider(frm, "Min Size", self.var_min, 1, 2000, 10)
        self._add_slider(frm, "Hole Threshold", self.var_hole, 1, 2000, 10)
        self._add_slider(frm, "Merge Ratio", self.var_merge, 0.00001, 0.1, 0.0001)

        tk.Checkbutton(frm, text="Clear Border", variable=self.var_clear, command=self._set_custom).grid(row=8, column=0, sticky='w')
        tk.Checkbutton(frm, text="Invert Mask", variable=self.var_invert, command=self._set_custom).grid(row=8, column=1, sticky='w')

        btns = tk.Frame(self)
        btns.pack(pady=5)
        tk.Button(btns, text="Apply", command=self._apply).pack(side=tk.LEFT, padx=5)
        tk.Button(btns, text="Close", command=self.destroy).pack(side=tk.LEFT, padx=5)

    def _add_option(self, parent, label, var, options):
        row = parent.grid_size()[1]
        tk.Label(parent, text=label + ":").grid(row=row, column=0, sticky='w')
        opt = ttk.OptionMenu(parent, var, var.get(), *options, command=lambda _: self._set_custom())
        opt.grid(row=row, column=1, columnspan=2, sticky='ew')

    def _add_slider(self, parent, label, var, frm, to, step):
        row = parent.grid_size()[1]
        tk.Label(parent, text=label + ":").grid(row=row, column=0, sticky='w')
        scale = tk.Scale(parent, variable=var, from_=frm, to=to, resolution=step, orient='horizontal', command=lambda _: self._set_custom())
        scale.grid(row=row, column=1, columnspan=2, sticky='ew')

    def _update_fields_from_mode(self, *_):
        mode = self.var_mode.get()
        self._set_custom(skip=True)
        presets = {
            "Default": self.defaults,
            "Option 1": {
                'method': 'Sauvola', 'window_size': 15, 'k': 0.15, 'morph_disk': 1,
                'min_size': 3, 'hole_threshold': 3, 'merge_ratio': 1e-5,
                'clear_border': True, 'invert_mask': True
            },
            "Option 2": {
                'method': 'Sauvola', 'window_size': 15, 'k': 0.15, 'morph_disk': 1,
                'min_size': 3, 'hole_threshold': 3, 'merge_ratio': 1e-5,
                'clear_border': False, 'invert_mask': True
            },
            **self.user_presets
        }
        if mode in presets:
            self._set_fields(presets[mode])

    def _set_fields(self, p):
        self.var_method.set(p['method'])
        self.var_window.set(p['window_size'])
        self.var_k.set(p['k'])
        self.var_disk.set(p['morph_disk'])
        self.var_min.set(p['min_size'])
        self.var_hole.set(p['hole_threshold'])
        self.var_merge.set(p['merge_ratio'])
        self.var_clear.set(p['clear_border'])
        self.var_invert.set(p['invert_mask'])

    def _collect_current(self):
        return {
            'method': self.var_method.get(),
            'window_size': self.var_window.get(),
            'k': self.var_k.get(),
            'morph_disk': self.var_disk.get(),
            'min_size': self.var_min.get(),
            'hole_threshold': self.var_hole.get(),
            'merge_ratio': self.var_merge.get(),
            'clear_border': self.var_clear.get(),
            'invert_mask': self.var_invert.get(),
            'preset_name': self.var_mode.get()
        }

    def _apply(self):
        self.seg_params.update(self._collect_current())
        self.on_apply()
        #self.destroy()

    def _set_custom(self, skip=False):
        if not skip:
            self.var_mode.set("Custom")

    def _save_preset(self):
        name = simpledialog.askstring("Save Preset", "Preset name:")
        if not name: return
        if name in ("Default", "Option 1", "Option 2"):
            messagebox.showerror("Error", "Cannot overwrite protected presets.")
            return
        self.user_presets[name] = self._collect_current()
        self._save_presets()
        self.var_mode.set(name)

    def _delete_preset(self):
        name = self.var_mode.get()
        if name in ("Default", "Option 1", "Option 2"):
            messagebox.showerror("Error", "Cannot delete protected presets.")
            return
        if name in self.user_presets:
            del self.user_presets[name]
            self._save_presets()
            self.var_mode.set("Default")
            self._update_fields_from_mode()

    def _preset_path(self):
        import os
        return os.path.join(os.path.expanduser("~"), ".segmentation_presets.json")

    def _load_presets(self):
        import json
        try:
            with open(self._preset_path(), "r") as f:
                return json.load(f)
        except Exception:
            return {}

    def _save_presets(self):
        import json
        try:
            with open(self._preset_path(), "w") as f:
                json.dump(self.user_presets, f, indent=2)
        except Exception as e:
            print("Failed to save presets:", e)


class SegmentationLogic:
    def __init__(self, app):
        self.app = app

    def refresh_segmented_preview(self, label_map, zone_colors, zone_labels, label_positions, image, show_zone_numbers=True):
        import numpy as np
        import cv2
        from PIL import Image

        if label_map is None or label_map.max() == 0:
            return None

        h, w = label_map.shape
        gray = np.array(image.resize((w, h), Image.Resampling.LANCZOS))
        base = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
        seg_img = base.copy()

        for zid in range(1, int(label_map.max()) + 1):
            mask = label_map == zid
            color = zone_colors.get(zid, (255, 255, 255))
            if color != (255, 255, 255) and mask.any():
                bgr = np.array(color[::-1], dtype=np.uint8)
                seg_img[mask] = cv2.addWeighted(seg_img[mask], 0.5, np.full_like(seg_img[mask], bgr), 0.5, 0)

        if show_zone_numbers:
            font = cv2.FONT_HERSHEY_SIMPLEX
            for zid, (cx, cy) in label_positions.items():
                txt = zone_labels.get(zid, str(zid))
                if label_map.max() < 50:
                    fs, th = (0.8, 2)
                elif label_map.max() < 150:
                    fs, th = (0.5, 1)
                else:
                    fs, th = (0.4, 1)
                (tw, tht), _ = cv2.getTextSize(txt, font, fs, th)
                pos = (int(cx - tw // 2), int(cy + tht // 2))
                cv2.putText(seg_img, txt, pos, font, fs, (255, 255, 255), th + 2, cv2.LINE_AA)
                cv2.putText(seg_img, txt, pos, font, fs, (0, 0, 0), th, cv2.LINE_AA)

        return Image.fromarray(cv2.cvtColor(seg_img, cv2.COLOR_BGR2RGB))



    def segment_image(self, image_resized, log_params=True):
        self.app.last_orig_pil = image_resized
        self.app.image = image_resized
        gray = np.array(image_resized.convert('L'))
        mask = self._threshold_image(gray)
        mask = self._cleanup_binary(mask)
        if self.app.seg_params.get('invert_mask', True):
            mask = ~mask
        if self.app.seg_params.get('clear_border', True):
            mask = clear_border(mask)
        label_map = label(mask, connectivity=2, background=0)
        label_map = self._merge_small_regions(label_map, min_area_ratio=self.app.seg_params.get('merge_ratio', 0.00001))
        self.app.label_map = label_map
        self.app.num_zones = int(label_map.max())
        self.app.zone_label_positions = self._compute_label_positions(label_map)
        self.app.zone_labels = {i: str(i) for i in range(1, self.app.num_zones + 1)}
        self.app.zone_colors = {}
#        if log_params:
#            self.app.log_to_terminal("Segmentation Parameters", self.app.seg_params)
#        self.app.history.clear()
#        self.app.redo_stack.clear()
        preview = self.app.segmentation.refresh_segmented_preview(self.app.label_map, self.app.zone_colors, self.app.zone_labels, self.app.zone_label_positions, self.app.image, self.app.show_zone_numbers)
        if preview:
            self.app.last_seg_pil = preview
            self.app.display_overlay_image()
        self.app.push_history()

    def _threshold_image(self, gray):
        k = self.app.seg_params.get('k', 0.15)
        w = self.app.seg_params.get('window_size', max(15, (min(gray.shape) // 50) | 1))
        try:
            local_th = threshold_sauvola(gray, window_size=w, k=k)
            mask = gray <= local_th
            frac = mask.mean()
            if frac < 0.01 or frac > 0.99:
                raise ValueError
            return mask
        except Exception:
            return gray <= threshold_otsu(gray)

    def _cleanup_binary(self, mask):
        r = self.app.seg_params.get('morph_disk', 1)
        m = closing(mask, disk(r))
        area = m.size
        fallback_sz = max(30, int(area * 1e-5))
        min_size = self.app.seg_params.get('min_size', fallback_sz)
        hole_size = self.app.seg_params.get('hole_threshold', fallback_sz)
        m = remove_small_objects(m, min_size=min_size, connectivity=2)
        m = remove_small_holes(m, area_threshold=hole_size, connectivity=2)
        return m

    def _merge_small_regions(self, label_map, min_area_ratio=0.00001):
        zones = label_map.copy()
        total = zones.size
        thresh = total * min_area_ratio
        for r in regionprops(zones):
            if r.area < thresh:
                minr, minc, maxr, maxc = r.bbox
                crop = zones[minr:maxr, minc:maxc]
                mask = (crop == r.label)
                border = binary_dilation(mask, disk(3)) & ~mask
                neigh = crop[border]
                valid = neigh[(neigh != r.label) & (neigh != 0)]
                if valid.size:
                    zones[zones == r.label] = Counter(valid).most_common(1)[0][0]
        return zones

    def _compute_label_positions(self, label_map):
        pts = {}
        for r in regionprops(label_map):
            minr, minc, maxr, maxc = r.bbox
            sub = (label_map[minr:maxr, minc:maxc] == r.label)
            dt = distance_transform_edt(sub)
            if dt.max() > 1:
                y0, x0 = np.unravel_index(dt.argmax(), dt.shape)
                pts[r.label] = (minc + x0, minr + y0)
            else:
                cy, cx = r.centroid
                pts[r.label] = (int(cx), int(cy))
        return pts

    def __path_segmentation_settings(self):
        return os.path.join(os.path.expanduser("~"), ".segmentation_settings.json")

    def _load_segmentation_settings(self):
        try:
            with open(self.__path_segmentation_settings(), "r") as f:
                return json.load(f)
        except Exception:
            #from segmentation import SegmentationSettingsDialog
            from segmentation import get_segmentation_presets
            return get_segmentation_presets()["Default"].copy()

            #return SegmentationSettingsDialog(None, {}, {}, lambda: None).defaults.copy()

    def _save_segmentation_settings(self):
        try:
            with open(self.__path_segmentation_settings(), "w") as f:
                json.dump(self.app.seg_params, f, indent=2)
        except Exception as e:
            self.app.log_to_terminal("Save Failed", str(e))



class SegmentationGUI:
    def __init__(self, app):
        self.app = app

    def open_segmentation_settings(self):
        from segmentation import SegmentationSettingsDialog

        def on_apply():
            self.app.segmentation._save_segmentation_settings()
            if self.app.last_orig_pil:
                self.app.segmentation.segment_image(self.app.last_orig_pil)

        #SegmentationSettingsDialog(self.app.root, self.app.seg_params, self.app.presets["Default"], on_apply)
        from segmentation import get_segmentation_presets
        defaults = get_segmentation_presets()["Default"]
        SegmentationSettingsDialog(self.app.root, self.app.seg_params, defaults, on_apply)


    def open_svg_segmentation(self, svg_path=None):
        from tkinter import filedialog
        from PIL import Image
        import random

        if not svg_path:
            svg_path = filedialog.askopenfilename(
                title="Select SVG File",
                filetypes=[("SVG Files", "*.svg")]
            )
        if not svg_path:
            return

        # Use current image size if available, otherwise default
        if self.app.image:
            w, h = self.app.image.width, self.app.image.height
        else:
            w, h = 3300, 2550  # Default size

        # Process SVG to label map and metadata
        vs = VectorSegmentation(svg_path, image_size=(w, h))
        vs.run_all()

        self.app.label_map = vs.label_map
        self.app.num_zones = len(vs.zones)
        self.app.zone_labels = {i: str(i) for i in range(1, self.app.num_zones + 1)}
        self.app.zone_label_positions = vs.label_positions

        # Generate random pastel color for each zone
        def random_pastel():
            return tuple(random.randint(100, 230) for _ in range(3))

        self.app.zone_colors = {
            zone_id: random_pastel()
            for zone_id in range(1, self.app.num_zones + 1)
        }

        # Use a white base image
        white = Image.new("RGB", (w, h), (255, 255, 255))
        self.app.image = white
        self.app.last_orig_pil = white
        self.app.base_pil = white.copy()

        # Show the overlay preview
        preview = self.app.segmentation.refresh_segmented_preview(
            self.app.label_map,
            self.app.zone_colors,
            self.app.zone_labels,
            self.app.zone_label_positions,
            self.app.image,
            self.app.show_zone_numbers,
        )
        if preview:
            self.app.last_seg_pil = preview
            self.app.display_overlay_image()

        self.app.push_history()






class VectorSegmentation:
    def __init__(self, svg_path, image_size):
        self.svg_path = svg_path
        self.image_size = image_size
        self.paths = []
        self.label_positions = {}
        self.zones = []
        self.label_map = None

    def run_all(self):
        self._load_svg()
        self._polygonize()
        self._rasterize_to_label_map()

    def _load_svg(self):
        from svgpathtools import svg2paths
        paths, _ = svg2paths(self.svg_path)
        sampled_paths = []
        for path in paths:
            points = [path.point(t) for t in np.linspace(0, 1, 50)]
            coords = [(pt.real, pt.imag) for pt in points]
            if len(coords) >= 2:
                sampled_paths.append(LineString(coords))
        self.paths = sampled_paths

    def _polygonize(self):
        merged = unary_union(self.paths)
        polys = list(polygonize(merged))
        self.zones = [p for p in polys if p.area > 100]
        self.label_positions = {
            i + 1: (int(p.representative_point().x), int(p.representative_point().y))
            for i, p in enumerate(self.zones)
        }

    def _rasterize_to_label_map(self):
        import numpy as np
        from PIL import Image, ImageDraw
        from skimage.morphology import binary_dilation, remove_small_objects
        from skimage.measure import label

        w, h = self.image_size
        scale = 2  # 2x oversample
        big_w, big_h = w * scale, h * scale
        mask = np.zeros((big_h, big_w), dtype=np.uint16)  # was uint8 — now fixed

        for i, poly in enumerate(self.zones):
            img = Image.new("L", (big_w, big_h), 0)
            xy = [(x * scale, y * scale) for x, y in poly.exterior.coords]
            ImageDraw.Draw(img).polygon(xy, fill=255)
            mask_i = np.array(img)
            mask[mask_i == 255] = i + 1

        # Downsample back to original size
        from skimage.transform import resize
        mask_small = resize(mask, (h, w), order=0, preserve_range=True, anti_aliasing=False).astype(np.uint16)

        # Binarize, dilate, cleanup
        labeled = label(mask_small > 0, connectivity=2, background=0)
        cleaned = remove_small_objects(labeled, min_size=32, connectivity=2)
        dilated = binary_dilation(cleaned > 0)

        final_label = label(dilated, connectivity=2, background=0)
        self.label_map = final_label


def get_segmentation_presets():
    return {
        "Default": {
            'method': 'Sauvola',
            'window_size': 51,
            'k': 0.2,
            'morph_disk': 2,
            'min_size': 500,
            'hole_threshold': 500,
            'merge_ratio': 0.002,
            'clear_border': True,
            'invert_mask': True,
            'preset_name': "Default"
        },
        "Preset 1": {
            'method': 'Sauvola',
            'window_size': 15,
            'k': 0.15,
            'morph_disk': 1,
            'min_size': 3,
            'hole_threshold': 3,
            'merge_ratio': 1e-5,
            'clear_border': True,
            'invert_mask': True,
            'preset_name': "Preset 1"
        },
        "Preset 2": {
            'method': 'Sauvola',
            'window_size': 15,
            'k': 0.15,
            'morph_disk': 1,
            'min_size': 3,
            'hole_threshold': 3,
            'merge_ratio': 1e-5,
            'clear_border': False,
            'invert_mask': True,
            'preset_name': "Preset 2"
        },
    }
