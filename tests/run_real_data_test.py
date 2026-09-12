"""Execute and validate the TinForge real survey workflow."""

from pathlib import Path
import sys


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from src.process_real_data import format_bytes
from src.test_real_workflow import run_real_workflow


def main() -> int:
    """Run the workflow and verify its outputs."""
    results = run_real_workflow()
    output_files = results["output_files"]
    total_input_size = sum(item["file_size"] for item in results["inputs"])
    total_output_size = sum(path.stat().st_size for path in output_files.values())

    print("TinForge real survey workflow validation")
    print("=======================================")
    print()
    print("Input files:")
    for item in results["inputs"]:
        print(
            f"  - {item['file_path'].name}: "
            f"{format_bytes(item['file_size'])}, "
            f"{item['summary']['point_count']} extracted points"
        )

    print()
    print("Generated files:")
    missing = []
    for label, output_path in output_files.items():
        exists = output_path.exists() and output_path.stat().st_size > 0
        status = "OK" if exists else "MISSING"
        print(f"  - {label}: {output_path.name} [{status}] {format_bytes(output_path.stat().st_size) if output_path.exists() else '0 B'}")
        if not exists:
            missing.append(str(output_path))

    print()
    print(f"Combined points: {len(results['combined_points'])}")
    print(f"Triangles created: {results['tin_statistics']['triangle_count']}")
    print(
        "Coordinate bounds: "
        f"X[{results['tin_statistics']['bounds']['x_min']:.2f}, {results['tin_statistics']['bounds']['x_max']:.2f}] "
        f"Y[{results['tin_statistics']['bounds']['y_min']:.2f}, {results['tin_statistics']['bounds']['y_max']:.2f}] "
        f"Z[{results['tin_statistics']['bounds']['z_min']:.3f}, {results['tin_statistics']['bounds']['z_max']:.3f}]"
    )
    print(f"Input size total: {format_bytes(total_input_size)}")
    print(f"Output size total: {format_bytes(total_output_size)}")
    print(f"Report: {results['report_path']}")
    print(f"Validation summary: {results['validation']}")

    if missing:
        print()
        print("Validation failed. Missing outputs:")
        for path in missing:
            print(f"  - {path}")
        return 1

    if len(results["combined_points"]) < 3 or results["tin_statistics"]["triangle_count"] < 1:
        print("Validation failed. Insufficient points or triangles were generated.")
        return 1

    print()
    print("Full test report:")
    print(results["report_text"])
    print("Validation successful.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
