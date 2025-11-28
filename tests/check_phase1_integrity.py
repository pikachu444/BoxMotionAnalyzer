import os
import ast
import sys

def check_symbol_in_file(filepath, symbol_name, symbol_type='class'):
    """
    Parses a python file and checks if a specific symbol (class or function) exists.
    symbol_type: 'class', 'function', or 'assign' (for variables/constants)
    """
    if not os.path.exists(filepath):
        print(f"[FAIL] File not found: {filepath}")
        return False

    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            tree = ast.parse(f.read())
    except Exception as e:
        print(f"[FAIL] Could not parse {filepath}: {e}")
        return False

    found = False
    for node in ast.walk(tree):
        if symbol_type == 'class' and isinstance(node, ast.ClassDef):
            if node.name == symbol_name:
                found = True
                break
        elif symbol_type == 'function' and isinstance(node, ast.FunctionDef):
            if node.name == symbol_name:
                found = True
                break
        elif symbol_type == 'assign' and isinstance(node, ast.Assign):
            # Check for global variables/constants
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == symbol_name:
                    found = True
                    break

    if found:
        print(f"[PASS] Found {symbol_type} '{symbol_name}' in {filepath}")
        return True
    else:
        print(f"[FAIL] {symbol_type} '{symbol_name}' NOT found in {filepath}")
        return False

def verify_phase1_integrity():
    checks = [
        # Analysis Module
        ('src/analysis/main_window.py', 'MainApp', 'class'),
        ('src/analysis/core/pipeline_controller.py', 'PipelineController', 'class'),
        ('src/analysis/core/data_loader.py', 'DataLoader', 'class'),
        ('src/analysis/ui/widget_raw_data_processing.py', 'WidgetRawDataProcessing', 'class'),

        # Visualization Module
        ('src/launcher.py', 'LauncherWindow', 'class'),
        ('src/config/config_visualization.py', 'BOX_SIZE', 'assign'),
        ('src/config/config_visualization.py', 'STYLE', 'assign'),

        # Utils
        ('src/utils/header_converter.py', 'convert_to_multi_header', 'function'),
        ('src/utils/make_testdata.py', 'main', 'function'), # Changed from make_testdata to main
    ]

    all_passed = True
    print("Starting Phase 1 Static Integrity Check...\n")

    for filepath, symbol, sym_type in checks:
        if not check_symbol_in_file(filepath, symbol, sym_type):
            all_passed = False

    print("\n" + "="*40)
    if all_passed:
        print("VERIFICATION SUCCESS: All critical symbols verified in new locations.")
        sys.exit(0)
    else:
        print("VERIFICATION FAILED: Some files or symbols are missing.")
        sys.exit(1)

if __name__ == '__main__':
    verify_phase1_integrity()
