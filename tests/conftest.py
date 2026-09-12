"""Attach evidence scope to each JUnit testcase; do not run extra analysis."""
from src.simulation.public_validation_summary import evidence_level


def pytest_collection_modifyitems(items):
    for item in items:
        item.user_properties.append(('evidence_level', evidence_level(item.nodeid.split('::')[0], item.name)))
