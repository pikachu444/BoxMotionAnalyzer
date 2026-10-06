# Profile preview design debate — #138 / PUB05

Last Reviewed: 2026-10-06

Current status, 2026-10-06: the user approved the final interactive mockup.
Production software and automatic verification passed final independent review.
Required clean-commit hosted CI gates merge; native follow-up stays open. Historical mockup review states
below describe their own revision, not current approval. Native external input
and actual OS125% remain unexecuted; real experiment validation is separate.


Plan Spec: ISTA6A-PLAN-20261001-v1

## Status and participants

The user explicitly requested two GPT-6.1 Sol / xhigh design advisors after
rejecting the compact prototype. Main spawned `preview_design_a` and
`preview_design_b` with that exact model/effort. Both worked read-only, created
no agents and changed no files. They inspected the original images and actual
prototype/rendering paths independently, then exchanged proposals and rebuttals
directly. Main challenged both to explain why another enlargement would differ
from the already rejected layouts. Both final reports accept the same packet;
neither reports a remaining substantive disagreement.

This is design advice, not the later independent production acceptance review.
No UI approval, new render acceptance, native acceptance or #138 completion is
asserted. Production implementation remains pending. This discussion introduced
no new physical tolerance or baseline and no migration decision.

Base/HEAD: `1f654faddd44eedf7ff6e807d85f5e08559f8b13`.
Branch: `issue138-marker-profile-semantics`; working tree already contained the
uncommitted preapproval prototypes and documentation. Main did not modify code
or images during this design discussion; this record and its references are the
only new edits at that discussion boundary. Main subsequently implemented a
standalone prototype and generated fresh review images; see the latest review
in [marker_profile_138.md](marker_profile_138.md). That prototype is pending
user approval and does not constitute production delivery or native acceptance.

## Independent findings

| Advisor | Main finding | Evidence |
| --- | --- | --- |
| A: rendering and geometry | The stacked preview combines an oversized table with a square 3D viewport. Compact gives the main plots only about half the canvas width and spends the rest on redundant context. Fixed aspect constrains a wide, short stacked row; stretching it would misrepresent geometry. | `generate_mockups.py` table/header/splitter; `generate_stacked_mockups.py` grid; `generate_compact_mockups.py` main rectangles and context strip; installed `Axes3D.apply_aspect` square viewport. |
| B: editing and information priority | Thumbnails and 13 facts repeat data without helping the primary editing task. Current selection works from table to plot only; name changes can disconnect selection from the valid preview. Enlarged bounds and zero name-box collisions do not establish readable or selectable markers. | Original stacked/compact FHD and small-window images; `generate_preview_options.py` row selection and button-release handler; compact meanings panel. |

Both reject the earlier enlargement claim as sufficient evidence: the prior
20°/30° camera was changed to 12°/18° along with fitting. Approximately 19% of
the change in projected width/height ratio comes from that camera change.
Read-only projection calculations also identify cross-face overlap at B10/T2
under the compact camera. These calculations are diagnostic; they are not new
widget renders or an accuracy acceptance run.

Reviewed originals include:
[A 3D](mockups/marker_profile_138/revised/A-32-1920x1080-3d.png),
[B paired](mockups/marker_profile_138/revised/B-32-1920x1080-back.png),
[stacked](mockups/marker_profile_138/stacked/stacked-32-1920x1080-both.png),
[compact](mockups/marker_profile_138/compact/compact-32-1920x1080-both.png),
[compact small](mockups/marker_profile_138/compact/compact-32-820x600-bottom.png),
[compact process 125%](mockups/marker_profile_138/compact125/compact-32-1920x1080-both.png).
The last two layouts remain rejected review history.

## Debate and resolutions

| Question | Resolution |
| --- | --- |
| 1:1 or taller upper 3D? | Default upper/lower 55:45 with a user-adjustable vertical splitter; actual visible bounds govern fitting. |
| Fill remaining width with context? | Remove six miniature plots and the permanent facts table. Restore space to the two main views and their pan/zoom. Do not distort geometry or promise every wide row will be filled. |
| Six face buttons or dropdown? | Wide: one compact row of face name/count/color buttons serving both selection and legend. Narrow: dropdown. No repeated thumbnails. |
| All-gray background markers or preserved face colors? | Retain each face's hue; strengthen the viewed face and soften the other faces. Selection readout retains the selected marker's declared face. |
| New renderer, origin gizmo or label rails? | Keep Matplotlib. Renderer replacement does not by itself fix aspect/layout or picking. New gizmo/triad and label rails are not required for this delta. Preserve signed local axes and complete Rules. |
| Dense labels? | Names=All by default; explicit Names=Selected plus hover/pick/zoom. Do not silently hide names or move marker geometry. |

## Agreed next-mockup packet

All sizes below are estimates for a future mockup, not measured results or pass
thresholds. The user's table-left, upper-overall-3D/lower-face-2D structure stays.

1. Use two independent canvases in a vertical splitter. A default dialog around
   1280×960–980 logical pixels must be clamped to the actual available screen.
   Default table width is about 440–480 pixels with useful column widths and
   approximately 26-pixel rows. FHD maximization retains the same hierarchy and
   the preview's full available width; no arbitrary maximum-width cap.
2. At FHD, target about 480/400 logical pixels for upper/lower panels after
   compact shared controls, header and fixed actions. Approximate projected
   box/Back-face sizes of 500×405 and 560×335 pixels are planning estimates.
   Fit box corners, axes and selected annotation together at one XYZ mm scale.
   Use a consistent 20°/30°, Y-up orthographic baseline. Keep clipping within
   each canvas; do not disable clipping globally to allow pane overflow.
3. At 820×600 retain Markers/Preview/Rules tabs. Each plot gets roughly 330–370
   pixels of content height, with only the plot area scrolling. Readout, state
   and Preview/Reset/Save/Apply/Cancel remain reachable. FHD PNG resolution and
   the dialog's logical size are separate requirements.
4. Link table and 2D point/name selection in both directions. A 3D hit with
   multiple candidates opens a short ID + declared-face menu instead of choosing
   an arbitrary nearest marker. Preserve selection through rename via stable
   editing-row identity and preview-snapshot mapping. Preserve camera and
   per-face pan/zoom through selection and Preview; Fit restores context.
5. Show identity/source/box dimensions, draft/applied/compatibility state and
   selected ID/XYZ/face/normal concisely. Rules keeps the complete read-only
   origin, signed local axes, world +Y, prefixes, time meaning and half-turn
   mapping. Move the full-width Preview button to an ordinary fixed action.
6. Plot/count/normal read from the last valid Preview snapshot; current edits
   mark it stale. The viewed face is distinct from the selected marker's face:
   viewing Front must not change M2's Bottom declaration or `[0,-1,0]` normal.
   Preserve explicit Apply, reset target, cancel, unsupported and legacy blocks.

## Acceptance evidence needed

- Compare geometry/camera/point size/font held constant; separate camera-choice
  experiments from fitting/layout changes. Record actual viewport and visible
  box/axis/name bounds, not just projected box width.
- Confirm all public-32 rows and final T3 selection, all six face views including
  empty Bottom, public-18 M2 `[38,-60,-18]` mm, and exact label/face/normal meaning.
- Demonstrate plot-to-table selection, cross-face overlap candidates such as
  B10/T2 and F2/B1, long/dense names and unambiguous point/name/leader association.
  Zero label-box collisions alone is insufficient.
- Demonstrate rename preserving selection, coordinate edit marking preview
  stale, Preview preserving applied state, reset/cancel/Apply distinctions, and
  no unexpected camera/zoom reset. Inspect rotation clipping and pane boundaries.
- Preserve geometry/hash, lineage, prefix/face rules, collinear-face allowance,
  legacy unknown/blocked semantics, single_drop and correction default OFF.
- Capture original FHD, 820×600 and process-125% images, then separately verify
  actual native Windows 125% screen/input. Existing black captures and activation
  failures remain pending; process-scaled widget renders are not native passes.

#113 registration remains excluded by the user's prior decision. #104 physical
validation is separate; the public virtual fixtures do not establish measured
experimental accuracy. #139 onward and #143 features remain outside this work.
