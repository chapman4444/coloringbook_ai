# ColoringBook AI

A PyQt5-based interactive zone labeler and coloring assistant for SVG artwork. This tool rasterizes SVGs, auto-detects coloring zones, places labels, and assigns colors from a palette manager.

---

## ✨ Features

- 🖼 Rasterizes SVGs and detects distinct coloring zones
- 🎯 Places numeric labels at the center of each zone
- 🎨 Built-in palette manager (sequential/random modes)
- 🧪 Adjustable threshold + fill preview
- 🧲 JSON export of zone coordinates
- 🔍 Zoom, pan, and real-time zone relabeling

---

## 📦 Requirements

Install Python packages with:

```bash
pip install -r requirements.txt
```

Or for Windows:

```bat
install_requirements.bat
```

---

## 🚀 Usage

```bash
python main.py
```

---

## 📁 Repository Structure

```
coloringbook_ai/
├── main.py
├── palette_manager.py
├── segmentation.py
├── install_requirements.bat
├── SVG/
│   ├── 00.svg
│   └── 01.svg
```

---

## 🧠 Future Plans

- SVG export with filled colors  
- AI-assisted coloring suggestions  
- Manual zone editing tools (lasso, brush, merge)

---

## 📜 License

MIT License — © 2025 chapman4444
