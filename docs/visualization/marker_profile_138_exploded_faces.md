# Display-only exploded profile faces — #138 / PUB05

Last Reviewed: 2026-10-06

Current status, 2026-10-06: the user approved the final interactive mockup.
Production software and automatic verification passed final independent review.
Required clean-commit hosted CI gates merge; native follow-up stays open. Historical mockup review states
below describe their own revision, not current approval. Native external input
and actual OS125% remain unexecuted; real experiment validation is separate.


Plan Spec: ISTA6A-PLAN-20261001-v1

## User proposal and current state

The user proposed keeping the original box in the center and offsetting each
face with its markers. This explicitly supersedes the prior advice against
exploded geometry for this display mode. Main implemented a standalone review
prototype; production code, profile coordinates and export/analysis are unchanged.
The same formal independent reviewer has approved the final corrected new mode
with no outstanding P0/P1/P2. The final original FHD image has been shown and
user confirmation requested before production UI changes. Earlier formal
approval of the audited prototype is retained as historical evidence.

The user accepted the B angle/spacing direction after seeing its actual render
and requested a final readability review. Main corrected label/title occlusion
and leader crossings; final100/125% runs and independent UI-only review passed.

Two existing read-only Sol/xhigh advisors (`marker_visibility_a/b`) examined
actual renders and discussed the approach. No additional agents or writer work
were delegated. They initially favored isometric projection, then revised that
opinion after actual images: both recommend the original20°/30° Y-up orthographic
camera and the original55:45 splitter, which preserves the lower2D detail.
That was a limited two-angle comparison at one spacing, not an optimum search.
After the user challenged it, both advisors inspected the joint angle/spacing
variants and now recommend B: Y-up elevation25°, azimuth50°, roll30°, R1.0.
They report improved ID identification, not formal approval or native acceptance.

## Joint angle and spacing comparison

Main scanned208 geometry-only combinations, then608 including screen roll.
The same680×355 logical-pixel viewport and common scale were used; the latter
scan covers public18/32, elevation15/25/35/45/55, azimuth20/35/50/65/80,
roll0/30/60 and R ratios.75/1/1.25/1.5, plus the previous20/30/0 baseline.
These are deterministic display diagnostics, not fitting to experimental truth.

Sixteen actual Qt captures remeasured the scene after real annotation-aware Fit.
For32/default1280×960, the previous view has two different-face point pairs
within14 logical pixels (F2/L1, B7/R2) and5.94% summed pairwise frame overlap.
B has zero such pairs, zero same-face pairs and0% frame overlap. Increasing R
to1.25 at B's angle creates four same-face near pairs after Fit, so it was not
recommended. The14-pixel threshold is the existing display point-obstacle
diameter, not an approved physical tolerance. Polygon overlap is a diagnostic
sum, not union coverage or a readability pass.

Both read-only advisors checked actual default/FHD images and favor B over A
(25/65/30,R.75); C's additional gap shrinks the dense faces without improving
ID reading. They found remaining F4/F10 leader association and an18-profile
Right title over the selected B1 ring. The same formal UI reviewer independently
confirmed that the old32 selected B1 badge also covered B3/B10 disks.
Main fixed all three, using actual rendered marker/ring/badge/arrow paths
and a bounded two-label search when an unobstructed name occupies a needed slot.
No ID-specific exception or source coordinate displacement is used.

- [Angle/spacing/roll scan](mockups/marker_profile_138/angle_spacing_roll_scan/scan.json)
- [Sixteen actual comparison captures and measurements](mockups/marker_profile_138/angle_spacing_actual/evidence.json)
- [B FHD before final label correction](mockups/marker_profile_138/angle_spacing_actual/B-balanced-32-1920x1080.png)
- [Final visibility generator](mockups/marker_profile_138/finalize_exploded_visibility.py)

The final generator additionally checks direct ID clicks, Reset view to B,
mode switching and literal18 M2 source[38,-60,-18]/display[38,-200,-18]. It
checks all50 selected-layout renders per DPR, plus narrow top/bottom and invalid
B2/Y accessibility. Final results and the reviewer verdict are recorded below;
intermediate or failed attempts are not acceptance evidence.

## Final verified presentation

B uses the25°/50°/30° Y-up orthographic camera and R1.0. Main's final generator
SHA256 is `f987039755f51a50288d581a167a5e3821c187c11bc28c786b317a25890b8e46`.
Actual marker-circle and selected-ring extents, all badge rectangles and actual
leader paths are checked. Names use10pt at stable positions when selection
changes; selection adds a border and a9pt ring rather than larger text. A
bounded two-label relocation can resolve blocked legal slots; it is geometry
based and contains no marker-ID-specific exceptions.

All-label layout cache keys include canonical coordinates/dimensions/profile
version, display coordinates, IDs/declared faces, name mode, projection, figure
bounds and DPR. Editing a position or name, switching mode or resizing cannot
reuse an unrelated layout. The cache stabilizes selection positions only;
actual current overlay extents and paths are checked after every render.
Transient pre-show constructor layouts are not acceptance renders.

- [Final32/default1280×960](mockups/marker_profile_138/visibility_final_v9/final-32-1280x960-both.png)
- [Final32/FHD original1920×1080](mockups/marker_profile_138/visibility_final_v9/final-32-1920x1080-both.png)
- [Final18/FHD original1920×1080](mockups/marker_profile_138/visibility_final_v9/final-18-1920x1080-both.png)
- [Final32/125%FHD original2400×1350](mockups/marker_profile_138/visibility_final_v9125/final-32-1920x1080-both.png)
- [Final32/820×600 top at125%, actual1025×750](mockups/marker_profile_138/visibility_final_v9125/final-32-820x600-top.png)
- [Final32/820×600 bottom](mockups/marker_profile_138/visibility_final_v9/final-32-820x600-bottom.png)
- [Final32/820×600 invalid B2/Y](mockups/marker_profile_138/visibility_final_v9/final-32-820x600-invalid.png)

```powershell
$env:QT_SCALE_FACTOR='1'
.venv/Scripts/python.exe docs/visualization/mockups/marker_profile_138/finalize_exploded_visibility.py --output docs/visualization/mockups/marker_profile_138/visibility_final_v9 --selection-sweep
$env:QT_SCALE_FACTOR='1.25'
.venv/Scripts/python.exe docs/visualization/mockups/marker_profile_138/finalize_exploded_visibility.py --output docs/visualization/mockups/marker_profile_138/visibility_final_v9125 --selection-sweep
```

Both exit0; stderr logs are empty. Each has10 fresh original captures,50 actual
selected-layout renders and58 readability records. Marker-disk overlaps,
selected-ring/neighbor intersections, ID/title occlusions and leader crossings
are0. All50 selection layouts reuse stable positions; QTest direct badge clicks
are separate named tests, not a claim that all50 were native input tests.
Names Selected/View face/All counts, F1/X21→22 Preview, F1→F9 Preview, unchanged
applied profile, cache identity changes and Reset are checked. The same read-only
reviewer independently verified current source/dependency hashes, all20 PNGs,
selection/readout, source preservation, cache invalidation and reset at DPR1.25.
Its final verdict is **APPROVE — new exploded-face UI prototype only**, with no
outstanding findings. See [review record](marker_profile_138_ui_review.md).

Evidence is fresh for the v9 runs; earlier runs are retained without promotion:
v1/v2 checked narrower diagnostics and still had leaders needing correction;
v3/v4's slow initial assembly was interrupted; v5 failed selection crossings;
v6 failed B11 point obstruction at100% and B1 crossing in a125% small window;
v7's32px-margin experiment failed true disk overlap and was reverted to16px;
v8 passed its defined render/sweep checks but needed cache-key and mode/edit
invalidation checks added in v9. The early comparison summary KeyError and
interrupted initial selection attempts are also retained in logs. Only verified
task-owned processes were stopped. None of these partial/failed attempts are
final passes.

Evidence: [DPR1](mockups/marker_profile_138/visibility_final_v9/evidence.json),
[DPR1.25](mockups/marker_profile_138/visibility_final_v9125/evidence.json).
Environment is Windows11/Python3.13.5/PySide6 6.10.1/Qt windows, OS100%;125% is
a Qt-process override. FHD originals are1920×1080 and2400×1350; logical820×600
is actual820×600 and1025×750. No low-resolution image was enlarged. Static
public fixtures have no random seed; source equality is exact and no physical
tolerance/baseline approval is introduced. Native OS125%/external input/capture,
arbitrary import/camera guarantees and production delivery remain outside these
passes. No validated real experimental dataset is assumed.

## Display and data contract

- Box remains available; Exploded faces adds six translated face frames, one
  marker instance per source ID, face-name/count badges and six faint dashed
  connections from original face centers. A gray central wirebox and XYZ
  direction triad provide the source reference.
- Current B face center radius `R=1.0 × max(box_dims)`; earlier captures used.75.
  Each frame and all its declared
  markers move by `NORMALS[face] × (R − dims[normal_axis]/2)`. Face geometry and
  the common XYZ scale are retained. No camera-based face inference, point
  jitter, coordinate snapping or source migration is introduced.
- `source_xyz` and `display_xyz` are separate. The parent helper's `xyz` alias is
  display-only for 3D hit testing/callouts; table, selected readout/normal, lower
  2D and draft/applied objects use the original profile. Selected rings, ID
  anchors, projected candidate picking and scene Fit use the display array.
- `Display only` is explicit. Global numeric/mm plot axes are removed from the
  translated scene; the original selected mm values and outward normal remain.
  Box/Exploded camera and zoom states are preserved separately. Switching view
  does not Apply a profile.

Example32: R225, display translations along normal axis are Right/Left±75,
Top/Bottom±135, Front/Back±180. Example18: R150, translations±50/±90/±110.
Those are the historical.75-radius views. B uses32 R300 and translations
±150/±210/±255;18 R200 and translations±100/±140/±160.
These are derived display translations in the same numeric geometry scale,
not physical mounting measurements, accuracy tolerances or approved baselines.

## Historical initial exploded review images

- [Primary32/default1280×960](mockups/marker_profile_138/exploded_final/32-original-1280x960.png)
- [Primary32/FHD original1920×1080](mockups/marker_profile_138/exploded_final/32-original-1920x1080.png)
- [Example18/default](mockups/marker_profile_138/exploded_final/18-original-1280x960.png)
- [Primary32/125%FHD2400×1350](mockups/marker_profile_138/exploded_final125/32-original-1920x1080.png)
- [Isometric comparison32/default](mockups/marker_profile_138/exploded_final/32-isometric-1280x960.png)

The early70:30 split made2D too small. Removing outer direction axes and fitting
the actual displayed frame/annotation extents with16 logical-pixel margins
allowed the original55:45 ratio. Both advisors inspected refined actual32
default/FHD camera variants; original camera separates the Top plane from Back
more clearly than the isometric35.264°/45° arrangement in these fixtures.

Those historical views had residual Left/Front and Right/Back projected
proximity and some longer ID leaders. Outward translation cannot guarantee all projected points separate at
every camera angle. The direct ID label selection and existing candidate ID/face
chooser remain necessary. Zero badge-bbox overlaps is not human readability or
leader association certification.

## Verification and limits

```powershell
$env:QT_SCALE_FACTOR='1'
.venv/Scripts/python.exe docs/visualization/mockups/marker_profile_138/generate_exploded_mockups.py --output docs/visualization/mockups/marker_profile_138/exploded_final
$env:QT_SCALE_FACTOR='1.25'
.venv/Scripts/python.exe docs/visualization/mockups/marker_profile_138/generate_exploded_mockups.py --output docs/visualization/mockups/marker_profile_138/exploded_final125
```

Both exit0, eight fresh states per DPR (16 total), prototypeQTest passed and
stderr logs empty. Public18/32 input hashes match literal independently recorded
values; source profiles remain exact before/after Box/Exploded switches,
selection and camera changes. Literal expectation: example18 M2 source
[38,-60,-18], display[38,-150,-18], source normal[0,-1,0]. Its selected mm
readout stays unchanged. F1 name click selects the canonical row. Independent
mode camera assertions restore edited Box25°/40° versus Exploded35.264°/45°.
Repeated overlays retain exactly three triad lines, avoiding stale duplicates.

Run evidence records schema/plan, source digest, base/dirty, command/environment,
static public input hashes/seed-not-applicable, derived display offsets, actual
logical/pixel/DPR sizes, bbox diagnostics, expectations/results and limitations:
[DPR1](mockups/marker_profile_138/exploded_final/evidence.json),
[DPR1.25](mockups/marker_profile_138/exploded_final125/evidence.json).
Windows11/Python3.13.5/PySide6 6.10.1/Qt windows; OS100%, Qt-process125% override.
FHD PNGs are directly rendered1920×1080 and2400×1350, without enlargement.
The earlier marker-name comparisons retain their earlier source digests; their
shared helper gained display-overlay/obstacle hooks for this new mode.

The earlier exploded captures omitted820×600. It is included in the successful
final visibility pass above; actual OS125% native input remains unverified. Native
capture/activation error remains recorded. This is a proposed visual mode, not
production schema/persistence/worker/export validation or completed#138. #113
registration remains excluded, #104 actual experiment validation separate/no
verified real dataset, #139/#143 out of scope. Existing source lineage, baseline,
correctionOFF and delivered#135/#136/#137 are unchanged.
