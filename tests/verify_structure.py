import os
import sys

def verify_structure():
    expected_files = {
        "src/analysis/main_window.py",
        "src/analysis/ui/widget_raw_data_processing.py",
        "src/analysis/ui/widget_results_analyzer.py",
        "src/analysis/core/pipeline_controller.py",
        "src/analysis/core/data_loader.py",
        "src/utils/header_converter.py",
        "src/launcher.py",
        "src/config/config_visualization.py",
        "src/utils/make_testdata.py",
        "archive/unused/data_processing_window.py",
        "archive/unused/main.py",
        "docs/README.md",
        "docs/visualization_AGENTS.md",
        "docs/visualization_README.md",
        "docs/launcher_layout_sketch.txt",
        "docs/changeheader.txt"
    }

    missing_files = []
    for filepath in expected_files:
        if not os.path.exists(filepath):
            missing_files.append(filepath)

    if missing_files:
        print("Missing files:")
        for f in missing_files:
            print(f" - {f}")
        sys.exit(1)
    else:
        print("All files verified at expected locations.")
        sys.exit(0)

if __name__ == "__main__":
    verify_structure()
