# Independent product widget review

Last Reviewed: 2026-11-12

This review is independent of product source implementation. The reviewer edited
only the verification script and public UI evidence. The current reproducible script
is `scripts/gui_metric_parity_product_check.py`; it uses the native Windows Qt platform with
the existing default font and no OS/font changes. `product_checks.json` records
the exact source hashes, logical clients, device ratio, input checks and results.

The checked-in re-run command is:

```powershell
python scripts/gui_metric_parity_product_check.py
```

It uses the current checkout, generates only public fixture inputs under
`product_inputs/`, and writes actual executed checks rather than a fixed expected
check count. The historical broad and focused runs below remain distinct records;
the current script includes all final diagram and initial-layout checks.

## Observed product behavior

The completed broad run executed **176 checks: 176 passed, zero failed**. It saved
37 Qt buffer captures plus separate native-window and VTK render captures. These
counts describe this script, not physical accuracy, experimental equivalence or
completion of all issue acceptance requirements.

After the final initial-layout and full-size-image changes, a focused reinspection
executed **262 checks: 262 passed, zero failed**, with 36 captures. Its separate
`product_focused_checks.json` records those source hashes and results. These checks
overlap the broad run and are not 438 independent feature or numerical cases.

Qt 6.10.1 used the native Windows platform, existing Malgun Gothic (맑은 고딕)
9pt and device pixel ratio 1.0. Every requested 1510×800, 1100×720, 820×600,
1100×760 and 640×480 client in the report matched its actual client size.
EN/KO instances were created through the existing language initialization path.

The processing input is a generated supported 21-sample observation CSV. The
script loads it, saves a real 0.1–0.3s, 11-sample slice with explicit dimensions,
and loads that slice into the actual Step 1.5 widget. It does not run processing,
optimization or a solver. Result views load a saved public registered-contact
fixture from the independent contract suite, with a literal zero Beta series for
the identity-pose graph. The copied result is the same trial; the comparison shows
two files and one observation group. These are generated display/contract fixtures,
not measured experiments or independent repeat trials.

| Initial processing client | Settings columns | Top | Right | Log | Footer |
|---|---:|---:|---:|---:|---:|
| 1510×800 | 5 | 427 | 329 | 104 | 48 |
| 1100×720 | 3 | 342 | 299 | 90 | 48 |
| 820×600 | 2 | 263 | 268 | 80 | 48 |

The final source seeds the specific responsive pixel targets once while retaining
the existing splitter stretch behavior. Actual heights differ by up to three pixels
because the splitter handle consumes space. User splitter changes survive
Single/Batch visits, an actual height +40px/restore roundtrip, and hide/show.
No settings horizontal scrolling is required; Advanced settings
and the enabled range field are fully reachable in their scroll. Fixed footer
actions remain visible. Moved controls remain within the execution lock.

The actual Step 2 CAE tab retains the fixed export command and scrolling inputs.
The new velocity option starts OFF/disabled, enables only with Manual Height,
and clears when leaving that mode. A short persistent mode/time summary remains
visible. Core summary values and reasoned unavailable rows now remain visible in
the narrow table. The script does not substitute a successful serializer check
for the separate export failure-preservation suite.

Both Guide wrappers instantiate the same product renderer. After the final two
saved-Details fallback registrations, a fresh final-cardinality check reached all
61 entries through real Qt Tab events in EN/KO, with every heading visible and
horizontal maximum zero; see `product_registry_recheck.json`. This cardinality
is an observation, not the semantic metric acceptance criterion.
Content widths 999/1000/1001 select 1/2/2 columns. After those
reflows, the 640px client has a 596px viewport and 596px content, with hidden
horizontal scroll maximum zero. Hidden targets clear filters and receive focus;
unknown targets select Interpretation at its top. Empty filter text, missing-image
text alternatives, Close/Escape hide and same-instance reopen pass.

Each diagram group now has a keyboard-accessible View diagram command. In EN/KO
at both 640×480 and 1100×760, actual Tab then Space opens a separate owned window.
That window retains the original image pixel size and aspect ratio; users inspect
the original text with scrolling rather than a reduced overview. Keyboard arrows
reach both image edges. Close remains fully visible and reachable, Close/Escape
hide, reopening reuses the same object, and missing-image text remains available.
The 640px window deliberately shows a scrollable part of the original; it does not
claim to fit the entire original image simultaneously.

The installed Matplotlib Customize dialog was opened, its labelled Title field
changed, and Apply clicked. Existing axis Text font sizes 13/14 survived Apply and
the product redraw. This Matplotlib dialog has no axis-label font-size editor;
13/14 were set on the real Text objects before opening it. They were not entered
through a nonexistent dialog control.

The comparison's ordinary Experiment info text omits raw hashes, full paths and
processing JSON. Synthetic input is explicitly labelled. Diagnostics starts closed,
retains raw evidence in a separate read-only window, and opens on an explicit action.
Two actual VTK viewers and box actors were created. Their framed renderer outputs
are saved as `product-vtk-render-*.png`; the camera was fitted to each loaded box
actor only for inspection, without changing data. Qt/native-window captures omit
the OpenGL child image on this environment, so those composite captures alone do
not demonstrate the 3D scene. The separate VTK buffers show the rendered box.
The literal Beta series populates the actual comparison graph. Native desktop
input automation and rendered marker-tracking behavior are not established by
these box-only fixtures.

## Findings and reinspection

1. The first product render's long summary labels expanded the metric column until
   the value column was outside the narrow panel. The implementer bounded/wrapped
   the columns. Reinspection shows both metric and value at 820×600.
2. Target-card QSS initially styled all descendant labels, added distracting borders
   and widened hidden horizontal content. It now targets the card identity and
   focus state. Reinspection shows one card border, unclipped text and horizontal
   maximum zero.
3. First-entry keyboard focus initially left its heading above the viewport. The
   product now scrolls to each focused card's heading. Every registered entry
   passes EN/KO traversal with visible headings, including the fresh final
   61-entry recheck.
4. Selected-time presentation initially printed `0.07200000000000001 s`. It now
   displays `0.072 s`; the stored sample was not changed.
5. The posture figure originally clipped its title and overlapped axis/corner/Beta
   labels. The implementer replaced it with a clear 2D projection and external
   callouts. The current full-size original has no observed annotation collision.
   Impact and Contact originals also have no observed collision.
6. A verification-script draft used the first `QLineEdit` as Customize's Title;
   Qt child order did not identify that field. The reviewer corrected the checker
   to use the visible `QFormLayout` label. The actual Title/Apply operation then
   passed; no product change was needed for that checker error.

7. Inline figures reduced to approximately 500px columns made their annotations
   too small to read comfortably. The implementer added original-size viewing.
   The first Posture View diagram button was reachable by Tab but almost entirely
   above the viewport (only six pixels visible). The same focus-reveal handling
   now covers diagram buttons. Reinspection passes all three groups in both
   languages and both client sizes, including full button visibility, original
   pixels, keyboard image panning, fixed Close, reuse and missing-image fallback.

No unresolved blocking visual defect remains in the reviewed scope. The original
image window resolves the annotation-readability observation; the inline image is
the compact overview, with readable definitions below it.

The figures use English annotation text, including in the KO Guide; descriptor
definitions/cautions provide the Korean explanations. Earlier captures exposed
English normal-field labels and phase/reference text in KO. The implementer added
translations, and the fresh KO comparison reinspection passes 13 checks; see
`product_language_recheck.json` and the updated KO comparison captures. Final
Guide phase/reference text uses the Korean descriptor fields. Raw diagnostics
retain original technical text. No runtime language-switching feature was tested
or claimed.

Actual OS125: **Not run**. Native desktop input automation: **Not run**.
Human GUI acceptance: **Pending**. Measured physical accuracy and private adoption:
**Not evaluated**. Batch execution/failure cases, export byte goldens and numerical
owners are covered by separate assigned checks, not inferred from this UI review.

## Late Selected series recheck on Qt 6.12

The on-demand Selected series entry was reviewed separately after the earlier
captures. The exact interpreter was `tmp/issue188-qt612/Scripts/python.exe`:
Python 3.13, PySide6 **6.12.0**, Qt **6.12.0**, native Windows Qt platform.
This addendum does not relabel the earlier Qt 6.10.1 evidence as a Qt 6.12 run.
No other main GUI run occurred concurrently with this check.

Executed commands, each with exit code 0:

```powershell
tmp/issue188-qt612/Scripts/python.exe -m pytest tests/test_gui_metric_parity_workflows.py -k real_point_combo_series_contexts_reuse_one_explicit_card -q
tmp/issue188-qt612/Scripts/python.exe -u scripts/gui_metric_parity_series_check.py
```

The targeted existing test executed both EN/KO cases: **2 passed, 19 deselected**
in 6.52s. The independent bounded checker executed **434 passing UI conditions,
zero failures**, and saved ten `product-series-*.png` captures. Its UTC start/end,
runtime, source hashes, actual clients/font/DPR, conditions and scope are in
`product_series_qt612_recheck.json`. Relevant source did not change during the run.
The checker subprocess completed and released its GUI before the final main GUI
checks resumed.

The actual Results Point-target combo drove the owned Guide at 1100×760 and
640×480 in EN/KO. Eight exact column tuples cover per-row posture, world and
analysis-frame derivatives, a rotation-vector component, legacy corner category,
and corner heights. Two corner-height objects and a corner/centre velocity pair
exercise full-tuple identity despite shared component labels. The public in-memory
input deliberately has missing series values: the definition remains available
without inventing a sample value.

Each tuple received the correct on-demand `step2:series:` identity, declared unit,
row-specific context and explicit distinction from precontact/peak/fit quantities.
Exactly one dynamic card was present; repeating a tuple reused its card, replacing
it removed and deleted the old card, and the host reused the same Guide object.
Unknown input removed the stale dynamic entry and selected Interpretation at its
top. Valid input restored the definition; summary focus cleared the row-specific
card. Hidden-target filters, actual Tab access, visible headings, horizontal fit,
Escape/reopen and rapid queued replacements passed without an asynchronous Qt
callback exception. The captured text is readable in both requested client widths.

These repeated UI conditions are not 434 independent physical or numerical cases.
This late check ran no pipeline, optimizer or solver, did not perform an external
desktop click, and adds no OS125 or human-acceptance claim. No blocking defect was
observed in this late Selected series scope.

## Controlled Qt platform diagnosis

Two later narrow-window assertions failed in a 40-test run which specified
`QT_OPENGL=desktop` but did not specify the Qt platform. Collection imports
`tests/test_results_analyzer_experiment_summary.py`, whose existing module-level
`os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')` selects offscreen before
QApplication is created. Desktop OpenGL alone does not select the Windows platform.

The read-only Qt 6.12 probe measured actual platform **offscreen**, Sans Serif 9pt:
the processing split changed `[438,366]` to `[464,340]` after mode/reload and its
live content-derived explicit minimum changed 366 to 296. The CAE scroll viewport
was 254px while content and the new checkbox minimum were 360px. These reproduce
both reported assertions. No VTK viewer was created by this offscreen probe.

The same plot-only probe on actual platform **windows**, with the existing native
9pt font, retained processing split `[528,275]`; its explicit minimum was 240px.
CAE viewport/content were both 241px and the checkbox minimum was 180px. The exact
two assertion nodes also passed independently in the controlled Windows setting.

The full unchanged five-file, 40-test order was then run on source `593c669` with
both `QT_QPA_PLATFORM=windows` and `QT_OPENGL=desktop`. The actual QApplication
platform was printed as **windows** before `pytest.main`. Result: **40 passed,
zero failed in 53.98s**, exit code 0. The JUnit output is
`tmp/parity-affected-windows-control.xml`; the persistent measured evidence and
exact file order are in `product_qpa_control_qt612.json`.

No product correction, font/OS change, test edit or weakened assertion was used.
This result establishes the controlled declared native Windows Qt configuration;
it does not relabel the failed offscreen run as passing. The checker process exited
before GUI ownership was handed back to the main agent.
