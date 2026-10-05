# Independent profile UI mockup review — #138 / PUB05

Last Reviewed: 2026-10-06

Current status, 2026-10-06: the user approved the final interactive mockup.
Production software and automatic verification passed final independent review.
Required clean-commit hosted CI gates merge; native follow-up stays open. Historical mockup review states
below describe their own revision, not current approval. Native external input
and actual OS125% remain unexecuted; real experiment validation is separate.


Plan Spec: ISTA6A-PLAN-20261001-v1

## Scope and reviewer

User-requested independent review of terminology, controls/menu placement and
the actual current profile editor mockup. Reviewer: `profile_ui_review`,
GPT-6.1 Sol / high, read-only, no additional agents or file edits. Main owns all
corrections. The earlier two Sol/xhigh participants were design advisors only.

Base/HEAD: `1f654faddd44eedf7ff6e807d85f5e08559f8b13`; branch
`issue138-marker-profile-semantics`, dirty documentation/prototypes. Production
code is unchanged. User liked the 1280×960 table/stacked-preview layout; formal
mockup approval remains distinct from independent review. #113 registration is
excluded by user decision; #104 physical validation is separate, with no verified
real experimental dataset. #135/#136/#137 delivery is preserved. No #139/#143.

## Initial independent verdict

**Changes required.** No P0/P1. Four P2 UI approval blockers and two minor P2
notes were reproduced by the reviewer using actual PNGs and read-only Qt/QTest
diagnostics. Original evidence: `mockups/marker_profile_138/wording/` and
`wording125/`, 13 states each. The reviewer read all three generator dependencies,
AGENTS, the requirements/design record and reviewed default/FHD/small/error/
legacy/incompatible/overlap/last-row images at both DPRs.

| Finding | Reproduction and impact | Main correction |
| --- | --- | --- |
| P2 blocker: 3D axis clipping | `generate_reviewed_mockups.py`, original `fit3`; default32 1280×960/DPR1.25 clips Local Z. Label y=-5.8487 physical pixels, height65.8482, canvas962.5×423.75. | Fit rendered corners/axis labels/ticks/selected annotation using DPR-aware canvas margins and assert containment; preserve common XYZ scale. |
| P2 blocker: wrong invalid cell | Inherited `generate_mockups.py:199`, B2/Y=`bad` highlights F1/X; repair leaves F1/X pink, raw conversion message omits the field. | Mark actual invalid numeric cells, name marker/field, clear repaired brushes, preserve stale valid preview and Preview/Save/Apply gates. |
| P2 blocker: misleading Copy | Inherited `generate_mockups.py:152`, Copy preset resets F1/X22 to21 under the same customID, losing edits. | Remove/disconnect the redundant copy control in an editor already holding a copy; copy entry remains in the export-window mockup. |
| P2 blocker: narrow 2D controls | 820×600 at scroll bottom shows the 2D plot but hides heading/Names/Pan/Zoom/Fit. | Move 2D heading/controls outside plot scroll; assert controls stay visible. |
| P2 minor: Pan/Zoom state | Clicking Pan then Zoom leaves both pressed although only zoom is active. | Synchronize pressed states with actual navigation mode. |
| P2 minor: unlabeled selection/normal | `B1 Back (...) n=(...)` does not explain selection or vector meaning. | `Selected: ... Normal: ...` and concise outward box-local normal tooltip. |

The reviewer accepted the wide hierarchy, clarified face counts, overlapping-hit
candidate ID/face menu, explicit Apply and legacy-blocked wording as suitable.

## Final same-reviewer verdict

**APPROVE — current UI prototype only.** Outstanding findings in this bounded
review: P0=0, P1=0, P2=0. The same read-only reviewer confirmed all six findings
resolved after Main's corrections and final fresh images.

Final source SHA256:
`e3da9c8d9d5a8177e120ba92f29763ae98ed7c667304eb9a8aa09a506e88b6af`.
Both evidence manifests match that source. Final run IDs:
`reviewed-20261005T042425Z` (DPR1) and `reviewed-20261005T042426Z` (DPR1.25).
Main verified all 40 original PNG dimensions against manifests and empty stderr.

The reviewer independently ran live DPR1.25 Qt/QTest checks for actual axis
label extents, B2/Y invalid input and repair/gates, exclusive Pan→Zoom→off,
M2's selected normal while viewing Front, and the full small-window 2D canvas.
Default Local Z label is contained (y=11.8809 physical pixels). Final small
2D canvas y=1, height275 logical pixels in a276-pixel viewport: fully contained
at bottom scroll. Its earlier top-strip cropping note is closed. Narrow 3D is
intentionally scrollable; whole3D-fit at first scroll position is not asserted.

Actual final default1280,18/32FHD,overlap,last-row,invalidB2,legacy/incompatible,
wide/narrow Rules,narrow Markers,small upper/lower images were reviewed at the
applicable DPRs. The reviewer found View face (marker count), Front (11),
Preview — not applied, Selected and Normal clear/natural/concise; Rules readable
and control positions suitable. Reset view and Reset to source have separate
contexts. No edits or additional agents were made by the reviewer.

## Main correction evidence

Fresh outputs: `mockups/marker_profile_138/audited/` and `audited125/`.
Both generation commands exited0: 20 states per DPR and prototype QTest passed;
each `render-stderr.log` is empty. Extra images show wide/narrow Rules, narrow
Markers and the B2/Y invalid-cell case. Main also inspected default/narrow/125%
actual images. Same-reviewer re-review approved the final prototype above.

```powershell
$env:QT_SCALE_FACTOR='1'
.venv/Scripts/python.exe docs/visualization/mockups/marker_profile_138/generate_reviewed_mockups.py --output docs/visualization/mockups/marker_profile_138/audited
$env:QT_SCALE_FACTOR='1.25'
.venv/Scripts/python.exe docs/visualization/mockups/marker_profile_138/generate_reviewed_mockups.py --output docs/visualization/mockups/marker_profile_138/audited125
```

Windows11, Python3.13.5, PySide6 6.10.1, Qt windows. Original FHD PNGs are
1920×1080 at DPR1 and 2400×1350 at DPR1.25. 820×600 is logical;125% output is
1025×750. WindowsOS scaling remains100%;125% is a Qt-process override.
RunReport-style evidence.json records schema/plan, source digest, commit/dirty,
command/environment, input public geometry hashes, actual dimensions, static
seed-not-applicable, exact geometry invariance, fresh captures and limitations.
QTest independent expectations include M2=[38,-60,-18]/BOTTOM/outwardnormal
[0,-1,0], F1/X21→22 Preview retaining applied, Reset restoring21, B2/Y malformed
input marking only that cell, repair clearing, and exclusive Pan/Zoom states.

Failed correction attempts are recorded in `prior_attempts`: reading Matplotlib
`get_ticklabels` after draw reset projected 3D label positions; use rendered
`majorTicks.label1` instead. Setting validation backgrounds emitted `itemChanged`
recursively; block table signals during background updates. These failures were
corrected before the successful fresh renders; partial failed attempts are not
acceptance evidence.

## Acceptance boundaries

This review can approve a UI mockup only. Production semantic identity/version,
compatibility execution, persistence/export/worker propagation and final CI are
not implemented or accepted here. Save JSON and legacy/compatibility messages
are fixtures. Native capture/activation previously failed with black output;
native external input, actual OS125% and real experimental accuracy remain
unexecuted/unavailable. User mockup approval and later production acceptance
must not be inferred from automatic render/QTest results.

## Final exploded-face review (supersedes the earlier 3D presentation)

**APPROVE — new exploded-face UI prototype only.** The same independent
GPT-6.1 Sol / high reviewer inspected all20 final original PNGs and ran separate
read-only DPR1.25 Qt/QTest diagnostics. Outstanding P0/P1/P2 findings:0.
Main authored all corrections; no reviewer edits or additional reviewers.

Reviewed source SHA256:
`f987039755f51a50288d581a167a5e3821c187c11bc28c786b317a25890b8e46`.
Final evidence: [DPR1](mockups/marker_profile_138/visibility_final_v9/evidence.json)
and [DPR1.25](mockups/marker_profile_138/visibility_final_v9125/evidence.json).
Both commands exited0 with empty stderr:10 fresh captures and50 actual selected
layout renders per DPR. The reviewer checked source/dependency hashes and every
PNG's actual pixel dimensions. Runs remain at the base HEAD with dirty standalone
prototypes/documentation; production code is unchanged.

The three earlier new-mode P2 findings are resolved: example18 Right title no
longer hides selected B1; example32 selected B1's badge no longer hides B3/B10;
F4/F10 labels have short, unambiguous leaders next to their Front markers. Actual
marker disks, selected rings, ID/title badges and rendered leader paths have
zero measured occlusions/crossings in the58 readability records per DPR. Some
leaders reach93–96 logical pixels in default/small views. The reviewer found
them individually traceable through empty space without crossing other markers,
names or leaders, so they are not outstanding findings. All-label positions
remain stable across selection changes.

Independent actual badge QTest clicks B3/B10/F4/F10 selected their canonical
table rows/readouts at DPR1.25. The reviewer independently checked unchanged
source coordinates, all32 stable ID positions, Box/Exploded switches, literal
M2 source[38,-60,-18]/display[38,-200,-18]/normal[0,-1,0], Names counts,
F1/X21→22 Preview and F1→F9 Preview cache invalidation with applied unchanged,
and Reset to source restoring the fixture. The reviewer accepted terminology,
face counts, display-only tooltip, separate Reset view/Reset to source, fixed
actions and narrow-window scrolling/error accessibility.

The approved configuration is B: Y-up elevation25°, azimuth50°, roll30°,
R1.0 and55:45 stacked preview. Approval covers public18/32 and the inspected
1280×960,1920×1080,820×600 logical windows at Qt-process100/125%. It does not
guarantee every imported geometry/camera is overlap-free. Actual OS-native125%,
external native input/capture, production semantics/persistence/export/worker/CI
and real experimental validation remain unexecuted or outside this UI review.
Earlier native capture/activation failures are retained. User final mockup
confirmation was requested after showing the final original FHD PNG; it is
separate from this independent approval. Earlier/interrupted attempts and
pre-show constructor layouts are not final acceptance evidence.

## Navigation question and remaining verification

After the final image was shown, the user asked whether the3D view supports
rotation, zoom and movement. Main inspected the actual prototype and installed
Matplotlib source: the3D Axes default left-drag rotation, middle-drag pan and
right-drag zoom remain connected; `ReviewedPrototype.wheel3` adds wheel zoom,
and Fit/Reset view are explicit controls. This is source inspection, not new
navigation acceptance. The final review above tested selection and camera
restoration, not free mouse rotation/pan/zoom sequences or their redraws.
Production verification must cover click versus drag, name/point alignment
after movement, mode/selection redraw preserving the current camera/limits,
and Fit/Reset restoring the full scene. Arbitrary rotation can superimpose
projected faces; the approved default and2D face view remain recovery paths.
Native external mouse input is still unexecuted.

The user subsequently proposed individual face dragging and raised performance
concerns. A bounded [navigation/cost review](marker_profile_138_navigation.md)
with the same read-only reviewer found3 P1 interaction blockers and1 P2 cache
bound issue in extending the current prototype. Corrected sequential100/125%
cost probes are measurement-only, not responsiveness passes. Verdict:
**CHANGES REQUIRED for new navigation/face drag**. Existing static B approval
is retained; it does not cover these new controls. That verdict applies to the
original static implementation. Main subsequently authored the separate Qt
interactive replacement. Fresh v10 renders/QTest at100/Qt125% passed; the same
read-only reviewer is rechecking source, gestures, terminology/readability,
source preservation and work bounds. This new review is pending; the original
P1/P2 findings are not closed by Main's tests alone. Production remains unchanged.
See [new source and evidence](marker_profile_138_navigation.md).

## Corrected interactive mockup review

**APPROVE — implemented standalone interactive #138 UI mockup only.** The same
GPT-6.1 Sol/high read-only reviewer confirmed the two new P2 findings and the
subsequent minor toolbar note resolved; no P0/P1/P2 remain. It accepted naming,
menu/control placement, face-title drag handles, separate view/source Reset,
small scrolling, fixed actions and error visibility. Minor nonblocking note:
explicitly prefix the pinned narrow face toolbar with2D to distinguish its Pan/
Zoom/Fit from the3D viewport below. Main corrected the title and fresh affected
caption-only checks passed; the same reviewer inspected all12 new original PNGs
and source/dependency/pixel/logical/DPR evidence and approved that small delta.
It performed no additional Qt run for the caption-only recheck.

Viewport SHA256:
`f4192d9e479f84605b9eeff6a75f4ed113638dc332ee812c251decd8795c0b90`;
full v11 harness SHA256:
`39850a771dd92d3d0706dd788ad5dc3ad1da1acb0c34aae57a9b654d4b27a643`.
Fresh [DPR1](mockups/marker_profile_138/navigation_v11_100/evidence.json) and
[DPR1.25](mockups/marker_profile_138/navigation_v11_125/evidence.json) each have
10 PNGs,150 stable selection layouts and64 extra painted zoom.3/.5 selection
layouts. Both exit0/empty stderr; source/dependency hashes and actual pixel
dimensions matched at those runs. The reviewer rechecked representative changed
PNGs and pixel-compared unchanged images against previously inspected v10.

Independent sequential QTest at both DPRs confirmed middle click keeps selection,
unrelated release/competing press preserves the captured left gesture, and only
matching left release ends it. Actual QPainter badge recording at public32
zoom.5 F10/F1 and zoom.3 T2 confirms selected fallback avoids other names,
face titles and existing leaders and enters the hit registry. Exact source/draft/
preview/applied preservation passed. The review used cwd
`C:/SourceCodes/BoxMotionAnalyzer`, PowerShell `PYTHONDONTWRITEBYTECODE=1`,
`QT_SCALE_FACTOR=1` then `1.25`, and `.venv/Scripts/python.exe -c $reviewCode`.
Both exit0; final output `BUTTON+FALLBACK INDEPENDENT V11 PASS DPR 1.25`.
Evidence is tool transcript only (chunks `3c0fb6`, `32def0`), no saved file.

The earlier three P1 and cache P2 are resolved by one Qt gesture owner, retained
buffers, no2D reconstruction or name solve during motion, cancellable keyed idle
placement, recoverable limited-name fallback,8-entry LRU and256-entry samples.
The8ms/100ms scheduling targets are cooperative: one bounded repair step can
perform up to5 candidate batches before the next clock check. No strict timing,
native latency/FPS/RSS, universal overlap-free view or performance-budget pass
is claimed. This display-state rule hash is not production analysis semantics.

Approval covered public18/32,1280/FHD/820 and Qt process100/125% only. The user
subsequently approved the final interactive mockup on 2026-10-06.
At that prototype boundary, production semantic identity/compatibility/legacy/
persistence/export/worker/CI, actual OS125% and external native input/capture
remained unverified. #104 is a separate real experiment track with no validated
dataset assumed. No reviewer edits or new agents were made. Current caption
source/evidence are recorded in the [interaction record](marker_profile_138_navigation.md);
v11 unaffected full verification is reused for that caption-only delta, not
rerun or relabeled fresh.

## Final production review

The same read-only GPT-6.1 Sol/high reviewer approved the final34-file software
delta after Main corrected the P1 declared-source local-rank bypass and P2
silent Generate block. No P0/P1/P2 remain. It reviewed actual code/consumers,
state transitions, persistence, stale results, independent oracles, terminology,
control placement and final60 original editor PNGs plus blocked-export screens.
The [unaltered report](marker_profile_138_independent_review.md) binds the exact
snapshot/file hashes and distinguishes fresh corrected-gate probes from reused
unchanged algorithm checks after the final reason-only correction. Display-only
offsets preserve physical centre/results; a mapping change does not assert
numerical pose change. Required hosted CI remains the merge gate. Native/actual
OS125%, #104 measured accuracy and issue-wide completion remain unverified.
