# Issue #158 validation and handoff

Last Reviewed: 2026-11-09

[Issue #158](https://github.com/pikachu444/BoxMotionAnalyzer/issues/158) defines
the scope, expected results, and approval gates. The remote main baseline is
`d7d61435c89bacda0d87175c06887b1d85f24e2e`. See [baseline.json](baseline.json)
for source hashes, open issues, and the parent and child relationships.

## Work and evidence

| Issue | Task | Source or evidence | Remaining condition |
|---|---|---|---|
| #159 | 158-01 | Git object and working-copy hashes, current GitHub issue inventory | Baseline recorded |
| #160 | 158-02 | Step 1 window, scene table, and save controls. G1/G2 baseline shows only two full rows in the constrained states | GUI direction approval, implementation, action checks, native acceptance |
| #161 | 158-03 | Step 1 and comparison toolbar actions. Step 1 axes measured at both client sizes | Approve direction, measure comparison axes and keep toolbar actions and keyboard access |
| #162 | 158-04 | Original path and tooltip test. Step 1 long Unicode filename and 9 pt local axis-label proposal | Verify resize, font overrides, and native legibility |
| #163 | 158-05 | Existing comparison initial dispatch and generated corner geometry | Complete G5 initial, replacement, invalid, and reopen cases in the real display |
| #164 | 158-06 | Existing comparison list, selection, modes, and reload tests | Complete G6 details and keyboard focus checks |
| #165 | 158-07 | Existing viewer replacement, cleanup, and reload tests | Complete G7 timer checks and three native add/play/remove/close/reopen cycles |
| #166 | 158-08 | Appendix A bytes and Appendix B vectors verified | Public head CI |
| #167 | 158-09 | Fixed ROW examples, actual comparison lookup, serialized regression, independent differential probe | Public head CI |
| #168 | 158-10 | FRAME reference and adoption schema checked with generated inputs | Consumer-side before/after evidence and approval |
| #169 | 158-11 | Two isolated venvs, wheel allowlist, installed bytes and fixed vectors checked | Public head CI. Release rights, metadata, and publication approval pending |
| #170 | 158-12 | This report and [execution record](execution-2026-11-09.json) | Record final head CI and pending GUI/native conditions |

Tasks 08–11 follow 01 in order. Existing-window verification can run
independently after 01. Layout changes follow approval of the
[Step 1 proposal](gui-proposal.md). Any change to G5–G7 requires a reproduced
defect. Task 12 records evidence as the other tasks advance.

| Related issue | Existing source or delivery evidence | Next condition |
|---|---|---|
| #111 | Existing workflow parent and issue history. PRs #127–#133 document the delivered review and comparison scope | Retain its child relationships |
| #112 | Event-local marker review in analysis UI and worker | Previously delivered, issue remains open by request |
| #113 | Registration UI excluded by the recorded decision | New explicit decision required |
| #119 | Metric-level duplicate and conflict resolution in comparison | Representative reprocessing selection remains excluded |
| #120 | First-contact investigation recorded | Bounded contact policy deferred pending a new decision |
| #134 | Existing roadmap and [delivery audit](../analysis/reference/pub_delivery_status.md) | Preserve software, native, numerical, and measured evidence separately |
| #136 | Flip review layout and lifecycle, PR #147. Current-scale native Apply and Cancel controls exercised | Complete remaining native states and sizes |
| #137 | Scene review, workspace save and reopen, PR #148. Current-scale native save/reopen and changed-evidence handling exercised | Verify native unchanged-evidence restoration, remaining editing and export paths |
| #138 | Profile editor, identity and GUI tests, PR #149. Current-scale native profile views and face switching exercised | Verify remaining input paths and Windows 125% |
| #139 | Single and continuous modes, PR #150. Current-scale native mode switching exercised | Verify full native mode round trip and Windows 125% |
| #140 | Suction and regrasp UI and sequence controls, PR #151. Current-scale native selected-drop Preview and Apply exercised | Verify native run/viewer, Windows 125%, numerical bounds, baseline/trial and measured evidence |
| #135, #141–#144 | Merged software and hosted evidence in the delivery audit | Native and physical acceptance retain their own gates |
| #152 | Language Options issue | Separate plan, review, and PR |
| #104 | Independent measured validation issue | Calibrated real captures and synchronized references unavailable in this run |

## Shared core source and execution

| Commit | Scope |
|---|---|
| `7531ad4516dc846f7aa8bec8c4ebcde04ce8cb41` | Baseline and fixed kernel |
| `12959c13b8cd8a710eea9151591807c2158c706e` | Public ROW lookup and fixtures |
| `d8064955b30df929fe61c0cd930a911e2d905f7b` | FRAME reference and adoption schema |
| `fdcb7d2d6e2196538b931b386767bf132eb696a2` | Tested code candidate, isolated package and CI |

The kernel SHA-256 is
`824bf08d3852dc25b2e1856ebf55dbd14e527e7dfbb93519d40cfb013190b970`.
The package candidate is `0.1.0.dev0`. The source receipt binds four source
files. The CI artifact records the public PR head and the tested checkout
separately.

| Evidence | Result |
|---|---|
| TIME-KERNEL/1 | 16 success vectors, 11 exception vectors, unchanged read-only view |
| Actual ROW-1/1 adapter | 16 pre-change tests passed. Candidate also checks overflow policy and verifies that real playback calls the shared selector |
| Independent ROW comparison | 9,792 lookups matched baseline return values, exception type and message, and warnings |
| Serialized `.proc` | Existing comparison suite exercised writer, reader, model, missing t1, time columns, source eligibility, incompatible model identity and invalid declarations |
| FRAME-1/1 | Nine fixed C1 cases and C2 reference checks pass. Consumer code and experiments require their own execution and approval |
| Adoption schema | Three valid and 14 invalid examples under Draft 2020-12 |
| Isolated wheel | Python 3.13.5, NumPy 2.5.4. Six archive entries. Canonical, wheel, and installed runtime bytes match. Runtime executed outside the checkout with `-I` |
| Qt baseline | 163 existing comparison, processing, scene, flip, profile and simulation checks passed. Qt logic, input injection, and widget rendering are recorded by their actual scope |
| Native Windows | 2560×1440 physical desktop, DPR 1.0. Initial `GetCursorPos` access was denied. A later Windows capture and input session exercised the controls listed below. Comparison 3D display and actual Windows OS 125% remain unverified |
| Real measurements | Pending calibrated independent data |

Main and independent review session metadata recorded GPT-6.1 Sol and High.
The host configuration used the default service tier. Neither session log
reported the resolved service tier. The independent reviewer reproduced an
overflow warning and exception from a distant interval during strict-axis
validation, missing FRAME first-row coverage, a missing MuJoCo CI dependency,
and metadata-only wheel drift. The revised code preserves the selected
interval calculation when validation overflows, checks FRAME first-row
behavior, installs the CI dependency, and rejects altered metadata. The
reviewer rechecked all four changes. The initial ROW test expectation for
an invalid gap string was corrected from `TypeError` to the observed baseline
`ValueError` before changing the production adapter.

## Hosted checks and later Windows observations

PR [#171](https://github.com/pikachu444/BoxMotionAnalyzer/pull/171) first ran at
`070180ae2850ea8c8ca9bce1a34494366b621118`. The
[shared core check](https://github.com/pikachu444/BoxMotionAnalyzer/actions/runs/42571720510)
passed, including the isolated wheel on Python 3.13.17 and NumPy 2.5.4.
The [Windows integration run](https://github.com/pikachu444/BoxMotionAnalyzer/actions/runs/42571720390)
first stopped at the Mesa archive download. Its second attempt passed the
download and then failed the unchanged serialized-identity test after 1,083
tests passed. It used pandas 3.1.1, which treats the converted opaque ID
`NA` as missing. A fresh local pandas 3.1.1 environment reproduced the
same expected `NA` versus observed `None` failure. The baseline's passing
hosted run used pandas 3.0.6. The
application requirement now limits pandas to versions below 3.1, and the
shared core CI job uses the same constraint and runs the existing identity
regression. The reader's opaque-ID and missing-value policies are retained.
[Pandas 3.1 I/O changes](https://pandas.pydata.org/docs/whatsnew/v3.1.0.html#i-o)

The later Qt run passed 94 checks across comparison, flip, scenes, profile
editing, simulation layouts, modes and robot sequence. A generated
`.proc` probe used the real `VistaWidget`. It dispatched row 0 before
playback, rendered the generated box to the VTK buffer, and reset to row 0
when reloading a one-row result without t1. The timer stopped on close.
Changing model identity preserved both numerical lookups and both curves,
while excluding the incompatible result from comparable metrics. The
existing repeat-statistic regression also passed for `ModelId`.

The later native session used a 2560×1440 desktop at DPR 1.0 and the
existing application windows with generated input:

- Step 1 at 1100×720 accepted Details, Include and Exclude. The native
  chooser saved and reopened the review file. Recalculation of the seeded
  fixture changed scene evidence and showed `Review again` in eight rows.
- The flip dialog at 1280×960 showed both plots and accepted the event
  Apply toggle. The 32-marker editor at 1280×960 showed both views and
  updated the selected face and marker count after a native click.
- Simulation at 1510×800 switched from Single drop to Robot sequence.
  Selecting one drop showed `Drop 1 only (16 excluded)` in Preview.
  Apply enabled Run. Numerical approval and a native engine run are separate.
- Comparison at 1100×720 accepted the native result chooser, arrow-key
  file selection, playback and file removal. Windows capture showed the
  sample label and graph updating, with a blank native 3D capture area
  before and during playback. The VTK render-buffer result is recorded
  separately. The three-cycle native closure gate is still open.

## Consumer handoff

Use the public code candidate commit, version, kernel hash and
[source receipt](../../bma_shared_core/SOURCE_RECEIPT.json) with
[TIME-KERNEL/1, ROW-1/1 and FRAME-1/1](consumer_contracts.md) and the linked
generated fixtures. Pin the exact adopted revision and verify the actual
consumer adapter against its own baseline. Store approvals in the
[adoption schema](adoption.schema.json). Restore the previous kernel, adapter,
and dependency pin together if the consumer cannot meet the gate.

Public code has local implementation and review evidence. GUI acceptance and
hosted head CI have separate gates. Independent installation is verified.
Downstream approval and measured validation are pending. Publication remains
pending owner approval.
