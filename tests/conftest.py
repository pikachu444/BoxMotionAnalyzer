"""Attach evidence scope to each JUnit testcase; do not run extra analysis."""
from src.simulation.public_validation_summary import evidence_level


def pytest_collection_modifyitems(items):
    for item in items:
        item.user_properties.append(('evidence_level', evidence_level(item.nodeid.split('::')[0], item.name)))
        item.user_properties.append(('nodeid', item.nodeid))


def pytest_addoption(parser):
    parser.addoption('--pub11-inventory', help='Write collection-only node inventory to a new file')


def pytest_sessionfinish(session, exitstatus):
    path = session.config.getoption('--pub11-inventory')
    if path:
        from src.analysis.regression.contracts import envelope, write_new_json
        if not session.config.option.collectonly or exitstatus != 0 or not session.items:
            raise ValueError('Required inventory needs a successful nonempty collection-only execution.')
        write_new_json(path, envelope('RequiredTests', nodeids=[item.nodeid for item in session.items]))
