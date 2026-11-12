# Actual-widget prototype review

Last Reviewed: 2026-11-12

Reviewed independently from product implementation for issues #191, #193 and #194.
The selected composition is approved for implementation. This is a developer layout
decision, not human acceptance or a declaration that the product requirements pass.

The prototype script is `scripts/gui_metric_parity_prototype.py`. It instantiates the actual
`WidgetSliceProcessing` and `WidgetResultsAnalyzer`, reparents their controls in
subclasses, and builds a shared-registry Guide prototype. Source files were not edited.
The displayed affine curve and filenames are generated presentation fixtures; they
are not loaded experimental results and do not establish producer or numerical parity.

The reviewed original captures are historical implementation-stage evidence. The
original processing baseline was `20dd4ce53a6d401fd6e219d6086b7600dba35ad7`;
the Guide prototype used the then-new shared registry. A pure baseline checkout
does not contain that registry and cannot replay the complete combined prototype.
The checked-in script now supports the final product: it reuses accepted processing
cards and the existing velocity checkbox when present, preventing duplicate controls.
Its separate `prototype_replay/` output was executed successfully with 30 native
Windows Qt captures. That replay does not overwrite historical before captures
and is not claimed to be pixel-identical to the original proposal.

From the repository root and declared Windows project environment:

```powershell
python scripts/gui_metric_parity_prototype.py
```

The replay records source hashes, actual client/font/DPR values, and output scope
in `prototype_replay/prototype_geometry.json`. It defaults to the native Windows
Qt platform without changing OS or font settings.

## Observed composition

The final run used Qt 6.10.1 with the native Windows platform, existing default
Malgun Gothic (맑은 고딕) 9pt, and device pixel ratio 1.0. No OS setting or application
font was changed. `prototype_geometry.json` records requested/actual clients and fonts.
Thirty final captures cover EN/KO, Single/Batch, the three processing/results sizes,
CAE rest/selected-time modes, Guide sizes, search and empty states. Six
`prototype-before-process-*.png` captures retain the original composition with the
same generated display input; see `prototype_before_geometry.json`.

| Processing client | Settings columns | Top height | Right width | Log height | Footer height |
|---|---:|---:|---:|---:|---:|
| 1510×800 | 5 | 429 | 345 | 104 | 48 |
| 1100×720 | 3 | 344 | 300 | 90 | 48 |
| 820×600 | 2 | 265 | 270 | 80 | 48 |

All three actual clients equal the request. Settings horizontal scroll maximum is
zero. The small client scrolls its later setting rows vertically. The upper context
has its own scroll and the small Log remains visible. These capture targets were
initialized separately for each proposed initial view; product resizing must not
reapply them over a user's splitter adjustment.

The CAE prototype places the new velocity option immediately below Manual Height.
A short persistent source summary sits above the fixed export command. In the
820×600 EN/KO renders the graph remains usable, the option fits, and later input
fields remain in the existing scroll. Leaving Manual Height disables and clears the
option; returning does not restore a hidden ON state. No export was run by this
prototype.

The Guide uses one scroll, fixed search/group/context controls, definition and
interpretation tabs, and fixed Close. At actual content widths 999/1000/1001 it
uses 1/2/2 columns; the 1100×760 and 640×480 clients remain exact. EN/KO text wraps
without scaling the font. Definitions here reflect the in-progress registry and
do not constitute an independent review of every final formula or drawing.

## Findings, corrections and product follow-up

1. The first offscreen run selected unavailable `Sans Serif` and rendered missing
   glyph boxes. It was rejected for readability review. Rerunning with the native
   Windows platform and its unchanged default font produced readable EN/KO buffers.
   The saved final captures replace the rejected offscreen buffers.
2. A card's inherited `minimumSizeHint()` included stale allocation and caused an
   incorrect one-column wide view. The prototype now uses explicit control-derived
   minima and equal grid stretches. Reinspection confirms 5/3/2 without horizontal
   settings scrolling. Product code must derive radio-row fit before fallback.
3. The initial CAE source paragraph consumed too much vertical space at 820×600.
   Three short mode/source/unit lines fit. Detailed frame/reference semantics belong
   in the tooltip/Guide while the output mode remains continuously visible.
4. The passive rich `QLabel` Guide entries are skipped by normal Tab navigation
   despite `StrongFocus`. This is an unresolved prototype limitation. The product
   renderer must provide actual keyboard entry navigation and test it; widget
   existence or label focus policy alone does not satisfy that requirement.
5. Searching an unqualified semantic key can correctly match both summary and
   comparison fallback entries. A complete context-qualified ID matches one entry.
   Product focus must use that identity rather than translated label matching.
6. The prototype's manually assigned long path labels can clip in the small right
   context. Product must retain its existing path elision/tooltip helper; these
   presentation fixtures must not replace that behavior.
7. The prototype title/value labels should suppress empty `()` units in the final
   renderer. Final diagrams, missing-image alternatives and semantic cautions still
   require the product's separate checks.

The design decision follows the retrieved `VIS-SPACE` rule (spacing establishes
related tasks), `WIN-COMMAND` (common execution commands remain visible),
`QT-PANELS` (preserve central plot and user resizing) and `QT-ACCESS` (inspect real
logical clients and keep keyboard focus visible). Source references are recorded in
the skill's visual-design reference corpus: [Windows content spacing](https://learn.microsoft.com/en-us/windows/apps/design/basics/content-basics),
[command bars](https://learn.microsoft.com/en-us/windows/apps/develop/ui/controls/command-bar),
[Qt splitters](https://doc.qt.io/qtforpython-6/PySide6/QtWidgets/QSplitter.html) and
[Qt high DPI](https://doc.qt.io/qt-6/highdpi.html). The rule selection is design
guidance, not proof of operation.

`prototype_interactions.json` records seven Qt-level checks, including original
resampling activation, mode-stack switching, search/filter, Close/reopen and actual
999/1000/1001 reflow. The keyboard-entry limitation above remains explicit.
Native desktop input automation: **Not run**. Actual OS125: **Not run**.
Human acceptance: **Pending**. Product processing, saving, failure preservation,
3D playback, final screenshots and numerical validation are outside this prototype.
