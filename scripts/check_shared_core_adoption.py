"""Run the fixed Draft 2020-12 examples with development-only jsonschema."""
import json
from pathlib import Path

from jsonschema import Draft202012Validator


def main():
    root = Path(__file__).resolve().parents[1]
    schema = json.loads((root / "docs/shared_core/adoption.schema.json").read_bytes())
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema)
    pending = dict(
        schema_version=1,
        canonical_repository="https://github.com/pikachu444/BoxMotionAnalyzer",
        canonical_commit=None,
        package_version="0.1.0.dev0",
        kernel_contract="TIME-KERNEL/1",
        consumer_profile="FRAME-1/1",
        consumer_baseline=None,
        adapter_version=None,
        adopted_kernel_sha256=None,
        evidence=[],
        status="pending",
        approved_by=None,
        previous_adoption=None,
        rollback_dependency_pin=None,
    )
    approved = dict(
        pending, canonical_commit="a" * 40, consumer_baseline="consumer-baseline",
        adapter_version="FRAME-1/1", adopted_kernel_sha256="b" * 64,
        evidence=["synthetic-approval-example"], status="approved",
        approved_by="review-owner", rollback_dependency_pin="not-installed",
    )
    validator.validate(pending)
    validator.validate(approved)
    validator.validate(dict(approved, status="rolled_back", evidence=["restored-baseline-test"]))
    invalid = [
        dict(approved, **{field: None})
        for field in ("canonical_commit", "consumer_baseline", "adapter_version",
                      "adopted_kernel_sha256", "approved_by", "rollback_dependency_pin")
    ]
    invalid.extend([
        dict(approved, canonical_commit="a" * 39),
        dict(approved, adopted_kernel_sha256="b" * 63),
        dict(approved, status="unknown"),
        dict(approved, evidence=[]),
        dict(approved, evidence=[""]),
        dict(approved, extra=True),
        dict(pending, status="rolled_back"),
        {key: value for key, value in pending.items() if key != "previous_adoption"},
    ])
    for record in invalid:
        if validator.is_valid(record):
            raise AssertionError("Invalid adoption example was accepted")
    print(json.dumps({"draft": "2020-12", "valid": 3, "invalid": len(invalid)}))


if __name__ == "__main__":
    main()
