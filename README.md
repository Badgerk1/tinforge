# TinForge 🏗️

**GPS TIN File Converter for Construction Site Preparation**

Convert surveyed land data into machine-control ready TIN files for Topcon and Licai systems. Generate design surfaces from survey points and prepare equipment guidance data for dozers, graders, and excavators.

## Overview

TinForge streamlines the construction site preparation workflow:

1. **Survey Data Input** → Accept GPS survey points (CSV, TXT, PDF coordinates)
2. **TIN Generation** → Create triangulated irregular networks using Delaunay triangulation
3. **Design Integration** → Add buildings, parking lots, drainage, roads to the surface
4. **Format Export** → Convert to Topcon (.tp3, .tin) or Licai (.tin, .dat) formats
5. **Machine Control** → Output GPS coordinates ready for equipment guidance systems

## Features

- ✅ Import surveyed points from multiple formats (CSV, TXT, coordinate data)
- ✅ Delaunay triangulation for optimal TIN mesh generation
- ✅ Design surface creation with breaklines and boundaries
- ✅ Cut/fill volume calculations between existing and design surfaces
- ✅ Export to Topcon machine control formats (.tp3, .tin, .xml/LandXML)
- ✅ Export to Licai system formats (.tin, .dat)
- ✅ PDF report generation with surface profiles and analysis
- ✅ 3D visualization of surfaces
- ✅ Interactive design editor

## Workflow

```
Surveyed Points (GPS)
    ↓
[TinForge Processing]
    ├── Parse coordinates
    ├── Validate data
    ├── Generate TIN mesh
    └── Apply design elements
    ↓
Export Formats
    ├── Topcon (.tp3, .tin, .xml)
    └── Licai (.tin, .dat)
    ↓
Machine Control Systems
    ├── Dozers
    ├── Graders
    └── Excavators
```

## Project Structure

```
tinforge/
├── src/
│   ├── core/
│   │   ├── triangulation.py      # Delaunay triangulation engine
│   │   ├── tin_model.py          # TIN data structure
│   │   └── surface.py            # Surface mesh operations
│   ├── parsers/
│   │   ├── point_parser.py       # Parse survey point data
│   │   ├── pdf_parser.py         # Extract coordinates from PDFs
│   │   └── csv_parser.py         # Handle CSV/TXT point files
│   ├── exporters/
│   │   ├── topcon_exporter.py    # Topcon .tp3, .tin format
│   │   ├── licai_exporter.py     # Licai .tin, .dat format
│   │   ├── xml_exporter.py       # LandXML format
│   │   └── pdf_reporter.py       # PDF reports & profiles
│   ├── design/
│   │   ├── design_editor.py      # Add design elements
│   │   ├── breaklines.py         # Ridges, edges, boundaries
│   │   └── cut_fill.py           # Cut/fill calculations
│   ├── viz/
│   │   └── viewer_3d.py          # 3D surface visualization
│   └── app.py                    # Main application
├── tests/
├── docs/
│   ├── TOPCON_FORMAT.md
│   ├── LICAI_FORMAT.md
│   └── USER_GUIDE.md
├── requirements.txt
└── setup.py
```

## Tech Stack

- **Backend**: Python 3.9+
- **Triangulation**: SciPy, NumPy
- **Visualization**: Three.js / Babylon.js (frontend)
- **Web Framework**: Flask or FastAPI
- **Geospatial**: GDAL, Shapely (optional)
- **PDF Processing**: PyPDF2, pdfplumber

## Installation

```bash
git clone https://github.com/Badgerk1/tinforge.git
cd tinforge
pip install -r requirements.txt
python src/app.py
```

## Usage

### Command Line

```bash
# Import survey points and create TIN
tinforge import points.csv --format csv --output survey.tin

# Export to Topcon format
tinforge export survey.tin --format topcon --output machine_control.tp3

# Export to Licai format
tinforge export survey.tin --format licai --output machine_control.tin

# Generate PDF report
tinforge report survey.tin --format pdf --output report.pdf
```

### Web Interface

1. Upload survey point file
2. Configure coordinate system
3. Create/edit design surface
4. Select export format (Topcon/Licai)
5. Download machine-ready files

## Supported Formats

### Input
- CSV/TXT point lists (X, Y, Z, ID)
- PDF coordinate reports
- Topcon survey data exports
- Licai survey data exports

### Output
- **Topcon**: .tp3, .tin, .xml (LandXML)
- **Licai**: .tin (text format), .dat
- **Reports**: PDF with profiles, cross-sections, volume calculations

## Documentation

- [Topcon Format Specification](docs/TOPCON_FORMAT.md)
- [Licai Format Specification](docs/LICAI_FORMAT.md)
- [User Guide](docs/USER_GUIDE.md)
- [API Reference](docs/API.md)

## Contributing

Contributions welcome! Please read [CONTRIBUTING.md](CONTRIBUTING.md) first.

## License

MIT License - See [LICENSE](LICENSE) file

## Support

For issues, questions, or feature requests, please open an issue on GitHub.

---

**Built for construction professionals who need precision site preparation.** 🚜
