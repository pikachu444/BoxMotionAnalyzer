# Profile 3D marker identification advice — #138 / PUB05

Last Reviewed: 2026-10-06

Current status, 2026-10-06: the user approved the final interactive mockup.
Production software and automatic verification passed final independent review.
Required clean-commit hosted CI gates merge; native follow-up stays open. Historical mockup review states
below describe their own revision, not current approval. Native external input
and actual OS125% remain unexecuted; real experiment validation is separate.


Plan Spec: ISTA6A-PLAN-20261001-v1

## Request and scope

After the independent UI prototype review, the user reported that individual
3D markers still could not be distinguished and requested agent opinions.
Main spawned two read-only GPT-6.1 Sol / xhigh design advisors,
`marker_visibility_a` and `marker_visibility_b`. They inspected current actual
`audited`/`audited125` PNGs and rendering/selection code independently, discussed
their alternatives, and then inspected Main's actual new comparison renders.
They edited nothing, created no agents and issued no formal approval verdict.
The single formal reviewer remains `profile_ui_review`.

Base/HEAD `1f654faddd44eedf7ff6e807d85f5e08559f8b13`, branch
`issue138-marker-profile-semantics`; dirty prototype/documentation work only.
The independently approved `generate_reviewed_mockups.py` is unchanged. New
comparison subclass: `mockups/marker_profile_138/generate_marker_id_options.py`.
No production code, profile identity or physical tolerance was changed.

## Findings and actual comparison

Both advisors found that existing dots were already about13 logical pixels,
with dark borders. Only the selected B1 had an ID: color or a larger dot cannot
tell B2 from B3. Other-face fill alpha.38 makes colors pale; this fade represents
the selected view face, not physical distance. F3/B2 is a true projection
overlap, so enlarging dots makes separation worse.

Main rendered exactly two name-display alternatives with identical geometry,
camera20/30, common XYZ scale, point area85 square points and existing layout:

- [View face,32/default1280](mockups/marker_profile_138/marker_ids/32-view-face-1280x960.png): current-face IDs plus selected ID. Other faces remain unnamed until selected or All is chosen.
- [All,32/default1280](mockups/marker_profile_138/marker_ids/32-all-1280x960.png): all32 IDs visible.
- [View face,32/FHD original](mockups/marker_profile_138/marker_ids/32-view-face-1920x1080.png)
- [All,32/FHD original](mockups/marker_profile_138/marker_ids/32-all-1920x1080.png)
- [All,18/default1280](mockups/marker_profile_138/marker_ids/18-all-1280x960.png)
- [All,32/small820](mockups/marker_profile_138/marker_ids/32-all-820x600.png)

Only name badges move in screen space. True marker centers never move. Regular
IDs use10pt dark text, white.94 background and thin.6pt leader lines; the selected
12pt bold ID/ring is retained. Other-face fill is.65, current-face fill.95 and
opaque dark edges are retained. A local 3D Names control offers View face / All /
Selected independently of the existing 2D Names control. Label picking selects
that exact ID; point picking retains the existing multiple-ID/face chooser.

Initially A preferred View face and B preferred All. They agreed to compare both
without presuming All was unreadable. After inspecting actual All32/default/FHD
and View-face renders, **both recommend All as the eventual default** for the
user's individual-identification goal, with View face as a focused alternative.
FHD All32 and default All18 were considered useful/readable. This is advice;
the user has not approved the new name-display variant.

## Remaining limitation and bounded next adjustment

In All32/default1280 and820, first-valid-position greedy placement sends some
B4/B8/B12 labels farther away. Their leaders cross other points/names and are
harder to trace. Neither advisor treats zero overlapping label rectangles as
proof of readable point/label association. The recommendation is to score legal
positions using short leader length plus penalties for crossing another name,
unrelated point or leader; try more nearby angles and bounded cluster-first or
second-pass placement. Preserve point/camera/box geometry. This adjustment is
not implemented or approved in these comparison images.

Names cannot undo a true coincident projection; explicit label selection and the
point candidate chooser remain needed. No size increase, six-shape palette,
point jitter, exploded geometry or general renderer rewrite is recommended.

## Prototype evidence

Commands, each exit0:

```powershell
$env:QT_SCALE_FACTOR='1'
.venv/Scripts/python.exe docs/visualization/mockups/marker_profile_138/generate_marker_id_options.py
$env:QT_SCALE_FACTOR='1.25'
.venv/Scripts/python.exe docs/visualization/mockups/marker_profile_138/generate_marker_id_options.py --output docs/visualization/mockups/marker_profile_138/marker_ids125
```

12 fresh states per DPR,24 total: public18/32 × View face/All ×1280×960/FHD/820×600.
OriginalPNG sizes at DPR1 are1280×960,1920×1080,820×600; at1.25 they are1600×1200,
2400×1350,1025×750. Windows11 / Python3.13.5 / PySide6 6.10.1 / Qt windows;
desktopOS100%, process override125%. Stderr logs are empty after final runs.
Both example hashes/coordinates are unchanged. QTest independently expects
All32, exact F3/B2 badge clicks selecting their IDs, Back12, SelectedB2 and
unchanged public marker coordinates. Per-image name IDs, bbox conflicts and
clipping are measured. No random seed is required for static geometry; no
physical accuracy tolerance or experimental acceptance is implied.

[DPR1 evidence](mockups/marker_profile_138/marker_ids/evidence.json) and
[DPR1.25 evidence](mockups/marker_profile_138/marker_ids125/evidence.json) record
schema/plan, commit/dirty, source digest, commands, scale, input hashes, fresh
captures, expectations/results and limitations. A failed first manifest write
(NumPy int64 counts were not JSON serializable) is recorded in prior_attempts;
counts were converted to builtin int before final fresh replay. Failed evidence
is not treated as a passed run.

## Sources and acceptance boundary

W3C recommends another identifying cue in addition to color, supporting direct
IDs rather than hue alone: [Use of Color](https://www.w3.org/WAI/WCAG21/Understanding/use-of-color.html).
Matplotlib documents point area and edge width increasing the visible footprint,
supporting restraint about bigger dots: [scatter](https://matplotlib.org/stable/api/_as_gen/matplotlib.pyplot.scatter.html).
ParaView describes point selection and ID labels as linked inspection tools:
[Selecting Data](https://docs.paraview.org/en/latest/UsersGuide/selectingData.html).
These inform design judgment; they are not a certification of this UI.

Earlier independent approval applies only to the unchanged audited prototype.
These new variants have design opinions and prototype checks, not formal review
approval/native input acceptance. Production semantic compatibility, persistence,
exports/workers and CI remain pending; native capture/activation remains blocked
by the recorded environment error. #113 registration excluded, #104 physical
validation separate/no validated real dataset, #139/#143 out of scope.
