"""TinForge Main Application."""

import sys
from pathlib import Path
from typing import Optional

from src.core.triangulation import DelaunayTriangulator
from src.parsers.csv_parser import CSVParser
from src.parsers.pdf_parser import PDFParser
from src.exporters.topcon_exporter import TopconExporter
from src.exporters.licai_exporter import LicaiExporter


class TinForgeApp:
    """Main TinForge application controller."""
    
    def __init__(self):
        self.csv_parser = CSVParser()
        self.pdf_parser = PDFParser()
        self.topcon_exporter = TopconExporter()
        self.licai_exporter = LicaiExporter()
    
    def process_survey_file(self, input_file: str) -> Optional[object]:
        """
        Process survey point file and create TIN.
        
        Args:
            input_file: Path to survey point file (CSV, TXT, or PDF)
            
        Returns:
            TINModel object or None on error
        """
        file_path = Path(input_file)
        
        if not file_path.exists():
            print(f"Error: File not found: {input_file}")
            return None
        
        try:
            # Determine file type and parse
            if file_path.suffix.lower() in ['.csv', '.txt']:
                print(f"Parsing CSV/TXT file: {input_file}")
                points = self.csv_parser.parse(input_file)
            elif file_path.suffix.lower() == '.pdf':
                print(f"Parsing PDF file: {input_file}")
                points = self.pdf_parser.parse(input_file)
            else:
                print(f"Error: Unsupported file format: {file_path.suffix}")
                return None
            
            print(f"Loaded {len(points)} points")
            
            # Generate TIN using Delaunay triangulation
            print("Generating TIN surface...")
            triangulator = DelaunayTriangulator(points)
            tin_model = triangulator.triangulate()
            
            # Print statistics
            stats = triangulator.get_statistics()
            print(f"\nTIN Generated:")
            print(f"  Points: {stats['point_count']}")
            print(f"  Triangles: {stats['triangle_count']}")
            print(f"  Area: {stats['area']:.2f} sq units")
            print(f"  Bounds: X[{stats['bounds']['x_min']:.2f}, {stats['bounds']['x_max']:.2f}] "
                  f"Y[{stats['bounds']['y_min']:.2f}, {stats['bounds']['y_max']:.2f}] "
                  f"Z[{stats['bounds']['z_min']:.2f}, {stats['bounds']['z_max']:.2f}]")
            
            return tin_model
        
        except Exception as e:
            print(f"Error processing file: {e}")
            return None
    
    def export_to_topcon(self, tin_model: object, output_file: str, format_type: str = 'tp3') -> bool:
        """
        Export TIN to Topcon format.
        
        Args:
            tin_model: TINModel object
            output_file: Output file path
            format_type: 'tp3', 'tin', or 'xml'
            
        Returns:
            True if successful
        """
        try:
            if format_type == 'tp3':
                self.topcon_exporter.export_tp3(tin_model, output_file)
            elif format_type == 'tin':
                self.topcon_exporter.export_tin(tin_model, output_file)
            elif format_type == 'xml':
                self.topcon_exporter.export_xml_landxml(tin_model, output_file)
            else:
                print(f"Error: Unknown Topcon format: {format_type}")
                return False
            
            print(f"Exported to Topcon {format_type.upper()}: {output_file}")
            return True
        
        except Exception as e:
            print(f"Error exporting to Topcon: {e}")
            return False
    
    def export_to_licai(self, tin_model: object, output_file: str, format_type: str = 'tin') -> bool:
        """
        Export TIN to Licai format.
        
        Args:
            tin_model: TINModel object
            output_file: Output file path
            format_type: 'tin', 'dat', or 'xyz'
            
        Returns:
            True if successful
        """
        try:
            if format_type == 'tin':
                self.licai_exporter.export_tin(tin_model, output_file)
            elif format_type == 'dat':
                self.licai_exporter.export_dat(tin_model, output_file)
            elif format_type == 'xyz':
                self.licai_exporter.export_xyz(tin_model, output_file)
            else:
                print(f"Error: Unknown Licai format: {format_type}")
                return False
            
            print(f"Exported to Licai {format_type.upper()}: {output_file}")
            return True
        
        except Exception as e:
            print(f"Error exporting to Licai: {e}")
            return False


def main():
    """Command line interface for TinForge."""
    app = TinForgeApp()
    
    print("""\n
╔═══════════════════════════════════════════════╗
║        🏗️  TinForge - Construction TIN Tool   ║
║   GPS Data → Machine Control Ready Files     ║
╚═══════════════════════════════════════════════╝\n""")
    
    # Example usage
    if len(sys.argv) > 1:
        input_file = sys.argv[1]
        tin_model = app.process_survey_file(input_file)
        
        if tin_model:
            # Export to both formats
            output_name = Path(input_file).stem
            
            app.export_to_topcon(tin_model, f"{output_name}_topcon.tin", 'tin')
            app.export_to_licai(tin_model, f"{output_name}_licai.tin", 'tin')
            
            print("\n✅ Processing complete!")
    else:
        print("Usage: python -m src.app <survey_file.csv>")
        print("\nSupported input formats: CSV, TXT, PDF")
        print("Supported output formats: Topcon (.tp3, .tin, .xml), Licai (.tin, .dat, .xyz)")


if __name__ == '__main__':
    main()
