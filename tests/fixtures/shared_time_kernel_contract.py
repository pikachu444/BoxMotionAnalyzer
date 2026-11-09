import json
import numpy as np
from bma_shared_core import nearest_sample_position

SUCCESS = [
    ([], 0., None),
    ([0.125], 0.125, 0),
    ([0.125], 0., None),
    ([0.125], 0.25, None),
    ([0., 0.125, 0.25], 0., 0),
    ([0., 0.125, 0.25], 0.125, 1),
    ([0., 0.125, 0.25], 0.25, 2),
    ([0., 0.125, 0.25], 0.03125, 0),
    ([0., 0.125, 0.25], 0.09375, 1),
    ([0., 0.125, 0.25], 0.0625, 0),
    ([0., 0.125, 0.25], 0.1875, 1),
    ([0., 0.125, 0.25], -0.03125, None),
    ([0., 0.125, 0.25], 0.28125, None),
    ([10., 10.03125, 10.0625], 10.03125, 1),
    (["0", "0.125"], "0.0625", 0),
    ([False, True], True, 1),
]
INVALID = [
    ([], np.nan),
    ([[0., 0.125]], 0.),
    (np.asarray(0.125), 0.125),
    ([0., 0.], 0.),
    ([0.125, 0.], 0.),
    ([0., np.nan], 0.),
    ([0., np.inf], 0.),
    ([0., 0.125], np.nan),
    ([0., 0.125], np.inf),
    ([0., 0.125], "invalid"),
    (["invalid"], 0.),
]
for times, target, expected in SUCCESS:
    actual = nearest_sample_position(times, target)
    assert actual == expected, (times, target, expected, actual)
    assert actual is None or type(actual) is int
for times, target in INVALID:
    try:
        nearest_sample_position(times, target)
    except ValueError:
        pass
    else:
        raise AssertionError(("Expected ValueError", times, target))
base = np.asarray([0., 0.0625, 0.125, 0.1875, 0.25])
before = base.copy()
view = base[::2]
view.setflags(write=False)
assert nearest_sample_position(view, 0.125) == 1
np.testing.assert_array_equal(base, before)
print(json.dumps({"contract": "TIME-KERNEL/1", "success_vectors": len(SUCCESS),
                  "invalid_vectors": len(INVALID), "readonly_view_unchanged": True}))
