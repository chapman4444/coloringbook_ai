# main.py

import sys
import os
import json
import numpy as np
import cv2
from PyQt5.QtCore import Qt, QRectF, QPointF, QSizeF, pyqtSignal
from PyQt5.QtGui import QImage, QPainter, QFont, QTransform, QColor, QContextMenuEvent
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QGraphicsView, QGraphicsScene,
    QGraphicsTextItem, QFileDialog, QToolBar, QAction, QMessageBox,
    QWidget, QVBoxLayout, QSlider, QCheckBox, QLabel, QHBoxLayout, QMenu
)
from PyQt5.QtSvg import QGraphicsSvgItem, QSvgRenderer
from palette_manager import PaletteManager
from segmentation import SegmentationLogic, get_segmentation_presets


class ZoneLabel(QGraphicsTextItem):
    def __init__(self, text, pos, parent=None):
        super().__init__(text, parent)
        self.setZValue(10)
        self.setFlag(QGraphicsTextItem.ItemIgnoresTransformations, True)
        self.setFont(QFont("Arial", 14, QFont.Bold))
        self.setDefaultTextColor(Qt.red)
        self.setPos(pos - QPointF(self.boundingRect().width() / 2, self.boundingRect().height() / 2))
        self.setAcceptHoverEvents(True)
        self.setAcceptedMouseButtons(Qt.MiddleButton)

    def mousePressEvent(self, event):
        if event.button() == Qt.MiddleButton:
            self.setDefaultTextColor(Qt.blue if self.defaultTextColor() == Qt.red else Qt.red)


class GraphicsView(QGraphicsView):
    zoomChanged = pyqtSignal(float)

    def __init__(self, scene, parent=None):
        super().__init__(scene, parent)
        self.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.AnchorUnderMouse)
        self.setDragMode(QGraphicsView.ScrollHandDrag)
        self._zoom = 1.0

    def zoom(self, factor):
        self._zoom *= factor
        self.setTransform(QTransform().scale(self._zoom, self._zoom))
        self.zoomChanged.emit(self._zoom)

    def reset_zoom(self):
        self._zoom = 1.0
        self.setTransform(QTransform())
        self.zoomChanged.emit(self._zoom)

    def wheelEvent(self, event):
        if event.modifiers() & Qt.ControlModifier:
            factor = 1.25 if event.angleDelta().y() > 0 else 0.8
            self.zoom(factor)
        else:
            super().wheelEvent(event)

    def contextMenuEvent(self, event: QContextMenuEvent):
        menu = QMenu()
        menu.addAction("Context menu placeholder")
        menu.exec_(event.globalPos())


class SvgZoneLabeler(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("SVG Zone Labeler — Pan/Zoom Fixed v2")
        self.resize(1200, 900)
        self.svg_filepath = None
        self.svg_item = None
        self.svg_renderer = None
        self.labels = []
        self.palette = PaletteManager()
        self.palette.generate_random_palette(8)
        self.raster_img = None
        self.raster_scale = 1.0
        self.scene_svg_rect = QRectF()
        self.binary_preview = None
        self.threshold = 240
        self.fill = False
        self._setup_ui()

    def _setup_ui(self):
        central_widget = QWidget()
        layout = QVBoxLayout(central_widget)
        self.setCentralWidget(central_widget)

        self.scene = QGraphicsScene(self)
        self.view = GraphicsView(self.scene, self)
        layout.addWidget(self.view)

        toolbar = QToolBar("Main Toolbar")
        self.addToolBar(toolbar)

        open_action = QAction("Open SVG", self)
        export_action = QAction("Export JSON", self)
        zoom_in_action = QAction("Zoom In", self)
        zoom_out_action = QAction("Zoom Out", self)
        reset_zoom_action = QAction("Reset Zoom", self)
        toolbar.addAction(open_action)
        toolbar.addAction(export_action)
        toolbar.addSeparator()
        toolbar.addAction(zoom_in_action)
        toolbar.addAction(zoom_out_action)
        toolbar.addAction(reset_zoom_action)

        control_layout = QHBoxLayout()
        self.threshold_slider = QSlider(Qt.Horizontal)
        self.threshold_slider.setMinimum(0)
        self.threshold_slider.setMaximum(255)
        self.threshold_slider.setValue(self.threshold)
        self.threshold_slider.setTickInterval(5)
        self.threshold_slider.setTickPosition(QSlider.TicksBelow)

        self.threshold_label = QLabel(f"Threshold: {self.threshold}")
        self.fill_checkbox = QCheckBox("Show Fill")
        control_layout.addWidget(self.threshold_label)
        control_layout.addWidget(self.threshold_slider)
        control_layout.addWidget(self.fill_checkbox)
        layout.addLayout(control_layout)

        open_action.triggered.connect(self.open_svg)
        export_action.triggered.connect(self.export_json)
        zoom_in_action.triggered.connect(lambda: self.view.zoom(1.25))
        zoom_out_action.triggered.connect(lambda: self.view.zoom(0.8))
        reset_zoom_action.triggered.connect(self.view.reset_zoom)
        self.threshold_slider.valueChanged.connect(self._on_threshold_preview)
        self.threshold_slider.sliderReleased.connect(lambda: self._on_threshold_change(self.threshold_slider.value()))
        self.fill_checkbox.stateChanged.connect(self._on_fill_toggle)

    def _on_threshold_preview(self, val):
        self.threshold = val
        self.threshold_label.setText(f"Threshold: {val}")

    def _on_threshold_change(self, val):
        self.threshold = val
        self.threshold_label.setText(f"Threshold: {val}")
        self.relabel_zones()

    def _on_fill_toggle(self, state):
        self.fill = state == Qt.Checked
        self.relabel_zones()

    def open_svg(self):
        path, _ = QFileDialog.getOpenFileName(self, "Open SVG", "", "SVG Files (*.svg)")
        if path:
            self.load_svg(path)

    def load_svg(self, filepath):
        if not os.path.exists(filepath):
            QMessageBox.critical(self, "Error", "File does not exist.")
            return

        self.scene.clear()
        self.labels.clear()
        self.svg_filepath = filepath
        self.svg_renderer = QSvgRenderer(filepath)

        if not self.svg_renderer.isValid():
            QMessageBox.critical(self, "Error", "Invalid SVG.")
            return

        svg_size = self.svg_renderer.defaultSize()
        if svg_size.width() == 0 or svg_size.height() == 0:
            QMessageBox.critical(self, "Error", "SVG size invalid.")
            return

        self.svg_item = QGraphicsSvgItem(filepath)
        self.svg_item.setZValue(0)
        self.scene.addItem(self.svg_item)
        self.scene_svg_rect = QRectF(QPointF(0, 0), QSizeF(svg_size))
        self.scene.setSceneRect(self.scene_svg_rect)

        self.raster_img, self.raster_scale = self.rasterize_svg(svg_size)
        self.relabel_zones()

    def rasterize_svg(self, svg_size):
        max_dim = 2048
        scale = min(max_dim / svg_size.width(), max_dim / svg_size.height(), 1.0)
        img_w = int(svg_size.width() * scale)
        img_h = int(svg_size.height() * scale)
        image = QImage(img_w, img_h, QImage.Format_ARGB32)
        image.fill(Qt.white)
        painter = QPainter(image)
        self.svg_renderer.render(painter)
        painter.end()
        return image, scale

    def detect_zones(self, qimage, threshold_val):
        from PIL import Image
        ptr = qimage.bits()
        ptr.setsize(qimage.byteCount())
        arr = np.array(ptr).reshape(qimage.height(), qimage.width(), 4)
        pil_img = Image.fromarray(cv2.cvtColor(arr, cv2.COLOR_BGRA2RGB))

        seg_params = get_segmentation_presets()["Preset 1"]
        seg_params["window_size"] = max(15, threshold_val | 1)

        class AppStub:
            def __init__(self):
                self.seg_params = seg_params
                self.zone_label_positions = None
                self.zone_labels = {}
                self.zone_colors = {}
                self.label_map = None
                self.image = pil_img.convert("L")
                self.show_zone_numbers = False
                def no_op(*a, **kw): pass
                self.segmentation = type("SegmentationStub", (), {
                    "refresh_segmented_preview": no_op,
                    "_save_segmentation_settings": no_op
                })()
                self.last_seg_pil = None
                self.last_orig_pil = self.image
                self.push_history = no_op
                def log(*a, **kw): pass
                self.log_to_terminal = log
                self.history = []
                self.redo_stack = []

        app = AppStub()
        logic = SegmentationLogic(app)
        logic.segment_image(app.image)

        positions = app.zone_label_positions
        return [QPointF(xy[0] / self.raster_scale, xy[1] / self.raster_scale) for xy in positions.values()]

    def relabel_zones(self):
        for label in self.labels:
            self.scene.removeItem(label)
        self.labels.clear()
        centroids = self.detect_zones(self.raster_img, self.threshold)
        for i, pt in enumerate(centroids, 1):
            zone_id = i
            fill_color = self.palette.get_zone_color(zone_id)
            if fill_color:
                ellipse = self.scene.addEllipse(pt.x() - 8, pt.y() - 8, 16, 16)
                ellipse.setBrush(fill_color)
                ellipse.setPen(Qt.NoPen)
                ellipse.setZValue(5)
            label = ZoneLabel(str(zone_id), pt)
            label.setPos(pt)
            self.scene.addItem(label)
            self.labels.append(label)
        self.setWindowTitle(f"SVG Zone Labeler — {len(centroids)} zones")

    def export_json(self):
        if not self.labels:
            return
        path, _ = QFileDialog.getSaveFileName(self, "Export Zone JSON", "", "JSON Files (*.json)")
        if not path:
            return
        data = {label.toPlainText(): [round(label.pos().x(), 2), round(label.pos().y(), 2)] for label in self.labels}
        with open(path, "w") as f:
            json.dump(data, f, indent=2)
        print(f"[INFO] Exported {len(data)} zones to {path}")


def main():
    app = QApplication(sys.argv)
    win = SvgZoneLabeler()
    win.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
