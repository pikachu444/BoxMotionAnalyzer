# Marker profile semantics and editing — #138 / PUB05

Last Reviewed: 2026-10-06

Current status, 2026-10-06: the user approved the final interactive mockup.
Production implementation, automatic verification and independent review are
complete; required clean-commit hosted CI gates publication. Historical mockup review states
below describe their own revision, not current approval. Native external input
and actual OS125% remain unexecuted; real experiment validation is separate.


Plan Spec: ISTA6A-PLAN-20261001-v1

## Delivery state

The user approved the final interactive mockup on 2026-10-06 after the same
independent reviewer approved its visibility, terminology and gesture corrections.
Main has implemented the production editor, source-bound identity, compatibility,
atomic persistence and worker guards. The same reviewer's production audit is
APPROVE with no remaining P0/P1/P2; required CI gates merge. The final
[independent report](marker_profile_138_independent_review.md) preserves its
exact source binding and fresh/reused execution limits.
The [current contract](../analysis/reference/marker_profile_semantics.md) is the
implementation reference. Display offsets and gestures retain the original
centre, physical coordinates, identity and numerical results. Correspondence
changes do not by themselves assert that numerical pose changes.

The sections after Proposed interaction retain historical mockup iterations.
Their "pending", rejected alternatives and prototype-only assertions describe
their own execution boundary and are superseded by this delivery state.
Publication retains linked historical images/reports and the complete approved
v11/caption/native evidence. Additional rejected-iteration captures remain in the
local archive; historical report inventories are not new production acceptance.

## Production evidence

The [self-contained review packet](marker_profile_138_review_packet.md) records
requirements/exclusions, base/head/file hashes, actual paths, independent oracles,
commands/results, mockup approval, original final screens and unexecuted items.
Correction core91, consumer/Compare146 and Qt125 editor/export14 passed;
production30 states per DPR
passed with default example18/32 actual name/badge/title occlusion count0. The
unchanged #135 frozen corpus passed6/6 fresh, with legacy Compare counts0.
Broad local preservation and retained failures are recorded separately without
adding duplicate runs as unique cases. Rank-deficient status describes the
current solver's local support guard, not proof of global nonidentifiability.
The same independent reviewer approved the final software delta; hosted clean
commit CI remains the publication gate.

FHD originals are1920×1080 pixels at QtDPR1 and2400×1350 at QtDPR1.25,
with logical1920×1080 client size. Small820×600 clients are captured separately.
Local Windows desktop2560×1440/OS100%; no image is upscaled. Windows Qt/widget/
QTest success is not external native input/screen or actual OS125% acceptance.
Retained capture/activation failures and disabled native APIs leave those native
checks open. #104 measured validation is separate and unavailable.

Base: `main@1f654faddd44eedf7ff6e807d85f5e08559f8b13`; initial working tree clean.
Work branch: `issue138-marker-profile-semantics`.
Completed #135/#136/#137 development and their existing native follow-ups remain
unchanged. #113 registration is excluded by the user's decision; existing source
identity/lineage must still be checked in #138. #104 real validation is separate;
there is no validated real experimental dataset for this work. #139 onward and
#143 features are out of scope.

## Proposed interaction

The existing [export window](mockups/marker_profile_138/1920x1080-existing.png)
gains [Copy/Edit entry points](mockups/marker_profile_138/1920x1080-entry.png).
The editor uses the current public geometry and Matplotlib preview. Presets
remain immutable. Custom ID and source lineage distinguish a user copy.

Wide windows pair the marker table and preview. At 820×600, Markers/Preview/Rules
tabs keep the lower actions accessible. Rules are read-only: geometric-center
origin; local +X=Right, +Y=Top, +Z=Front; world vertical +Y; mm and seconds;
explicit face prefixes; local half-turn face maps preserve observed XYZ and IDs.

- Copy/import establishes a draft and source snapshot; Apply changes the active
  profile. Preview does not Apply or approve an experiment.
- Reset to source restores the copied/imported geometry into the draft, retains
  its custom ID and history, and still requires Apply.
- Cancel discards this editing session and retains the earlier applied profile.
- Save JSON will persist valid draft/applied/source snapshots and history. Save
  failure/retry must preserve both prior file bytes and current editor state.
- Invalid input marks the affected cell and blocks Preview/Save/Apply; the last
  valid plot is explicitly marked as stale. Unsupported meanings block Apply.
- Legacy result compatibility stays unknown/blocked. New profile Apply cannot
  supply missing meaning evidence or approve an old result.

The compatibility, save-failure and observability messages here are independent
UI fixtures. They are not completed production compatibility or persistence
checks. Example profiles are public virtual geometry, not experimental standards.

## Review images

All PNGs are directly captured Qt widget renders, not enlarged images.

### Latest review: actual mockup from the design debate

The user subsequently proposed displaying six offset faces around the original
central box. Main rendered that display-only mode. After the user challenged the
limited angle comparison, joint angle/spacing/roll diagnostics and actual Qt
renders support B25/50/roll30,R1.0; both advisors recommend it. The user accepted
that direction and requested a final readability review. See [Exploded faces
prototype and source-preservation evidence](marker_profile_138_exploded_faces.md).
Final label/title/leader correction passed20 fresh renders and100 selected-layout
renders across Qt100/125%. The same independent reviewer inspected all20 PNGs
and ran separate DPR1.25 selection/cache/reset checks: **APPROVE for the new
exploded-face UI prototype only**, with no outstanding P0/P1/P2. User final
confirmation, native follow-up and production remain pending. This does not change the
canonical profile or analysis/export data.

- [Final default window](mockups/marker_profile_138/visibility_final_v9/final-32-1280x960-both.png)
- [Final FHD original1920×1080](mockups/marker_profile_138/visibility_final_v9/final-32-1920x1080-both.png)
- [Final125%FHD original2400×1350](mockups/marker_profile_138/visibility_final_v9125/final-32-1920x1080-both.png)
- [Final small-window bottom controls](mockups/marker_profile_138/visibility_final_v9/final-32-820x600-bottom.png)
- [Final invalid B2/Y](mockups/marker_profile_138/visibility_final_v9/final-32-820x600-invalid.png)

The final checked states have0 marker/name/title occlusions and0 rendered leader
crossings. Labels stay fixed when selection changes; position/name Preview
changes invalidate the layout cache. The approval is bounded to public18/32,
the inspected windows and Qt process scales; it is not a guarantee for arbitrary
imported geometry/cameras or actual OS125% native input/capture. See the current
[independent review record](marker_profile_138_ui_review.md).

The user subsequently asked about3D rotation/zoom/pan. Basic Matplotlib mouse
connections, prototype wheel zoom and Fit/Reset exist, but free-navigation
sequences were not part of the above approval. Verify drag/selection separation,
annotation reprojection, view preservation across redraw/mode changes and full
Fit/Reset in production; do not infer these passes from the fixed-camera images.
The user also proposed dragging offset faces and challenged reactive additions
and performance. Main replaced the static prototype's blocking path with a
standalone Qt viewport: one gesture owner, retained buffers/projection, bounded
idle name placement and8-entry cache. Fresh100/Qt125% QTest/render checks passed
for rotation/pan/zoom/normal-axis face-title dragging, cancellation, source
Preview and work bounds. The same independent reviewer approved the corrected
interactive mockup and bounded narrow-caption correction with no outstanding
P0/P1/P2. Main added the short2D title prefix and passed affected100/Qt125%
narrow render checks; the same reviewer inspected all12 fresh originals.
User confirmation and production remain pending. Current original
[FHD](mockups/marker_profile_138/navigation_v11_100/navigation-32-1920x1080.png)
and [Qt125% FHD](mockups/marker_profile_138/navigation_v11_125/navigation-32-1920x1080.png),
scope and limitations are in the [interaction review](marker_profile_138_navigation.md).

Earlier, after the first bounded approval, the user requested further 3D identification advice.
Two read-only Sol/xhigh advisors compared actual new ID-label variants and both
recommend All IDs as default. Long crossing leader lines remain a bounded
placement issue in those historical32/default/small views. See [3D identification advice and
comparison images](marker_profile_138_3d_visibility.md). They are superseded by
the final corrected exploded-face presentation above.

Independent UI review on 2026-10-05 required four P2 corrections. Main fixed
them and two minor notes; fresh `audited`/`audited125` renders contain 20 states
each and passed prototype checks. Same-reviewer final verdict: **APPROVE for the
UI prototype only**, with no outstanding P0/P1/P2 in that bounded review. See the
[independent UI review record](marker_profile_138_ui_review.md).

- [Corrected default window](mockups/marker_profile_138/audited/reviewed-32-1280x960-both.png)
- [Corrected FHD original](mockups/marker_profile_138/audited/reviewed-32-1920x1080-both.png)
- [Corrected small-window controls](mockups/marker_profile_138/audited/reviewed-32-820x600-bottom.png)

The user liked the 1280×960 layout but found the face counts and “Draft preview”
wording unclear. Main clarified the prototype to “View face (marker count)”,
“Front (11)” and “Preview — not applied”, retaining explicit outdated/invalid
preview states. The two design advisors agreed on a layout packet only; they
did not approve the rendered UI or production implementation. Formal independent
production review remains pending. On 2026-10-05 the user explicitly requested
independent mockup review, including terminology and menu/control placement.
Main spawned one read-only GPT-6.1 Sol / high reviewer, `profile_ui_review`, with
a self-contained requirements/evidence packet. Its initial verdict required
changes; the final corrected prototype is approved as recorded above. Main
checked the 26 existing PNG dimensions and current prototype source digest;
these checks reused the 2026-10-04 render evidence and did not rerun production.

- [Clarified default window](mockups/marker_profile_138/wording/reviewed-32-1280x960-both.png)
- [Clarified FHD original](mockups/marker_profile_138/wording/reviewed-32-1920x1080-both.png)
- [Clarified DPR 1 evidence](mockups/marker_profile_138/wording/evidence.json)
- [Clarified DPR 1.25 evidence](mockups/marker_profile_138/wording125/evidence.json)

The same generation commands below were used with `--output` set to `wording`
and `wording125`, respectively. Earlier `reviewed` images/evidence remain as
history; their recorded script digest identifies the earlier wording revision.

Main implemented the two advisors' agreed packet in a standalone Qt prototype,
then generated 13 fresh states at each of DPR 1 and 1.25. Approval is pending.
Production code is unchanged. The marker table is about 480 logical pixels wide;
the right-hand 3D and 2D canvases have an adjustable vertical splitter. Face
buttons also show counts. Selection is linked to the table, and an overlapping
hit opens a candidate list with marker ID and declared face. The selected
marker's normal stays tied to that marker when another face is viewed.

- [Default 1280×960 window, example 32](mockups/marker_profile_138/reviewed/reviewed-32-1280x960-both.png)
- [FHD original, example 32](mockups/marker_profile_138/reviewed/reviewed-32-1920x1080-both.png)
- [FHD original, example 18](mockups/marker_profile_138/reviewed/reviewed-18-1920x1080-both.png)
- [Overlapping F3/B2 candidate selection](mockups/marker_profile_138/reviewed/reviewed-overlap-1920x1080.png)
- [Final table row and Top face](mockups/marker_profile_138/reviewed/reviewed-last-row-1920x1080.png)
- [820×600 upper view](mockups/marker_profile_138/reviewed/reviewed-32-820x600-top.png)
- [820×600 lower view](mockups/marker_profile_138/reviewed/reviewed-32-820x600-bottom.png)
- [Invalid input](mockups/marker_profile_138/reviewed/reviewed-invalid-1920x1080.png)
- [Legacy compatibility block](mockups/marker_profile_138/reviewed/reviewed-legacy-1920x1080.png)
- [Changed identity compatibility block](mockups/marker_profile_138/reviewed/reviewed-incompatible-1920x1080.png)
- [125% FHD logical window, 2400×1350 actual pixels](mockups/marker_profile_138/reviewed125/reviewed-32-1920x1080-both.png)

Windows 11 / Python 3.13.5 / PySide6 6.10.1 / Qt windows backend:

```powershell
$env:QT_SCALE_FACTOR='1'
.venv/Scripts/python.exe docs/visualization/mockups/marker_profile_138/generate_reviewed_mockups.py
$env:QT_SCALE_FACTOR='1.25'
.venv/Scripts/python.exe docs/visualization/mockups/marker_profile_138/generate_reviewed_mockups.py --output docs/visualization/mockups/marker_profile_138/reviewed125
```

Both commands exited 0. Exact public example hashes/geometry were preserved.
QTest verified rename/Preview/reset/invalid gating and candidate-button selection;
assertions also checked independent per-face pan/zoom, selected-normal stability,
empty-face picking and the final row. These are prototype checks, not production
save/reload/worker validation. Fit uses explicit canvas margins; readable plots
and arbitrary camera annotation containment still need user/native acceptance.
The original captures are 1920×1080 / 1280×960 / 820×600 pixels at DPR 1 and
2400×1350 / 1600×1200 / 1025×750 at DPR 1.25. Windows desktop scaling remained
100%; 125% is a Qt process override, not an OS-scale native acceptance result.
Prior black capture/activation failure remains the native follow-up blocker.
Run identities, source digest, environment and actual dimensions are recorded in
[DPR 1 evidence](mockups/marker_profile_138/reviewed/evidence.json) and
[DPR 1.25 evidence](mockups/marker_profile_138/reviewed125/evidence.json).

### Read-only design debate

The user rejected the compact prototype and explicitly requested two
GPT-6.1 Sol / xhigh advisors. Their independent investigation and direct debate
are recorded in [the design debate](marker_profile_138_design_debate.md).
Both agree to remove the duplicate context strip, use two independent canvases
with an adjustable 55:45 split, link plot/table selection and resolve overlapping
hits explicitly. No code/images were changed during that discussion. All sizes
in its next-mockup packet are estimates; mockup approval, production work
and native acceptance remain pending. The compact revision below is rejected
history, not the accepted next UI.

### Rejected revision: fitted plots and face/meaning context

The user found the stacked layout too empty and requested more efficient use
of space. The revision retains upper overall 3D/lower selected-face 2D, narrows
the marker table from its previous fixed 45% to about 520 logical pixels at
FHD, and fits the projected 3D box into its available rectangular row. It keeps
one common XYZ display scale rather than stretching the box. The adjoining
strip now shows six face diagrams/counts above, and the selected marker's
read-only face/normal/origin/axis/half-turn meanings below. These are relevant
#138 context, not extra explanatory paragraphs or unrelated decorations.

- [FHD original, example 32](mockups/marker_profile_138/compact/compact-32-1920x1080-both.png)
- [FHD original, example 18](mockups/marker_profile_138/compact/compact-18-1920x1080-both.png)
- [820×600, upper view](mockups/marker_profile_138/compact/compact-32-820x600-top.png)
- [820×600, lower view](mockups/marker_profile_138/compact/compact-32-820x600-bottom.png)
- [125% FHD logical window](mockups/marker_profile_138/compact125/compact-32-1920x1080-both.png)
- [Legacy block](mockups/marker_profile_138/compact/compact-legacy-1920x1080.png)

The previous fixed-aspect viewport centered a small box in a wide column.
[Matplotlib's box-aspect zoom](https://matplotlib.org/3.10.0/api/_as_gen/mpl_toolkits.mplot3d.axes3d.Axes3D.set_box_aspect.html)
supports enlarging it while retaining XYZ proportions. The prototype measures
the projected public box bounds, adjusts the display zoom/center within a
rectangular target and reserves margins for axis labels. No profile coordinates,
geometry hashes or interpretation rules change. The compact default camera is
12° elevation/18° azimuth with Y vertical. Face diagrams keep equal axis scale;
their shapes therefore reflect the actual face dimensions, not equal square
cards. The small window retains tabs and plot scrolling with fixed action buttons.

The meanings panel describes the selected marker, even if the face-view selector
is changed to another face. In particular, selected M2 remains Bottom with
normal `[0,-1,0]` when the user views Front. New semantic identities and
compatibility propagation are still pending production work, not asserted by
these fixture labels.

```powershell
$env:QT_SCALE_FACTOR='1'
.venv/Scripts/python.exe docs/visualization/mockups/marker_profile_138/generate_compact_mockups.py
$env:QT_SCALE_FACTOR='1.25'
.venv/Scripts/python.exe docs/visualization/mockups/marker_profile_138/generate_compact_mockups.py --output docs/visualization/mockups/marker_profile_138/compact125
$env:QT_SCALE_FACTOR='1'
.venv/Scripts/python.exe docs/visualization/mockups/marker_profile_138/measure_compact_layout.py
```

Each scale records seven fresh images (14 total) and independent prototype
QTest checks for literal M2 coordinates/face/normal, view-vs-marker meaning,
F1 x=21→22, Preview retaining the applied snapshot, Reset and invalid blocking.
Original FHD pixel sizes are 1920×1080 at DPR1 and 2400×1350 at DPR1.25;
820×600 logical is 820×600/1025×750 pixels. OS remains 100%; 125% is a separate
Windows Qt process override. Exact example hashes/geometry and label-box
diagnostics are checked. [DPR1 report](mockups/marker_profile_138/compact/evidence.json),
[DPR1.25 report](mockups/marker_profile_138/compact125/evidence.json) and
[same-fixture layout comparison](mockups/marker_profile_138/compact/layout-comparison.json)
record commands, source digest, head/dirty state and bounds. The comparison
uses literal public-32 corners `[±150,±90,±45]` mm and expects XYZ display-scale
ratios `[1,1,1]`; its 1e-12 dimensionless relative bound only covers float64
normalization rounding, not physical accuracy or an approved experimental baseline.

Approval remains pending. The previous sparse stacked layout below is retained
as rejected review history. Production UI/contracts/export/persistence/worker
work and native external-input acceptance remain pending; existing black-capture
and activation failures are not a pass. #104 physical validation is separate.

### Rejected sparse layout: 3D above 2D in the right preview pane

The user clarified the layout: retain the marker table on the left and divide
the right preview vertically, with A's overall 3D on top and B's selected-face
2D below. The prototype now follows that arrangement. Both plots share row
selection, draft preview and the existing face selector. The 3D contains all
markers; the 2D contains only the selected face. There is no extra small 3D
overview or face-focused translucent 3D pane.

- [FHD original, example 32](mockups/marker_profile_138/stacked/stacked-32-1920x1080-both.png)
- [FHD original, example 18](mockups/marker_profile_138/stacked/stacked-18-1920x1080-both.png)
- [820×600, upper 3D](mockups/marker_profile_138/stacked/stacked-32-820x600-top.png)
- [820×600, lower 2D](mockups/marker_profile_138/stacked/stacked-32-820x600-bottom.png)
- [125%, FHD logical window](mockups/marker_profile_138/stacked125/stacked-32-1920x1080-both.png)
- [Invalid draft](mockups/marker_profile_138/stacked/stacked-invalid-820x600.png)
- [Legacy result](mockups/marker_profile_138/stacked/stacked-legacy-1920x1080.png)
- [Changed geometry](mockups/marker_profile_138/stacked/stacked-incompatible-1920x1080.png)

At FHD both plots fit together without scrolling. At 820×600, the existing
Markers/Preview/Rules tabs remain; only the plot area scrolls to keep the two
views readable. Preview/Reset/Save/Apply/Cancel remain outside the scroll area.
The initial 660px minimum canvas clipped parts of each plot in the minimum
viewport. It was revised to 500px with spacing between plots, then recaptured.
This small-window behavior is part of the pending mockup decision.

```powershell
$env:QT_SCALE_FACTOR='1'
.venv/Scripts/python.exe docs/visualization/mockups/marker_profile_138/generate_stacked_mockups.py
$env:QT_SCALE_FACTOR='1.25'
.venv/Scripts/python.exe docs/visualization/mockups/marker_profile_138/generate_stacked_mockups.py --output docs/visualization/mockups/marker_profile_138/stacked125
```

Each scale records nine fresh images: two examples at FHD and minimum window
(top/bottom scroll), plus invalid, legacy and incompatible fixtures. FHD
1920×1080 logical is 1920×1080 pixels at DPR1 and 2400×1350 at DPR1.25;
820×600 logical is 820×600 and 1025×750 respectively. These are original
Windows Qt widget captures, with OS scale 100% and a separate process 125%
override. [DPR1 evidence](mockups/marker_profile_138/stacked/evidence.json) and
[DPR1.25 evidence](mockups/marker_profile_138/stacked125/evidence.json) record
source/dependency hashes, HEAD/dirty state, commands, exact public geometry
hashes and independent QTest checks: actual upper-3D/lower-2D axis order,
scroll reachability, M2 `[38,-60,-18]` mm/Bottom, F1 x=21→22, Preview retaining
applied state, Reset restoring x=21 and invalid Apply blocking. Geometry/hash
invariance is exact; no physical accuracy tolerance or baseline is introduced.

The previous face-focused 3D interpretation below was rejected. This revised
layout awaits #138 mockup approval. Production UI and native visual/external
input acceptance remain pending; the existing capture/activation failure is
preserved and widget captures do not count as native acceptance.

### Rejected interpretation: B with a face-focused 3D right pane

The user rejected both A/B alternatives and suggested adding 3D to B's right
face view. The new prototype keeps a compact whole-profile view on the left;
the larger right view now contains the actual 3D box, selected-face plane,
its colored markers/names, gray context markers and an outward normal arrow.
No marker coordinates or face definitions change. Screen point/name overlays
keep the selected face legible; they do not claim physical occlusion accuracy.
The outside Back camera shows decreasing local X from left to right; axis
labels retain the actual local coordinates rather than silently mirroring data.

- [FHD, example 32, 3D angle](mockups/marker_profile_138/focus3d/B3D-32-1920x1080-3d.png)
- [820×600, example 32](mockups/marker_profile_138/focus3d/B3D-32-820x600-3d.png)
- [Face-aligned camera, FHD](mockups/marker_profile_138/focus3d/B3D-32-1920x1080-face.png)
- [125% small window](mockups/marker_profile_138/focus3d125/B3D-32-820x600-3d.png)
- [Invalid draft](mockups/marker_profile_138/focus3d/B3D-820x600-invalid.png)

This is one layout with two camera presets, not two new layout alternatives.
The 3D angle makes depth visible; Face aligned faces the selected plane directly.
Selecting a table row focuses that marker's face. Camera rotation, point labels
and selection ring are display controls; Preview/Apply keep separate meanings.
The right pane gets about twice the width of the whole-profile overview.

[ParaView display styling](https://docs.paraview.org/en/latest/UsersGuide/displayingData.html)
supports the use of opacity/point size to separate focus and context.
[Matplotlib camera controls](https://matplotlib.org/3.10.0/api/_as_gen/mpl_toolkits.mplot3d.axes3d.Axes3D.view_init.html)
support face-aligned views with Y as vertical. During the first small-window
render, two label overlaps exposed an aspect-order problem: box aspect must be
set after selecting the Y-up camera, and must match the actual XYZ ranges.
That was corrected in this prototype; independent checks verify equal display
scale per mm. Earlier A/B renders remain rejected historical evidence.

```powershell
$env:QT_SCALE_FACTOR='1'
.venv/Scripts/python.exe docs/visualization/mockups/marker_profile_138/generate_focus3d_mockups.py
$env:QT_SCALE_FACTOR='1.25'
.venv/Scripts/python.exe docs/visualization/mockups/marker_profile_138/generate_focus3d_mockups.py --output docs/visualization/mockups/marker_profile_138/focus3d125
```

Each scale produces nine fresh states (18 total): example 18/32, two cameras,
1920×1080/820×600 logical windows and invalid draft. Original pixel dimensions
are 1920×1080/820×600 at DPR1 and 2400×1350/1025×750 at DPR1.25. OS remains
100%; the 125% run is a separate Windows Qt process scale override.
[DPR1 evidence](mockups/marker_profile_138/focus3d/evidence.json) and
[DPR1.25 evidence](mockups/marker_profile_138/focus3d125/evidence.json) retain
source digest, head/dirty state, commands, literal example hashes, prior failure,
label diagnostics and independent QTest expectations. Exact marker geometry,
six literal outward normals, M2 selection, Preview preserving the applied
profile, Reset and invalid blocking are checked. A dimensionless relative
1e-12 bound only covers float64 display-aspect normalization rounding; it is
not a physical tolerance or new approved experimental baseline.

Approval remains pending. Production UI/contracts/persistence/worker work has
not started. Native visual/external-input checking remains unexecuted due to
the recorded black-capture/activation error; widget renders are not native
acceptance or experimental validation.

### Rejected A/B visibility alternatives

The first prototype drew every marker name directly at its projected point.
The user found the points difficult to see, especially at projected overlaps.
The following two alternatives replaced that preview only; the user rejected
both, so neither is approved
or integrated into production. Earlier editing/compatibility fixtures below
remain review references.

| Alternative | FHD original, example 32 | 820×600, example 32 | Tradeoff |
| --- | --- | --- | --- |
| A: one large view, switch 3D/face | [3D](mockups/marker_profile_138/revised/A-32-1920x1080-3d.png), [Back face](mockups/marker_profile_138/revised/A-32-1920x1080-back.png) | [Back face](mockups/marker_profile_138/revised/A-32-820x600-back.png) | More space per plot; switch views to compare whole box and one face. Rejected. |
| B: 3D and selected face side by side | [Paired](mockups/marker_profile_138/revised/B-32-1920x1080-back.png) | [Paired](mockups/marker_profile_138/revised/B-32-820x600-back.png) | Simultaneous context; smaller plots and more crowded axes in small windows. |

Both use larger points with dark outlines, lighter box edges, a selected-point
ring/readout and only the selected name in 3D. Face views show all names on that
face with offset labels, white backgrounds and connecting lines. Coordinates,
face definitions and existing example hashes are unchanged. A uses an explicit
View selector; B changes the face when a marker-table row is selected. Reset view
restores camera orientation; Reset to source still restores the draft geometry.
No automatic point displacement is used to separate a projected overlap.

Face plots use increasing local axes, not a mirrored outside-camera view:
Front/Back=X,Y; Right/Left=Z,Y; Top/Bottom=X,Z, in mm. Orthographic 3D can still
project distinct markers onto the same point. Its selection ring is a screen
overlay to locate the selected marker, not evidence of physical visibility.

The design follows [Matplotlib annotation support](https://matplotlib.org/3.10.1/users/explain/text/annotations.html)
for label offsets/connecting lines and [ParaView linked selection](https://docs.paraview.org/en/latest/UsersGuide/selectingData.html)
for table/plot coordination. [Orthographic projection](https://matplotlib.org/3.10.7/gallery/mplot3d/projections.html)
reduces perspective distortion; the separate face plot addresses cross-face
projection overlaps.

The revision produced 14 fresh states per scale (28 total): both examples,
both alternatives, FHD/minimum window and invalid-input state. No face label
boxes overlap in those fixture renders. This is a display diagnostic, not a
guarantee for every custom profile. Prototype QTest passed row selection,
M2 `[38,-60,-18]` mm/Bottom readout, F1 x=21→22 edit, Preview preserving the
applied snapshot, Reset restoring x=21 and invalid-input Apply blocking.

```powershell
$env:QT_SCALE_FACTOR='1'
.venv/Scripts/python.exe docs/visualization/mockups/marker_profile_138/generate_preview_options.py
$env:QT_SCALE_FACTOR='1.25'
.venv/Scripts/python.exe docs/visualization/mockups/marker_profile_138/generate_preview_options.py --output docs/visualization/mockups/marker_profile_138/revised125
```

[DPR1 report](mockups/marker_profile_138/revised/evidence.json) and
[DPR1.25 report](mockups/marker_profile_138/revised125/evidence.json) record
logical/pixel size, original capture bounds, input hashes, exact independent
expectations and the corrected initial annotation-bounds measurement failure.
FHD is 1920×1080 actual pixels at DPR1 and 2400×1350 at DPR1.25; the small window
is 820×600 and 1025×750 respectively. Example
[A at 125%](mockups/marker_profile_138/revised125/A-32-1920x1080-back.png),
[B at 125%](mockups/marker_profile_138/revised125/B-32-820x600-back.png) and
[invalid input](mockups/marker_profile_138/revised/A-820x600-invalid.png).
These are Windows Qt renders with a process scale override; OS scale remains
100%. Revised native visual/external-input acceptance has not been run because
the existing capture/activation failure remains unresolved. It is not a pass.

### Initial state fixtures

| State | FHD original | Small window |
| --- | --- | --- |
| Custom edit | [1920×1080](mockups/marker_profile_138/1920x1080-edited.png) | [820×600](mockups/marker_profile_138/820x600-edited.png) |
| Reset source | [Reset](mockups/marker_profile_138/1920x1080-reset.png) | [Reset](mockups/marker_profile_138/820x600-reset.png) |
| Invalid input | [Invalid](mockups/marker_profile_138/1920x1080-invalid.png) | [125% invalid](mockups/marker_profile_138/scale125/820x600-invalid.png) |
| Legacy result | [Legacy](mockups/marker_profile_138/1920x1080-legacy.png) | [Legacy](mockups/marker_profile_138/820x600-legacy.png) |
| Changed geometry | [Incompatible](mockups/marker_profile_138/1920x1080-incompatible.png) | [Incompatible](mockups/marker_profile_138/820x600-incompatible.png) |
| Unsupported meaning | [Unsupported](mockups/marker_profile_138/1920x1080-unsupported.png) | [Unsupported](mockups/marker_profile_138/820x600-unsupported.png) |
| Insufficient whole layout | [Unavailable](mockups/marker_profile_138/1920x1080-unidentifiable.png) | [Unavailable](mockups/marker_profile_138/820x600-unidentifiable.png) |
| Save failure/retry | [Save failure](mockups/marker_profile_138/1920x1080-save-error.png) | [Save failure](mockups/marker_profile_138/820x600-save-error.png) |

Small-window [Preview](mockups/marker_profile_138/820x600-preview.png) and
[read-only Rules](mockups/marker_profile_138/820x600-rules.png) are separate tabs.
Example 32, copy and applied states are also included in the evidence inventory.

## Execution and limits

Windows 11 build 26200, Python 3.13.5, PySide6 6.10.1; Qt platform `windows`.
System desktop: 2560×1440, OS scale 100%, available client area 2560×1392.
Separate processes use `QT_SCALE_FACTOR=1` and `1.25`; OS display settings are
unchanged. At DPR1, FHD logical/pixel size is 1920×1080. At DPR1.25, 820×600
logical produces 1025×750 pixels, FHD logical produces 2400×1350 pixels and
the target available 2048×1114 logical produces 2560×1393 pixels (DPR rounding).

```powershell
$env:QT_SCALE_FACTOR='1'
.venv/Scripts/python.exe docs/visualization/mockups/marker_profile_138/generate_mockups.py
$env:QT_SCALE_FACTOR='1.25'
.venv/Scripts/python.exe docs/visualization/mockups/marker_profile_138/generate_mockups.py --output docs/visualization/mockups/marker_profile_138/scale125
```

Each run records 27 fresh render states, complete visible button bounds and a
prototype QTest edit/Preview/Reset/invalid/Apply check. The independent edit is
F1 `[21,12,40]` → `[22,12,40]` mm. Preview must retain the prior applied snapshot;
Reset restores x=21 and retains the custom ID. There is no numerical tolerance
or random seed: this is static geometry and exact UI state, not pose accuracy.
Existing example 18/32 hashes are checked against separately recorded literals.
Reports include commit/dirty state, generator digest, UTC, environment, command,
profile identity and original PNG dimensions:
[DPR1 report](mockups/marker_profile_138/mockup-evidence.json),
[DPR1.25 report](mockups/marker_profile_138/scale125/mockup-evidence.json).

Native computer-use identified the Qt table, fields, status and fixed actions.
The 820×600, 1510×800 and FHD-client 1536×864 windows at Qt DPR1.25 returned black captures; activation
failed twice, including a fresh-window recovery. Native visual and external
input acceptance are **blocked**, not passed. The original black images and
accessibility/error records are in `mockups/marker_profile_138/native/`.
Production native copy/edit/reset/preview/Apply/cancel/save/reopen and error
checks remain pending after implementation. Prototype renders do not certify
production GUI completion or #104 measured accuracy.
