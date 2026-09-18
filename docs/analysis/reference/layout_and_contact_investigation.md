# Whole-layout and missing-corner investigations

Last Reviewed: 2026-09-18

Investigated main `1216c5dc5f601ee405d3ce57c0f0f48989572aa7` after PRs
#127–#132. The user's correction of #116 and normal-path requirement for #120
supersede the original proposals. These are public synthetic software checks,
not independent physical calibration (#104).

## #116: remove a demonstrated false rejection

The old profile loader rejected a face with exactly three collinear markers,
while allowing one, two, four or more. That prevented Import JSON, preview and
generation even when the other faces supplied enough information for the actual
pose fit. No extension of that restriction is warranted.

The pre-change probe placed FRONT markers at (-60,0,40), (-20,0,40),
(20,0,40), (60,0,40) mm on the public 200×120×80 mm example. With F4 missing
throughout, the remaining three FRONT markers and the other public markers
recovered all 50 declared poses. Loading precisely that remaining 17-marker
geometry as JSON failed with `Three-marker face is collinear.`

The change removes only that condition. Finite coordinates/dimensions, assigned
face bounds, 1 mm separation, marker names and public-example immutability remain
checked. Accepted profile hashes, conventions and serialization are unchanged.
Import is not certification: the production solver continues to check the whole
available marker set, including missing/unknown faces and local constraint rank.
No stress flag, registration procedure, new version or extra UI is introduced.

After the change, direct public `write_observations` exports with three, four and
five collinear FRONT markers pass the normal CSV reader, parser and actual Raw
optimizer. The motion is independently declared as Rz(10+20t degrees), with
origin (17+20t, 200−5t, 11+3t) mm, t=0…0.49 s in 0.01 s increments.
Analysis cannot open evaluator truth or corruption metadata. Coordinates and
hashes are retained unchanged.

| FRONT count | Maximum origin error (mm) | Maximum rotation error (degrees) |
| --- | ---: | ---: |
| 3 | 0.000108254 | 0.000379102 |
| 4 | 0.000412808 | 0.000611727 |
| 5 | 0.000115304 | 0.000266307 |

These satisfy the existing 0.1 mm / 0.1 degree noise-free mechanics bounds.
The independently calculated eight corners are also checked (0.4 mm bound,
allowing those origin/rotation bounds at the 123.3 mm corner radius). Profiles
containing only the collinear FRONT markers remain `UnidentifiableGeometry`,
with all pose/corner values unavailable. Successful cases and rank checks do not
prove global uniqueness, robustness under arbitrary occlusion/noise or real
tracking accuracy.

Actual Qt interaction imports and previews the three-marker face, generates a
63-sample MuJoCo observation CSV and opens it in Step 1 at 1510×800 logical /
DPR 1.25. The same test preserves cancellation, invalid-input handling, overwrite
refusal and retained successful output after an export error. Existing controls
and layout are unchanged. The preview is Matplotlib; these screenshots are not a
new VTK rendering claim. Numeric Raw recovery is tested separately above.

Local checks: 29 core tests, 122 validation/corruption contract tests and five actual GUI tests passed. Retained
evidence is in `tmp/issue116/` (pre-change probe, input hashes, recovery reports,
GUI screenshots and JUnit). Reproduce the retained numerical regression with
`python -m pytest -q tests/test_collinear_profile_recovery.py`; run
`tests/test_simulation_marker_export_gui.py` with `QT_SCALE_FACTOR=1.25` for widgets.
The required Windows lane runs both. Final independent review and exact-head
CI/merge status are recorded in the linked PR.

## #120: investigation complete, original implementation deferred

The original reproduction changes one saved C8 height to NaN while retaining the
previous contact summary. This proves rejection of inconsistent saved evidence;
it does not prove that losing a marker removes a box corner in normal analysis.

`PoseOptimizer` transforms all eight corners from a single position/rotation and
the declared dimensions. Some missing markers can still yield all corners.
Insufficient whole-pose constraints clear all pose/corner values. The earlier
all-marker-loss crash is already fixed in #115 / PR #127: rows remain, geometric
metrics use valid rows, and whole-record contact is explicitly unavailable.

Seven public-path probes used `write_observations`, the normal reader/parser,
actual Raw optimizer, postprocessor, `.proc` writer/reopening and ComparisonModel:
healthy; one marker missing after contact; all markers missing before or after
contact; only two markers remaining; and 2x resampling for partial/all loss.
The 72-row input uses an identity rotation and origin Y=60+max(0,
4903.325×(0.4²−t²)) mm on the same public box. The original rows are retained;
resampling produces 143 rows. Each row has either all 24 finite corner coordinates
or none. Maximum original-row corner error is 0.000357051 mm and maximum rotation
error is 0.000188134 degrees. Truth/event file reads are blocked during analysis.
Healthy/single-marker loss retains an impact result; whole-pose loss remains
`Unavailable`, including after disk I/O and resampling.

These generated captures do not record an operator contact choice; their
comparison correctly reports missing intent. They do **not** establish end-to-end
Match accuracy. The separate original saved-result mutation control gives Match
before mutation and Unclear afterward. Related checks: 57 passed; one optional
real-data test skipped because its input was unavailable. Independent code review
agreed and separately passed 41 contact tests. Local scripts/hashes/reports are
retained in `tmp/issue120/`; public findings are in
[the issue comment](https://github.com/pikachu444/BoxMotionAnalyzer/issues/120#issuecomment-5724511817).

Current contact analysis uses whole-record smoothing, extrema/height range and
late stable-contact evidence. Deleting its finite guard or cropping inputs would
not reproduce the recorded calculation. No isolated corner-loss generation
path was found; new policy/version/storage/UI are therefore deferred. This does
not prove that an earlier physical event can never be inferred after a later
tracking gap. Such a change needs a demonstrated user problem and justified
method/evidence, not the isolated NaN mutation alone. #120 stays unimplemented
under its original proposal, and #104 still needs independent real calibration.
