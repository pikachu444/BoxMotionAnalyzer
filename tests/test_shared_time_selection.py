"""Run the same fixed vectors used by the isolated wheel check."""
from pathlib import Path
import runpy


def test_fixed_kernel_contract():
    runpy.run_path(str(Path(__file__).parent / "fixtures" / "shared_time_kernel_contract.py"))
