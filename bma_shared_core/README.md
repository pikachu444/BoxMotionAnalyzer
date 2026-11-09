# BoxMotionAnalyzer shared core

Last Reviewed: 2026-11-09

`nearest_sample_position(times_sec, target_sec)` selects the position of an
actual sample in a finite, strictly increasing time axis measured in seconds.
Exact ties select the earlier sample. Empty input or an out-of-range target
returns `None`. Invalid input raises `ValueError`. Axis validation is linear.

The package uses Python 3.10 or later and NumPy 1.24 or later. Consumers keep
their own event alignment, gap, frame mapping, and metadata rules. See
[consumer contracts](https://github.com/pikachu444/BoxMotionAnalyzer/issues/158)
for the time kernel and the distinct row and frame profiles.

Version `0.1.0.dev0` is a local build candidate. Publication requires owner
approval of the distribution rights and release metadata.
