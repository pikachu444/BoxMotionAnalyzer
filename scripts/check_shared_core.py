"""Verify the source receipt and, optionally, the contents of a built wheel."""
import argparse
import csv
from email import policy
from email.parser import BytesParser
import hashlib
import io
import json
from pathlib import Path
from zipfile import ZipFile


PACKAGE_FILES = {"__init__.py", "time_selection.py", "pyproject.toml", "README.md"}
RUNTIME_FILES = {"__init__.py", "time_selection.py"}
KERNEL_SHA256 = "824bf08d3852dc25b2e1856ebf55dbd14e527e7dfbb93519d40cfb013190b970"


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def verify_source(source):
    receipt = json.loads((source / "SOURCE_RECEIPT.json").read_bytes())
    hashes = receipt["files"]
    if set(hashes) != PACKAGE_FILES or hashes["time_selection.py"] != KERNEL_SHA256:
        raise ValueError("Receipt does not declare the fixed TIME-KERNEL/1 source files")
    for filename, expected in hashes.items():
        data = (source / filename).read_bytes()
        if b"\r" in data or sha256(data) != expected:
            raise ValueError(f"Source drift in {filename}")
    return receipt


def verify_wheel(source, wheel, version):
    dist_info = f"bma_shared_core-{version}.dist-info"
    allowed = {f"bma_shared_core/{filename}" for filename in RUNTIME_FILES}
    allowed.update(f"{dist_info}/{name}" for name in ("METADATA", "WHEEL", "RECORD", "top_level.txt"))
    with ZipFile(wheel) as archive:
        entries = archive.namelist()
        if len(entries) != len(allowed) or set(entries) != allowed:
            raise ValueError("Wheel entries differ from the package allowlist")
        record = archive.read(f"{dist_info}/RECORD").decode("utf-8")
        if sorted(row[0] for row in csv.reader(io.StringIO(record))) != sorted(allowed):
            raise ValueError("Wheel RECORD differs from the package allowlist")
        for filename in RUNTIME_FILES:
            if archive.read(f"bma_shared_core/{filename}") != (source / filename).read_bytes():
                raise ValueError(f"Wheel source drift in {filename}")
        metadata = BytesParser(policy=policy.default).parsebytes(archive.read(f"{dist_info}/METADATA"))
        expected = {
            "Name": "bma-shared-core",
            "Version": version,
            "Summary": "Policy-free selection of actual recorded samples",
            "Requires-Python": ">=3.10",
            "Requires-Dist": "numpy>=1.24",
            "Description-Content-Type": "text/markdown",
        }
        if (set(metadata.keys()) != set(expected) | {"Metadata-Version"}
                or any(metadata.get_all(key) != [value] for key, value in expected.items())
                or metadata.get_payload().replace("\r\n", "\n") != (source / "README.md").read_text(encoding="utf-8")):
            raise ValueError("Wheel project metadata differs from the declared package")
        if archive.read(f"{dist_info}/top_level.txt") != b"bma_shared_core\n":
            raise ValueError("Wheel declares unexpected top-level imports")
    return {"wheel_sha256": sha256(wheel.read_bytes()), "entries": sorted(allowed)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=Path(__file__).resolve().parents[1] / "bma_shared_core")
    parser.add_argument("--wheel", type=Path)
    args = parser.parse_args()
    receipt = verify_source(args.source)
    report = {"contract": receipt["kernel_contract"], "package_version": receipt["package_version"],
              "source_sha256": receipt["files"]}
    if args.wheel:
        report.update(verify_wheel(args.source, args.wheel, receipt["package_version"]))
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
