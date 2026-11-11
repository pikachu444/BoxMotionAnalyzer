# Public GUI implementation and validation status (#177)

Last Reviewed: 2026-11-11

The public repository is the canonical GUI source. #177 changes the existing
widgets into fixed groups, tabs and action bars; it does not change calculation,
approval, source identity or saved-file semantics. Public implementation,
public validation, consumer adoption and real-data acceptance have separate
completion gates. No consumer or real-data completion is claimed here.

The user's current scope is the public repository only. Consumer repositories,
integration and adoption are a later roadmap, not a dependency of this chat's
public implementation, review or publication. No consumer path or internal
integration input is required to complete this public work.

Latest hosted candidate `b316b407af5c47b32a7b5f6084fee6289c2116d2`
failed public validation: 1,746 tests passed and three failed. The shared-core
job passed separately. The processing/source-identity/Simulation corrections
are implemented and have bounded local evidence below; Step 1 also received
the same full-field focus fix. Frozen-source integrated Qt 6.12/offscreen,
synthetic scale 1.25 checks passed **129 tests plus three subtests**. Independent
Step 1 and Simulation correction rechecks approved the inspected scope with
no P1/P2. Corrected production/tests/inventory are committed as `1fe0aa1`; the next documentation/hosted head and required hosted result are **Pending**.
Earlier local passes do not constitute a final hosted pass.
Current correction checks use offscreen execution only. Computer Use remains
stopped following the user's concern; no new desktop-capture run is implied.

## Source and historical checkpoints

| Record | Source/date | Meaning |
|---|---|---|
| #158 baseline | `d7d61435c89bacda0d87175c06887b1d85f24e2e`, 2026-11-09 | Historical shared-core/GUI checkpoint in [validation](../shared_core/validation.md) and [proposal](../shared_core/gui-proposal.md). Their counts and captures remain historical. |
| F1/F2/F3 original review | `d0c91f6a5355994f6e566ac76eff37f23823550a`, 2026-11-10 | Original input rejection, environment and status findings; not an inventory of defects still present on current main. |
| Public implementation baseline | `a6e5c0e0f41392408e9ab9022b14d53dd405ac1e`, 2026-11-11 | #177 reviewed baseline, including PR #176. Working-tree changes and evidence must be identified separately from this SHA. |
| F1/F2/F3 accessible source | [#177 follow-up comment](https://github.com/pikachu444/BoxMotionAnalyzer/issues/177#issuecomment-6784396536), consulted 2026-11-11 | Supplies the original review and states that the fixed #177 layout supersedes its Details toggle procedure. |
| Implementation revisions | `48e68fb` F1; `80c89fe` common; `fe7421b` flip; `fcf8444` processing; `ae35238` results; `f24ba72` Simulation; `5f44a54` Step 1; `e79ccd1` comparison; `80343c9` regression migration; `6265af4`/`c985a00`/`996a8dc` display/localization corrections; `4f60836` comparison plot bounds; `ae62f45` recorded-time display; `66efaf6` gap tooltip | These identify delivered changes and earlier local evidence; the later hosted candidate is `b316b407…`, and its public validation failed. Per-file capture digests identify captured source independently. |
| Latest hosted candidate / next candidate | `b316b407af5c47b32a7b5f6084fee6289c2116d2`: public validation **Fail**, shared core **Pass**; corrected production `1fe0aa1` with approved bounded reviews; next hosted head/run **Pending** | Captures with local changes are identified by their metadata and per-file hashes, not relabeled as a clean committed revision. No final hosted-pass revision is declared. |
| Post-failure correction source | Processing scroll, Step 1 review scroll, Simulation `mode_settings.py` and source-identity regression changes, committed as `1fe0aa1` | Frozen-source integrated 129 tests plus three subtests passed, independent corrections approved; commit `1fe0aa1`; next hosted result Pending. `66efaf6` is earlier local evidence, not the current corrected production source. |

The original review document SHA-256 is
`01597743f9ef567ece054f4346281492be803a47c3814341fbeef0fd9d309e7e`.
The local source copies `tmp/issue177-contract.md` and
`tmp/issue177-followup.md` are diagnostic inputs, not a separate consumer API.
Older #78/#106/#136/#137 native/Qt/capture evidence retains its original scope.

## Current public implementation

These entries describe the inspected and locally tested public code. Earlier
local integrated checks passed; later hosted public validation failed on three
cases. Corrections are implemented; frozen-source integrated and independent
correction checks passed as recorded below. The next candidate's required CI
remains pending. Data-selection tree expansion remains available; tool-panel accordion
and hidden collapse-state restoration are removed.

| GUI-ID / issue | Existing source and current change | Verification gate |
|---|---|---|
| GUI-01/02 / #178 | `src/utils/qt_sections.py`, `plot_toolbar.py`, language helpers, `src/launcher.py`, `src/analysis/app/main_window.py`: path identity, vertical real toolbar, page-scoped status and existing window reuse (`80c89fe`, `6265af4`). | Local Qt checks and fresh Windows widget evidence recorded below; earlier local integrated checks passed; next corrected candidate required CI Pending. |
| GUI-03 / #179 | `WidgetRawDataProcessing`: full-width graph above input/review/scenes/log/current-slice groups; review-area scrolling and fixed save bar (`5f44a54`, `6265af4`). Existing `SceneReviewFlow` and save gate remain the owners. Current `ReviewScrollArea` additionally reveals the whole focused field. | Same Qt cursor-only issue reproduced with real inputs: six negative controls failed before correction; 13 Step 1 tests passed after, preserving 4/4/2 rows. Independent six-test correction recheck approved; integrated checks passed. Next required CI Pending. |
| GUI-04 / #180 | `MarkerFlipReviewDialog`: event table, original/axis preview, persistent Correction ON/Axis missing summary, separate Evidence dialog (`fe7421b`). | Local layout/approval/cancel regressions passed; earlier local integrated checks passed; next corrected candidate required CI Pending. |
| GUI-05 / #181 | `WidgetSliceProcessing`: upper preview/batch list and input context, lower method/resampling/log groups, mode-specific fixed action bar (`fcf8444`). Current `_ProcessingScrollArea` reveals the full field after direct scroll and Tab focus. | Hosted whole-field failure corrected; Qt 6.10/6.12 bounded suites each 21 passed, Qt 6.12 Segoe UI 9pt 13 passed, nested negatives three passed; independent reviewer 20 passed plus three subtests. Integrated checks passed; next required CI Pending. |
| GUI-07 / #182 | `WidgetResultsAnalyzer`: files/selection/summary row, graph and Point / peaks / CAE export tabs; Guide uses the actual point target (`ae35238`). | Local selection/cancel/Guide regressions and unchanged CAE bytes passed; earlier local integrated checks passed; next corrected candidate required CI Pending. |
| GUI-06 / #183 | `CompareMainWindow`: File details/Playback settings tabs, owner counts/reasons, mode-specific empty-summary sizing; actual 3D and playback retained (`e79ccd1`). Plot bounds `4f60836`, recorded sample time `ae62f45`, gap tooltip `66efaf6`. | Local and independent regressions passed; real foreground box/file/camera/Play observations and their source limits are recorded below. Next corrected candidate required CI Pending; corrected clock has no second external run. |
| GUI-08 / #184 | `SimulationUI`: visible XYZ Rotation group, Current run inputs in Physics/Markers and noise tabs, distinct draft profile, existing Single/Robot and preview (`f24ba72`, `6265af4`, `c985a00`, `996a8dc`). `ModeSettings.fit_tab` now uses actual visible width, style chrome and table horizontal-scrollbar height. | Hosted Robot FHD preview's 2px clip corrected; Qt 6.10/6.12 focused checks each 18 passed, all-tab 9/11pt supported-resize checks two passed, unchanged Robot validator 13 states passed offscreen. Obsolete marker-wrap test migrated to actual Unicode source/clipboard identity: six passed plus three subtests. Independent correction checks and integrated run passed; next required CI Pending. |

No detector, physical acceptance threshold, t1 definition, ROW/FRAME policy,
aggregation rule or `.slice/.proc` schema is redefined by these layouts. UI
counts and unavailable reasons come from their existing owners. Comparison
observation groups count `impact["observations"]` entries, while metric n remains
the owner's per-metric valid count. Synthetic copies are not independent trials.

## F1/F2/F3 and current acceptance status

Issue state was observed separately from evidence by the live issue audit on
2026-11-11. CLOSED is an issue-management state and does not mean every native,
consumer, physical, measured or release gate passed. #178–#184 remain OPEN
through the final review/required-CI gate. #177 remains OPEN with its separately
recorded native/actual OS125 acceptance; the consumer roadmap is outside the
user's current public-only execution scope.

| Area / related issue | Issue state observed | Verified source/date | Actual evidence and status | Remaining condition |
|---|---|---|---|---|
| Kernel/source/wheel / #166,#169 | CLOSED | Hosted candidate `b316b407…`, 2026-11-11 | [Shared-core run 42946595410](https://github.com/pikachu444/BoxMotionAnalyzer/actions/runs/42946595410) **Pass**: 119 tests and isolated wheel verification. Unchanged kernel SHA `824bf08d3852dc25b2e1856ebf55dbd14e527e7dfbb93519d40cfb013190b970`, version `0.1.0.dev0`; [receipt](../../bma_shared_core/SOURCE_RECEIPT.json) binds four files. This hosted isolated verification is distinct from the earlier linked historical run. | Actual publication remains Pending. Next corrected candidate still requires its own required CI. |
| Actual ROW adapter / #167 | CLOSED | `48e68fb` correction through local-evidence source `66efaf6`, 2026-11-11 | Earlier ROW/kernel/FRAME combined regression **Pass**, 49 tests, exit 0; actual public playback adapter remains ROW-1/1. Later shared-core hosted result is separately recorded above. | Next-source required CI; do not normalize ROW rejection ordering to FRAME. |
| F1 FRAME reference / #168 | CLOSED | `48e68fb`, 2026-11-11 | Four original counterexamples reproduced as **Fail** before correction; unchanged probe after correction **Pass**, returns None/None/`invalid_t1`/`invalid_flag`, with healthy controls. Combined regression **49 passed**, exit 0. Source/adoption checks Pass, schema 3 valid/14 invalid. | Final-source head CI. Reference success does not verify an unseen consumer adapter. |
| F2 Qt automated GUI / #160,#162,#170 | CLOSED | Full original `a6e5c0e…` archive, earlier local runs, failed hosted `b316b407…` and frozen post-failure correction source, 2026-11-11 | Original offscreen English 1120-width failure and all hosted failures remain recorded. Processing/Simulation/source-identity/Step 1 corrections have bounded and independent checks. Root integrated Qt 6.12/offscreen scale 1.25 **129 passed plus three subtests**. | Next candidate required CI Pending. No anticipated count is treated as evidence; no width/visibility relaxation or accordion restoration. |
| Windows Qt widget rendering / #177 | OPEN | 2026-11-11; V7 metadata base `80343c9…` plus listed per-file digests and capture-stable source | `tmp/gui177/common-native-v7-en/metadata.json` and `common-native-v7-ko/metadata.json`: separate fresh language processes, temporary INI, normal configuration; 18 QWidget grabs at three sizes/three pages, Windows platform, 맑은 고딕 9pt, DPR 1, DPI 96. All requested client sizes/axis-label bounds pass, no missing glyphs; Step 1 complete rows 4/4/2 at 1510/1100/820. Toolbar 34/icons 16. This is **Pass** for the recorded widget geometry/glyph scope. | Final source identity/CI reconciliation. Foreground desktop input, actual OS125 and human acceptance remain separate. |
| Windows native input/desktop/actual 3D / #163–#165,#136–#140 | CLOSED | 2026-11-11 external execution base `996a8dc…` plus concurrent layout edits; exact dirty whole-window snapshot not recorded | **Pass** for foreground activation, Step status restoration, actual box at Sample 1/1.000 s, second-file source/color and camera-drag/return preservation. Play exposed the pre-fix clock mismatch, recorded as **Fail** for that display. Four public PNGs and [external record](mockups/gui177/external/external-input.json) preserve observed scope. Three cleanup cycles are historical, not freshly rerun. | Corrected clock's second external run **Not run** after user requested capture stop. Separate clean `4f60836` QWidget captures bind final plot layout; no clean final-layout claim is made for the external dirty execution. |
| Actual OS125 and human confirmation | Separate from issue closure | No new qualifying run recorded | **Pending**. Current DPR or `QT_SCALE_FACTOR=1.25` is not actual OS125. | Use an available actual OS125 environment and human readability/operation confirmation without changing the user's OS settings. |
| Numerical/physical acceptance / #120,#140 and existing contracts | Issue closure is not numerical approval | No new physical input/expectation/result in this GUI change | **Not run** for new physical claims; existing calculations/history are preserved. | Claim-specific independent physical evidence if pursued separately. GUI fixtures do not prove robot suction, regrasp, Raw accuracy or a measured second impact. |
| Independent measured data / #104 | CLOSED; explicitly unavailable | Existing real-data limitation, reaffirmed 2026-11-11 | **Not run / unavailable**, not Pass. | Independently calibrated representative captures and synchronized references. |
| Actual consumer adoption / #168,#177 P3–P5 | #168 CLOSED; separate roadmap | No actual consumer integration run recorded | **Not run; outside current public-only scope**. Public reference and adoption schema checks are public handoff evidence. | Later consumer-owner execution and approval; no consumer-path request or integration dependency for this chat. |
| Package publication / #169 | CLOSED | Receipt `published_commit: null` | Historical isolated verification and hosted shared-core run 42946595410 passed; actual release/publication **Pending**. | Release identity, rights/metadata and owner publication approval. Isolated wheel verification does not publish a package. |
| Latest hosted CI / #177,#178–#184 | OPEN | `b316b407af5c47b32a7b5f6084fee6289c2116d2`, 2026-11-11 | [Public run 42946595392](https://github.com/pikachu444/BoxMotionAnalyzer/actions/runs/42946595392) **Fail**: 1,746 passed/3 failed. Evidence gate: 24 steps/21 passed, 12 test runs/11 passed, nine reports all passed. Continued-on-error step conclusions masked failing outcomes; those steps/runs are **not Pass**. Shared-core run 42946595410 passed separately. | Corrections and local independent/integrated checks passed; next candidate publication and all required hosted checks Pending. Next head/run/conclusion Pending. |
| F3 documentation / #170,#177 | #170 CLOSED; #177 OPEN | This record, 2026-11-11 | Hosted failure, masked-outcome distinction and correction-pending state recorded; earlier local/historical checkpoints preserved. | Record next corrected source/review/required-CI result without replacing the failed candidate history. |

The historical original-review totals (76 passed/1 failed/0 skipped across its
77 pytest cases), schema examples and wheel vectors are not current counts and
must not be added to the new run totals.

## Evidence and command record

The curated public [capture/evidence manifest](mockups/gui177/evidence.json)
binds exported PNG bytes, producer commands and source digests. Its package
state is a complete representative snapshot package with explicit metadata gaps:
22 representative PNGs, four external foreground PNGs and archived producers.
`tmp/gui177` is local diagnostic
storage, not publication of those artifacts. Raw pytest XML can contain the
host name; use sanitized public summaries/artifacts rather than publishing raw
JUnit unchanged. Earlier local integrated count: **112 passed**. Latest hosted
public candidate `b316b407…`: **Fail**, 1,746 passed/3 failed. Bounded correction
results are recorded below; frozen-source integrated **129 tests plus three
subtests passed**. Next head/required hosted runs are **Pending**.

| Execution / evidence | Source/environment and result | Scope and follow-up |
|---|---|---|
| Original F2 replay | Full `git archive a6e5c0e… src bma_shared_core tests data` into `tmp/gui177/baseline-full`; fresh normal configuration/temp QSettings, Sans Serif 9pt, offscreen DPR 1, 800×800 virtual screen. English requested 1100×720 → actual 1120×720, scene minimum hint 1056/window minimum 1120; Korean actual 1100×720, scene hint 666/window minimum 790; both four whole rows. | `baseline-full/tmp/f2-original/{en,ko}/metadata.json` and PNG, `baseline-original-{en,ko}.log`. Diagnostic process exit 0 means observations were recorded; the English size gate is **Fail**, not Pass. This full replay supersedes hybrid-source diagnostic dimensions. |
| Corrected seven-file GUI regression | `.venv` Python 3.13.5, offscreen; **55 passed**, 8 existing gimbal-lock warnings, 0 skipped/xfail, 75.27 s. | `tmp/gui177/legacy-current.txt/xml`; fixed groups/tabs, exact client geometry, whole-row/negative visibility controls, Pan/Zoom keyboard, Include/Exclude and user font/splitter preservation. |
| Ancillary contract regression | **73 unique passed** as reported by the owner across dimensions, scene review, processing, comparison, marker export/guide and Simulation checks. | Related `tmp/gui177/ancillary-*` records; overlapping attempts/reruns are not added into a total with the other suites. |
| Common UI checks | Offscreen **26 passed** with two existing gimbal-lock warnings; Windows Qt **6 passed**, no warnings. | Recorded common UI/lifecycle/toolbar checks; Windows widget/input scope is not foreground desktop acceptance. |
| Root integrated Windows Qt, synthetic 1.25 scale | Initial **104 passed/2 failed**; `root-final-native125.log/xml`. Two targeted corrections passed. Next **109 passed/1 failed** in `root-corrected-native125.log/xml`: a test compared physical renderer pixels with Qt logical coordinates. Test-only coordinate correction passed **7 targeted checks**. A later native run was interrupted after the user's capture concerns. | Original failures/interruption are retained; the interrupted run is not counted as Pass. Current scale is OS100/DPR 1; `QT_SCALE_FACTOR=1.25` is not actual OS125. No OS scale was changed. |
| Earlier root offscreen, synthetic 1.25 scale | Local-evidence source `66efaf6`, 2026-11-11: `tmp/gui177/root-final-offscreen125.log/xml`, **112 passed**, 69 warnings, 121.61 s. | Local software regression Pass for that source/scope; the later hosted public failure is separately recorded below. |
| Hosted shared-core candidate | `b316b407af5c47b32a7b5f6084fee6289c2116d2`; [run 42946595410](https://github.com/pikachu444/BoxMotionAnalyzer/actions/runs/42946595410), **119 passed** plus isolated wheel verification. | Shared-core job Pass only; it does not override the public validation failure or publish the package. |
| Hosted public candidate | Same `b316b407…`; [run 42946595392](https://github.com/pikachu444/BoxMotionAnalyzer/actions/runs/42946595392), **1,746 passed/3 failed**. Failures: processing whole-field visibility, Robot FHD preview clipped by 2px, obsolete marker-wrap assertion. Evidence gate: **24 steps/21 passed; 12 test runs/11 passed; nine reports all passed**. | Overall **Fail**. Continued-on-error conclusions did not turn failing step outcomes or test runs into passes; passing reports alone are insufficient. Corrections are committed as `1fe0aa1` with bounded/integrated checks and approved reviews below; next hosted candidate/result Pending. |
| Processing whole-field correction | `_ProcessingScrollArea` fixes Qt revealing only a line edit cursor while leaving its border clipped. Full-rect checks and Tab-focus reveal now verify the field rather than just the insertion point. Qt 6.10 and 6.12 bounded suites each **21 passed**; Qt 6.12/Segoe UI 9pt **13 passed**; nested negative controls **three passed**. | `tmp/gui177/processing/ci-fullrect-{regression-610,regression-612,segoe-612,nested-612}.xml`. Independent reviewer **20 passed plus three subtests**; do not sum overlapping suites. |
| Additional Step 1 focus correction | Real inputs at 1100×720 and 820×600 on Windows 11/Qt 6.12/Segoe UI 9pt lost 4px after focus from the same cursor-only behavior. **Six negative controls failed before**, then current `ReviewScrollArea` full-field reveal passed **13 Step 1 tests**, retaining 4/4/2 complete rows at the supported sizes. | Independent **six-test correction recheck passed/approved**. This is a real-input focus test, separate from earlier Qt 6.10 widget captures and the failed hosted processing case. |
| Source-identity test migration | Obsolete marker-wrap expectation replaced with full Unicode source identity and actual clipboard behavior; **six passed plus three subtests**. | `tmp/gui177/ci-followup-source-identity-final.xml`; preserves source/path meaning rather than asserting a removed layout. |
| Simulation height-for-width correction | `ModeSettings.fit_tab` measures actual visible tab width, style chrome and horizontal-scrollbar height. Qt 6.10/6.12 focused checks each **18 passed**; 9pt/11pt all-tab and supported-resize checks **two passed**. Unchanged `robot_ui_validation` passed **13 states** offscreen on Windows 11/Qt 6.12/Segoe UI 9pt, synthetic scale 1.25. | `tmp/gui177/simulation/hfw-*` and `hfw-robot-612-run01/RunReport.json`. G selected viewport `[1085,848]`, target rect `[9,575,1067,264]`, scroll 0. Controlled font-stress red is separate; exact hosted native red is **not claimed reproduced offscreen**. |
| Frozen-source integrated rerun | Qt 6.12/offscreen, `QT_SCALE_FACTOR=1.25`: **129 passed, 71 warnings, three subtests passed**, 145.03 s. Fifteen files include all seven new GUI files, seven migrated legacy files and marker-raw integration. | `tmp/gui177/root-ci-corrections-qt612-125.log/xml`. Corrected production commit `1fe0aa1`; next hosted head/run Pending; this executed local result does not imply actual OS125 or hosted success. |
| Frozen-source CI preparation | **12 collection checks passed**, main inventory **1,760 nodes**. | Collection/preparation evidence only; node inventory is not a passed-test count or hosted result. |
| P02 before/after production processing | `tmp/gui177/processing/identity/before-after-identity.json`: generated public analytic marker input, 61 rows/278 columns; exact config/payload, dataframe, saved bytes and metadata preserved; original input unchanged. PROC SHA `616e756fa6f4baa1d44fd1c43f370569cbf45784b40dc53bf1693e269c395f69`. | Real UI/pipeline integration and byte identity, not an accuracy oracle; stored source kind remains `handcrafted_dummy`. Input SHA `eac7d79901030c8c0e29d273790ed8ed38e1cc07b58c1cd31097cb80e83c08dd`. |
| R02 CAE export identity | Existing generated result exported before/after through the unchanged scenario serializer; SHA `116691e9f5bc3dc5f1a46410ff2f42332c195e0a1e067e38688e5b10e483757c` retained. | `tmp/gui177/results/{before,after}-native.json` records `scenario_sha256`; no CAE physical acceptance claim. |
| Independent review | Processing correction review **20 passed plus three subtests**; Step 1 **six passed/approved**; Simulation **18 passed plus three focused checks and 40 resize/tab cycles**, approved with no P1/P2 in the inspected correction scope. Prior recorded-time cases also independently passed. | Frozen-source integrated checks passed; next required hosted CI remains Pending. Reviews are bounded to inspected changes, not physical/measured/actual OS125 acceptance; earlier failures stay in history. |

The original visibility regressions exposed clipped controls and an offscreen
frame-versus-virtual-desktop assumption. Controls were made scroll-reachable;
the actual native frame/desktop assertion is Windows-specific while exact
820×600 client and full-widget visibility assertions remain. No unconditional
skip, xfail, size relaxation or assertion removal was used to turn the F2
contract into a pass.

The [external foreground record](mockups/gui177/external/external-input.json)
and its four unedited safe PNGs distinguish the actual external observations
from QWidget grabs. At current OS100/DPR 1, the initial real box was visible at
Sample 1/1.000 s; switching to file 2 changed source/color, and camera rotation
survived returning through file 1 to file 2. Clicking Play exposed Sample 3 and
cursor at 1.020 s while the displayed clock read 1.036 s. Execution was based
on `996a8dc` with concurrent comparison layout edits; the exact whole-window
dirty snapshot was not recorded. `playback_panel.py` is identical between
`996a8dc` and `4f60836`, binding this playback observation, while clean
`4f60836` QWidget captures independently bind final graph geometry. The record
does not assert a clean final-layout external run.

`ae62f45` changes the Individual playback label to the selected recorded sample
time, with unavailable state inside a gap; `66efaf6` restores the `Recorded time`
tooltip on the next valid sample. Two deterministic cases first failed with the
observed clock/gap errors (`compare-recorded-time-red.xml`) and then passed
(`compare-recorded-time-green.xml`); both passed independent review. ROW lookup,
elapsed-time dispatch, gap policy, Aligned mapping and numerical arrays remain
unchanged. No second external run was performed after the user's request to
stop captures, so corrected-clock external confirmation is **Not run**.

Three actual native add/play/remove/close/reopen cleanup cycles are historical
evidence in [#158 layout record](step1_scene_layout_158.md) and its
[execution record](step1_scene_layout_158_evidence/execution.json). That record
names baseline `d7d61435…` and source commit `8f8b8b23…`; Git object identity
for `playback_panel.py` is the same at both (`d10d38cdee972d216ec2ed9ac33df6502fd9c115`).
The native-cycle paragraph in the linked historical document (lines 63–67)
belongs to that execution record's `8f8b8b23…` source, not its `d7d61435…`
baseline. The reviewed `d7d61435…`→`66efaf6` playback diff contains translations
and recorded-time label/tooltip changes only: close, stop, timer-stop, refresh
cleanup and VistaWidget cleanup flow remain unchanged. Main window closeEvent
also has an unchanged body. This narrowly reuses the earlier unchanged-flow
evidence without claiming fresh three-cycle execution or memory-leak freedom.
The historical blank 3D capture is superseded only for the newly observed
foreground box/file/camera scope, not for unperformed states or actual OS125.

F1 used the same probe before and after, SHA-256
`06cadc2ad2be7a39098cefda5241e94850a7d6556eded93ffeb2d442ce0d43f9`:

```powershell
.venv/Scripts/python.exe tmp/gui177/frame_rejection_probe.py
.venv/Scripts/python.exe -m pytest -c tmp/gui177/pytest.ini --rootdir . -q --tb=short tests/test_shared_frame_reference.py tests/test_shared_row_adapter.py tests/test_shared_time_selection.py --junitxml=tmp/gui177/f1-after-pytest-recheck.xml
```

`f1-before.log` records probe exit 1 with ValueError, TypeError, ValueError,
and `t1_not_detected`; `f1-before-pytest.log/xml` records four failed cases.
`f1-after.log` records probe exit 0 and healthy controls.
`f1-after-pytest-recheck.log/xml` records 49 passed and exit 0. An earlier
mistyped invocation in `f1-after-pytest.log` exited 4 and is retained as a
failed invocation, not counted as passing tests. The kernel hash stayed
`824bf08d3852dc25b2e1856ebf55dbd14e527e7dfbb93519d40cfb013190b970`.
FRAME helper `invalid_t1`/`invalid_flag` correspond to consumer contract
`t1_time_invalid`/`t1_detected_invalid` for these conversion-failure cases;
the mapping does not redefine missing-value or legacy policies.

Current source and adoption checks:

```powershell
.venv/Scripts/python.exe scripts/check_shared_core.py
.venv/Scripts/python.exe scripts/check_shared_core_adoption.py
```

Both passed; adoption schema examples are 3 valid/14 invalid. `jsonschema` was
initially absent from the local verification environment, then installed there
before the check passed. The dependency-missing attempt is neither a product
failure nor a passing validation. Package bytes/packaging stayed unchanged, so
the earlier local source/adoption checks did not claim a fresh wheel rebuild.
The later hosted shared-core run 42946595410 performed isolated wheel
verification and passed separately; neither stage is a package release.

Separate the following evidence types when completing the record:

- Qt offscreen assertions and captures check layout/state under their recorded
  platform, actual font/fallback, DPI/DPR and geometry. Known Korean tofu/glyph
  conditions in offscreen must be reported separately, not treated as Windows
  font success or silently counted as product rendering failure.
- Windows Qt QWidget grabs check actual Windows Qt layout and glyph support.
  `common-native-v7-{en,ko}/metadata.json` explicitly limits their scope; foreground
  desktop visibility and actual external input require separate observations.
- VTK render-buffer output confirms that backend rendering produced pixels.
  A black QWidget grab alone cannot prove viewer failure, and a good buffer
  alone cannot prove desktop display success.
- Actual desktop, native input, actual OS125 and human visual confirmation are
  individually recorded gates; none is inferred from another.

The existing F2 sequence maps to selecting the current fixed input/review groups
or relevant tool tabs at 1510×800 and 1100×720, checking four fully visible data
rows, axes, all toolbar actions/overflow and save controls. At 820×600 use
explicit scroll reachability rather than forcing four rows. Include English
and Korean normal `configure_language()` startup, preserved user settings,
long duplicate filenames, Pan/Zoom keyboard operations, Include/Exclude,
user-adjusted axes and splitter retention. The table header is not a data row.
F1 commands/checks use the existing pure kernel, actual ROW and FRAME reference;
the kernel's ValueError contract remains unchanged.

The historical Details test is now
`tests/test_processing_window_layout.py::test_capture_fixed_review_keeps_four_rows_actions_and_toolbar`.
It retains exact 1510×800/1100×720 client sizes, four whole data rows, the
13pt user-Y-title preservation input, Pan/Zoom keyboard and Include/Exclude
operations. `test_full_visibility_rejects_partial_and_empty_regions` provides
negative controls for the full-region check. These identities describe what
is exercised; final pass/fail is recorded from the actual run, not collection.

## Later consumer roadmap boundary and P3–P5

This section preserves public handoff information for later adoption. It is
outside the user's current public-only task and is not a condition for this
chat's implementation, tests, review, PR or CI. No consumer repository was
inspected or requested.

The following are actual public imports/signatures, not a new extracted
whole-GUI package or a claim that an external adapter already exists.

| Public import/entry | Current binding and consumer obligation |
|---|---|
| `src.analysis.app.main_window.MainApp()` / `AnalysisTabs` | MainApp constructs `DataLoader`, `Parser(face_prefix_map=FACE_PREFIX_TO_INFO)` and `PipelineController`. Adopt their compatible data/metadata contract, or propose and verify a bounded controller seam in canonical public source; there is no general dependency-injected MainApp constructor today. |
| `src.analysis.ui.widget_raw_data_processing.WidgetRawDataProcessing(data_loader, parser)` / `load_csv_path(filepath)` | `src.analysis.pipeline.data_loader.DataLoader.load_csv(filepath)` and the existing Parser supply current raw/parsed structures and source/timeline/geometry context. `file_loaded`, `slice_saved`, `process_requested` keep their existing signal contracts. Source revision, SHA and approval invalidation remain owner-controlled. |
| `src.analysis.ui.dialog_marker_flip_review.MarkerFlipReviewDialog(candidates, existing_decisions=None, parent=None)` | Receives the existing candidate/decision types and owner-provided evidence/context. UI cannot invent missing curves, approve a suggested axis, or save corrected input directly. |
| `src.analysis.ui.widget_slice_processing.WidgetSliceProcessing(data_loader, parser)` / `load_processing_inputs(paths, confirm=True)` | Existing `processing_requested` and `results_ready` bind processing and successful saved-path handoff. Preserve per-mode state and metadata, temporary-file replacement, source/geometry checks and explicit Run. |
| `src.analysis.ui.widget_results_analyzer.WidgetResultsAnalyzer(data_loader)` / `open_result_files(paths)` / `load_result_file(file_path, *, preserve_selection=False)` | `DataLoader.load_result_csv(filepath)` supplies supported multi-header results. Keep metric keys/units, point selection, export serializer, cancel/failure state and `compare_requested` paths. |
| `src.analysis.compare.main_window.CompareMainWindow()` / `load_result_files(filepaths, *, deduplicate=False)` | Constructs the actual `ComparisonModel`; use its file/source identity, ROW playback, timeline/eligibility reasons, observation resolution and per-metric n. Preserve PyVista/VTK capability policy and resource lifecycle rather than adding fake 3D slots. |
| `src.simulation.ui.main_window.SimulationUI(parent=None)` | Existing engine, ModeProfiles, robot capability and marker export remain responsible for payloads. Preserve Current run versus draft Apply/Cancel, mode state, actual coordinate/rotation units and unavailable-capability reasons. Backend replacement is separate work. |
| `src.launcher.LauncherWindow._open_work_window(attribute, factory)` and `MainApp.comparison_opener` | Existing launcher reuses open/minimized windows, replaces successfully closed windows and routes Compare into the launcher-owned window. This is the existing internal integration seam, not a new stable adapter SDK. |

Storage boundaries are the actual loader/writer and file-dialog/controller
paths for source CSV, corrected CSV, workspace/review documents, `.slice`,
`.proc`, profiles and CAE/point export. A consumer storage or legacy-file
adapter must preserve identity, units, source/correction history and atomic
save/cancel behavior. UI translation changes display text only, not enum/key,
export column or numeric settings. Consumer capabilities and data compatibility
must be explicitly declared; absence of a backend does not justify an active
nonfunctional action.

P3 pins the verified public commit/dependency and imports the same implementation.
A transitional copy is acceptable only with byte equality for the adopted
source closure, recorded owner/revision, a drift check and a plan to return to
direct common-source use. Copying a few helpers while separately maintaining
whole windows does not finish the common-GUI goal. P4 requires the consumer
owner's real-data, existing-file, correction, comparison, save/reload and CAE
workflow checks plus a rollback bundle. P5 keeps later changes public-first,
repeats approval-bound adoption and checks source drift. All three phases remain
**Not run / later roadmap**, outside this task; no private adapter or experiment
evidence was inspected here.
