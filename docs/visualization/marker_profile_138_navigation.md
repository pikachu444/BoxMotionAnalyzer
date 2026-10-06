# Profile preview interaction and cost review — #138 / PUB05

Last Reviewed: 2026-10-06

Current status, 2026-10-06: the user approved the final interactive mockup.
Production software and automatic verification passed final independent review.
Required clean-commit hosted CI gates merge; native follow-up stays open. Historical mockup review states
below describe their own revision, not current approval. Native external input
and actual OS125% remain unexecuted; real experiment validation is separate.


Plan Spec: ISTA6A-PLAN-20261001-v1

## State and accountability

The user asked about rotation/zoom/pan and individual separated-face dragging,
then challenged reactive feature additions and performance. Main's earlier
review concentrated on fixed-camera readability. It did not evaluate the whole
interaction before recommending a final presentation. The approved static
images do not approve free navigation, a face drag implementation or performance.
Main implemented a separate interactive Qt mockup after that finding. Rotation,
pan, zoom and face-title dragging now use one gesture owner and retained display
buffers. Production remains unchanged. This record preserves the original cost
finding and distinguishes it from the new mockup verification below.

Base/HEAD `1f654faddd44eedf7ff6e807d85f5e08559f8b13`, branch
`issue138-marker-profile-semantics`; dirty prototypes/documents. Main owns all
code, tests and documents. The same independent GPT-6.1 Sol/high reviewer is
read-only and creates no agents. #113 registration is excluded, #104 physical
validation separate/no validated dataset, #135/#136/#137 delivery preserved,
#139/#143 excluded.

## Original static prototype path and cost

`ReviewedPrototype.select_row` selects on press and calls `draw`; that clears
and reconstructs3D/2D figures. Both custom picking and Matplotlib's own Axes
mouse handlers own the same press/release events. `wheel3` and release call
`selection_overlay`. `FinalVisibilityPrototype` uses multiple synchronous draws
even with a cached name layout; a cache miss includes actual annotation-path
search. The projection-keyed cache is an unbounded dictionary. Connecting new
face motion directly to these callbacks would create latency, gesture conflicts
and retained cache entries. Moving the same solver to release alone still
blocks the GUI for seconds.

Main's fresh corrected cost probe measures12 existing-artist redraws,5 cached
overlays and3 uncached placements per fixture/window. Draw and solver counters,
wall-clock distributions, literal public18/32 hashes and exact unchanged
canonical/source/draft/preview/applied objects are recorded. Timing uses
`perf_counter_ns`; units are ms per synchronous Python call, not native
input-to-display latency or achieved FPS. No performance budget is approved
by these measurements. Static geometry has no random seed or physical tolerance.

Corrected100/125% results (median milliseconds):

| Qt process scale / public fixture / logical window | Existing artists redraw | Cached names overlay | Uncached names layout |
| --- | ---: | ---: | ---: |
| 100% /32 /1280×960 | 170.71 | 549.87 | 4724.10 |
| 100% /32 /1920×1080 | 184.00 | 549.26 | 2219.89 |
| 100% /18 /1280×960 | 117.88 | 356.80 | 1308.95 |
| 100% /18 /1920×1080 | 112.98 | 291.32 | 1272.23 |
| 125% /32 /1280×960 | 185.61 | 560.80 | 4472.12 |
| 125% /32 /1920×1080 | 182.41 | 553.17 | 2874.49 |
| 125% /18 /1280×960 | 112.39 | 374.68 | 1121.16 |
| 125% /18 /1920×1080 | 100.54 | 354.51 | 1220.20 |

Both sequential runs exited0 with empty stderr. Every raw redraw counts1
draw/0solver; cached overlay4draw/0solver; uncached6–7draw/1solver. These costs
fail to justify using the current path for continuous motion. This is a cost
finding, not a newly accepted performance baseline.

```powershell
$env:QT_SCALE_FACTOR='1'
.venv/Scripts/python.exe docs/visualization/mockups/marker_profile_138/measure_navigation_cost.py --output docs/visualization/mockups/marker_profile_138/navigation_cost_v2_100
$env:QT_SCALE_FACTOR='1.25'
.venv/Scripts/python.exe docs/visualization/mockups/marker_profile_138/measure_navigation_cost.py --output docs/visualization/mockups/marker_profile_138/navigation_cost_v2_125
```

Windows11, Python3.13.5, PySide6 6.10.1, Qt windows; OS100%, Qt-process1/1.25.
Captures/native external input are not part of this probe. Constructor startup
is excluded. The v1 probe captured a bound redraw method before instrumentation,
so its raw draw counter was0 instead of1. The same reviewer found this P2;
Main corrected it with dynamic lookup and a1draw assertion. Original v1 timing
samples remain descriptive only; their work counts are invalid. Corrected v2
100/125% exited0 and the reviewer verified every counter and source/dependency
hash. Probe SHA256 is
`a5908a4fe3bb05bb88a75606609c0f28ff700a08c7385b9a9a38f00bb0299fa8`.
125% was sequential to avoid competing Qt rendering workloads; the reviewer
ran no concurrent Qt rendering. Final evidence is measurement-only:
[100%](mockups/marker_profile_138/navigation_cost_v2_100/evidence.json),
[125%](mockups/marker_profile_138/navigation_cost_v2_125/evidence.json).

## Implemented standalone interaction

The new `ProfilePreviewNavigation` uses one controller for Pending click,
Rotate, Pan and Face offset drag, replacing
the inherited press-pick/release/wheel callbacks and default Axes mouse handlers
for this view. Do not layer another handler on top. Reuse the marker table,
public profile importer/validator,2D face view and existing renderer data.
The series of prototype subclasses is exploration history, not the production
class hierarchy.

- Marker selection happens on release only if movement stays below Qt's
  `startDragDistance` in logical pixels. Background left drag rotates, middle
  drag pans, wheel zooms. Pointer capture, release outside the canvas, focus
  loss, Escape and profile/mode changes must terminate the gesture explicitly.
- A face-name hover/drag is the only offset handle. Markers keep their selection
  role. No extra toolbar mode/button is proposed. Capture the face and start
  projection once; do not switch the target as the pointer crosses another face.
- Each face has one view-only normal-axis separation scalar. Use a ratio to the
  largest box dimension; canonical XYZ, labels/face semantics,2D, profile hash,
  compatibility, draft/applied/source and saved/exported profile stay unchanged.
  The source geometry cannot be altered by a display gesture.
- If the projected normal for one box-dimension displacement is shorter than
  Qt's logical drag distance, disable that handle for the current angle rather
  than amplify numerical noise. Hover guidance can say `Rotate view to adjust
  spacing`. This is a display interaction rule, not a physical accuracy tolerance.
- View-only offset ratios are bounded0–3;0 means the original source face,
 3 prevents unbounded spacing. Default B restores the existing R1.0 offsets.
  These are engineering display limits, not a measurement standard/baseline.
- Escape restores the captured drag-start view. Reset view restores B camera,
  zoom, pan and all six default separations. Fit retains current angle/separations
  and recenters/fits the complete scene. Neither operation resets a profile;
  Reset to source retains its separate draft/source meaning.

## Render and work bounds

During motion, update retained scene buffers and reproject current face titles
and the selected marker. Temporarily omit ordinary ID badges/leaders while
preserving the user's requested Names mode; restore names when idle. Every
visible anchor must follow the current scene—stale stationary labels are not
a fast path. Do not reconstruct figures, redraw2D, validate profiles or run
full label placement during motion. Queue one coalesced repaint, replacing the
pending view snapshot with the newest; do not enqueue every mouse event.

Full name placement needs a data-only bounded algorithm, not GUI-thread artist
creation for each trial. Obtain text extents on the GUI thread, then solve
immutable projected rectangles/segments. Qt/Matplotlib objects remain on the
GUI thread. The cooperative target is8ms per GUI slice and100ms total placement
work. A bounded placement/repair step can overrun either target; a repair step
has up to5 candidate batches before the next clock check. These are not hard
real-time guarantees. Iteration bounds also apply. When exhausted, use the best
valid placement or Selected/View face plus existing2D/candidate selection,
keeping the requested Names mode. These engineering scheduling targets are not
approved experimental tolerances.

Allow at most one active solve and one latest pending snapshot. A new gesture,
profile revision, mode, resize/DPR change or reset cancels/invalidates previous
work; generation keys alone do not prevent accumulated work. Keys include source
revision, captured view projection/offsets, viewport/DPR and Names mode. Selection
overlay is independent of cached layout, so an old selected ID cannot replace
the current selection. Results apply on the GUI thread only when generations
match and gesture state is Idle. An8-entry LRU bounds settled layouts; profile
replacement/resize/reset clears incompatible entries. No unbounded angle cache.

Arbitrary camera/offsets can physically project markers onto the same pixels.
No label algorithm can universally separate those source projections. Keep
the2D face view and candidate ID selector, use recoverable rendering fallbacks,
and retain the approved default. The prototype's assertions are deterministic
test gates; they must not become production crashes for unavailable placements.

Matplotlib's [blitting documentation](https://matplotlib.org/stable/users/explain/animations/blitting.html)
requires a valid cached background and puts dynamic artists above static ones.
Camera/limits/DPR changes invalidate backgrounds. Blitting is an option to
measure, not a universal3D fix or performance promise. First remove duplicate
draws and artist reconstruction, then measure the real gesture path.

## Original independent findings

The same reviewer considers one controller plus six view-only scalars a bounded,
appropriate direction. It rejects continuing to layer the static prototype
solver. New interaction is **not approved**:

| Severity | Location / reproduction | Impact / required evidence |
| --- | --- | --- |
| P1 | FinalVisibility overlay/untangle + Reviewed draw; call on each motion or release | Multi-draw synchronous blocking. Implement retained fast path and capped/cancellable placement; measure actual event latency, not solver timing alone. |
| P1 | Reviewed pick/release + MarkerId press selection + default Axes handlers | A single drag can select, recreate axes and rotate simultaneously. One gesture owner; deferred click and capture/cancel tests. |
| P1 | FinalVisibility/MarkerId hard placement assertions at a freely changed projection | Placement unavailable can throw. Recoverable Names/candidate/2D fallback and adversarial angles/offset tests. |
| P2 | FinalVisibility unbounded projection-keyed layout_cache | Repeated released views retain entries.8-entry LRU, clear rules and forced-eviction tests. |
| P2 corrected | v1 cost probe captured bound raw draw | Raw work counter wrong; corrected v2 dynamic lookup/assertion and fresh evidence, preserving invalid v1 record. |

The P1/P2 interaction defects were implementation gates for the replacement
mockup, not claims that production code had been changed or accepted. Main
implemented the bounded interactive prototype described below. The same
reviewer must recheck the new source and evidence before its UI-only acceptance.
Performance results need100/125% and default/FHD/small windows, event-loop/frame
latency and retained work/cache bounds; actual native input/capture limitations
remain explicit. #138 semantic compatibility/persistence/producer-consumer/CI
delivery is still pending. Do not mark the issue or all GUI work complete.

Original same-reviewer verdict: **CHANGES REQUIRED for extending the static
prototype to navigation/face dragging**. The replacement needs a fresh verdict
on the three P1 and bounded-cache P2 findings. The accepted single-controller
direction alone was not navigation or performance approval.
Even the1draw path costs100–186ms in this probe; persistent artists/coalescing
alone cannot be claimed to meet a responsiveness budget without real fast-path
measurements. The earlier fixed-camera UI approval is retained in its original
scope and is not promoted to free-navigation approval. The reviewer also noted
that mutating `face_offsets` alone is insufficient: `render3` recomputes them on
selection/Names changes, so six separation scalars must live in persistent view
state and drive artist updates. Native/production/CI/real experimental scope
remains unverified. No reviewer files were edited and no new agents created.

## Fresh interactive mockup verification

Main authored [the viewport](mockups/marker_profile_138/profile_preview_navigation.py)
and [the Qt evidence harness](mockups/marker_profile_138/generate_navigation_mockups.py).
Qt `QPainter` paints the source box, six display faces and markers. Matplotlib
provides the existing orthographic Y-up projection math only. Its canvas does
not redraw each motion. `Axes.apply_aspect` retains equal projection scale;
the earlier v1/v2 anisotropic renders are superseded and retained as history.
The initial inherited hidden canvas is released. Production will compose this
view with the existing editor; the exploration subclass chain is not a target
architecture.

Immutable source points, marker IDs/faces and mm readouts stay separate from
retained display/world-scene buffers. Camera/zoom and geometry projection keys
avoid repeated matrix/geometry work. A Qt update coalesces paints, while a single
cancellable timer job places names only after the gesture ends. No per-motion
validation, editor update,2D reconstruction or full name solve occurs. Layout
storage has an8-entry LRU; diagnostic samples use256-entry deques; picker menus
are deleted and source revisions guard their callbacks. No queue of old views
or unbounded per-angle cache is retained. Candidate batches are128 points with
bounded generic local repair, rather than trial artist creation/draws.

`ProfilePreviewViewState` has schema1, the plan spec, source profile hash, a
versioned display rule hash, finite view scalars, view-only ratio units and
explicit static-time meaning. The rule hash binds origin, axes, declared
normals, projection and offset formula. This is a display-state contract only:
it does not implement #138 analysis semantics or certify legacy results.

Fresh sequential v11 commands, both exit0/empty stderr:

```powershell
$env:QT_SCALE_FACTOR='1'
.venv/Scripts/python.exe docs/visualization/mockups/marker_profile_138/generate_navigation_mockups.py --output docs/visualization/mockups/marker_profile_138/navigation_v11_100
$env:QT_SCALE_FACTOR='1.25'
.venv/Scripts/python.exe docs/visualization/mockups/marker_profile_138/generate_navigation_mockups.py --output docs/visualization/mockups/marker_profile_138/navigation_v11_125
```

Evidence: [100%](mockups/marker_profile_138/navigation_v11_100/evidence.json),
[Qt125%](mockups/marker_profile_138/navigation_v11_125/evidence.json).
Each run has10 fresh PNGs: public18/32 at1280×960,1920×1080 and820×600,
plus small-window bottom and invalid B2/Y states. FHD originals are1920×1080
pixels atDPR1,2400×1350 atDPR1.25; no enlargement. All default names are shown
with0 badge/marker/title occlusions and0 marker-disk overlaps in these captures.
Equal projection scale differs by at most1e-9 logical pixels/projected unit;
this is floating-point arithmetic tolerance, not physical accuracy.

Each of six windows checks32 QTest motion samples, no solves during motion,
retained widget/buffers and2D axes, deferred click, exact unchanged source/draft/
applied, all150 stable selection layouts across fixtures/windows per DPR,
12 released views exercising8-entry eviction, sample capacity256, mode-cancel
and an unavailable normal-axis handle at a face-on view. Separate actual editor
Preview checks F1/X21→22 and F1→F9, cancellation of old layout work, preserved
view and unchanged applied state; invalid B2/Y blocks Preview/Save/Apply without
replacing the last valid scene; Reset restores the public source. Independent
literal checks include M2 source[38,-60,-18], display[38,-200,-18], one Front
offset+.2 (±.015 from integer pointer rounding), pan[40,25], Escape restoration,
marker drag without selection and actual M2 click selecting canonical row17.
Unsupported schema/policy, stale source, wrong units/time and NaN/Infinity reject.

Work bounds are verified by source and state counters, rather than claiming a
measured process-memory reduction. Recorded paint medians are4.56–8.52ms,
event-to-paint medians4.73–9.91ms across the checked windows/DPRs. These bounded
Qt samples exclude native input/compositor latency and do not establish FPS.
The8ms placement slice is cooperative and can overrun on one placement/repair
step (up to5 candidate batches). The raw evidence's shorter `one bounded vector
step` wording should be read with this precise qualification. The timings cited
above are v10 observations; v11 records fresh timings rather than a reused pass.
Arbitrary imports/angles may use the explicit limited-name/candidate/2D fallback;
overlap-free display is not promised for every projection.

The same independent reviewer approved the corrected interactive mockup and
its caption-only correction with no outstanding P0/P1/P2.
At that prototype boundary user confirmation remained pending. The user
subsequently approved this final interactive mockup on 2026-10-06.
Actual external native input/capture and OS125% remain unexecuted because the
previous activation/capture attempts failed and current CUA native APIs are
disabled. Qt process125% on OS100% is recorded separately. Production semantic
compatibility/persistence/export/worker checks, CI and #138 delivery are pending;
public synthetic passes are not real experimental validation.

### Recheck corrections

The first new-interaction audit at viewport SHA
`7a2d849e7a403a87608971773be3e4070835f1392959195e4df8bdd39d2346a3`
found no P0/P1 and accepted the original gesture/cache fixes, terminology/menu
placement and default images, but requested two P2 corrections. At zoom.5,
selected F10's fallback badge was actually painted over T3/R3 and omitted from
hit diagnostics. A middle click also selected a marker, and an unrelated release
could terminate a captured left drag. Main fixed both: fallback avoids all
painted badges/leaders and enters the hit registry; matching captured button
ends a gesture and only a left click selects; a competing press cannot replace
an active gesture. Strict display-rule version rejects boolean values as well.

v11 adds64 actually painted public32 selection states per DPR at zoom.3/.5,
checking every actual badge against other badges/leaders and fallback hit
registration. It also QTests middle click, unrelated release and competing press
against literal unchanged row/view/captured gesture expectations. Both full runs
pass with exact source/draft/applied unchanged. The same reviewer independently
rechecked matching-button handling and actual painted fallback badges at both
DPRs: the two P2 findings are resolved and no P0/P1 remain. It approved this
interactive UI mockup with one minor/nonblocking note: the narrow pinned2D
toolbar should explicitly say2D. Its inline read-only QTests exited0; final
output `BUTTON+FALLBACK INDEPENDENT V11 PASS DPR 1.25` is tool-transcript only
(chunks `3c0fb6`, `32def0`), not a saved reviewer file.
Full v11 harness SHA256:
`39850a771dd92d3d0706dd788ad5dc3ad1da1acb0c34aae57a9b654d4b27a643`;
viewport SHA256:
`f4192d9e479f84605b9eeff6a75f4ed113638dc332ee812c251decd8795c0b90`.
Earlier failed/limited/anisotropic iterations and their original evidence remain
history, not fresh acceptance claims.

Main subsequently prefixes the narrow toolbar title with `2D`, retaining the
approved pinned toolbar/control positions. Only the caption/draw hook and
caption-only harness scope changed; viewport/gesture source remains the v11
SHA above. Fresh bounded commands append `--caption-only`, with outputs
[100%](mockups/marker_profile_138/navigation_caption_100/evidence.json) and
[Qt125%](mockups/marker_profile_138/navigation_caption_125/evidence.json).
Each run exits0/empty stderr with6 fresh small top/bottom/invalid captures and
literal expected captions `2D Back / Z=-45 mm (12)` for32 and
`2D Back / Z=-40 mm (3)` for18. Existing accessibility/error/source preservation
checks pass. Unaffected v11 full navigation gates and wide PNGs are explicitly
reused, not claimed as new full runs. Current caption harness SHA256:
`fc4935d77caa67fbc8e8fa4ea8ac843d4f4bf582be2583c2fb78c234d96e70a4`.
The same reviewer inspected all12 fresh caption PNGs at original resolution and
checked source/dependency hashes and pixel/logical/DPR evidence without another
Qt run. Final verdict: **APPROVE for the implemented interactive UI mockup**,
no outstanding P0/P1/P2. Its earlier minor toolbar note is resolved. Human
confirmation was subsequently received on 2026-10-06. Production evidence is
recorded separately in the delivery document; native and real-experiment
exclusions remain.
