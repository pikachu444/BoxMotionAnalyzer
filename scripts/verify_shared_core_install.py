"""Build and test the wheel in separate, disposable Python environments."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys
from tempfile import TemporaryDirectory

from check_shared_core import verify_source, verify_wheel

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "bma_shared_core"
CONTRACT = ROOT / "tests/fixtures/shared_time_kernel_contract.py"
RUNTIME_CHECK = """
import hashlib, json, sys, sysconfig
from pathlib import Path
import numpy
import bma_shared_core

installed = Path(bma_shared_core.__file__).resolve().parent
site = Path(sysconfig.get_path("purelib")).resolve()
assert installed.parent == site
assert sys.flags.isolated and sys.prefix != sys.base_prefix
assert not any(
    line.strip() == "include-system-site-packages = true"
    for line in (Path(sys.prefix) / "pyvenv.cfg").read_text().splitlines()
)
for name in ("__init__.py", "time_selection.py"):
    assert (installed / name).read_bytes() == (Path(sys.argv[1]) / name).read_bytes()
assert bma_shared_core.__version__ == sys.argv[2]
print(json.dumps({
    "python": sys.version.split()[0], "numpy": numpy.__version__,
    "package_version": bma_shared_core.__version__,
    "location": "<runtime-site-packages>/bma_shared_core",
    "kernel_sha256": hashlib.sha256((installed / "time_selection.py").read_bytes()).hexdigest(),
}))
"""


def verify():
    receipt = verify_source(SOURCE)
    commands = []
    with TemporaryDirectory(prefix="bma-shared-core-") as folder:
        work = Path(folder)

        def run(executable, *args):
            result = subprocess.run(
                [executable, *args], cwd=work, text=True, encoding="utf-8",
                errors="replace", capture_output=True,
            )
            def redact(value):
                if value == RUNTIME_CHECK:
                    return "<installed-identity-probe>"
                return (str(value).replace(str(work), "<temp>").replace(str(ROOT), "<checkout>")
                        .replace(sys.executable, "<host-python>"))

            commands.append({
                "command": [redact(arg) for arg in (executable, *args)],
                "exit_code": result.returncode,
            })
            if result.returncode:
                raise RuntimeError(redact(result.stdout + result.stderr))
            return result.stdout

        package = work / SOURCE.name
        package.mkdir()
        for name in receipt["files"]:
            shutil.copyfile(SOURCE / name, package / name)

        def create_env(name):
            run(sys.executable, "-m", "venv", name)
            return work / name / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")

        build = create_env("build-env")
        run(build, "-m", "pip", "install", "build", "setuptools>=68", "wheel")
        tools = json.loads(run(
            build, "-I", "-c",
            "import json, sys, importlib.metadata as m; "
            "print(json.dumps(dict(python=sys.version.split()[0], "
            "**{p:m.version(p) for p in ('build','pip','setuptools','wheel')})))",
        ))
        run(build, "-m", "build", "--no-isolation", "--wheel", "--outdir", "artifacts", package)
        wheel, = (work / "artifacts").glob("*.whl")
        wheel_report = verify_wheel(SOURCE, wheel, receipt["package_version"])

        runtime = create_env("runtime-env")
        run(runtime, "-m", "pip", "install", wheel)
        run(runtime, "-m", "pip", "check")
        runtime_report = json.loads(run(runtime, "-I", "-c", RUNTIME_CHECK, package, receipt["package_version"]))
        fixture = work / "contract_vectors.py"
        shutil.copyfile(CONTRACT, fixture)
        vectors = json.loads(run(runtime, "-I", fixture))
        return {
            "status": "pass", "build_environment": tools, "wheel": wheel_report,
            "runtime_environment": runtime_report, "vectors": vectors, "commands": commands,
        }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = json.dumps(verify(), indent=2) + "\n"
    if args.output:
        args.output.write_text(report, encoding="utf-8")
    else:
        print(report, end="")


if __name__ == "__main__":
    main()
