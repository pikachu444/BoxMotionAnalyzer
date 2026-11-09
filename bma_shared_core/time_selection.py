"""Pure actual-sample selection; no alignment, gap or experimental policy."""
from collections.abc import Sequence
import numpy as np


def nearest_sample_position(times_sec: Sequence[float], target_sec: float) -> int | None:
    """Select an actual position in finite, strictly increasing seconds.

    Exact ties select the earlier time. Out-of-range and empty inputs return
    None. Invalid axes/targets raise ValueError. Inputs are never sorted,
    repaired or interpolated. Validation is linear in the number of samples.
    """
    try:
        target = float(target_sec)
        values = np.asarray(times_sec, dtype=float)
    except (TypeError, ValueError, OverflowError) as error:
        raise ValueError("Times and target must be real numbers") from error
    if not np.isfinite(target):
        raise ValueError("Target must be finite")
    if values.ndim != 1 or not np.isfinite(values).all():
        raise ValueError("Times must be a finite one-dimensional array")
    if len(values) > 1 and np.any(np.diff(values) <= 0):
        raise ValueError("Times must be strictly increasing")
    if not len(values) or target < values[0] or target > values[-1]:
        return None
    right = int(np.searchsorted(values, target, side="left"))
    if right == 0 or values[right] == target:
        return right
    return right - 1 if target - values[right - 1] <= values[right] - target else right
