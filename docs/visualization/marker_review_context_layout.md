# Marker review observation context

Last Reviewed: 2026-09-18

#121 keeps the existing modal review and embeds a read-only observation plot.
At 1280×740 (within a 1510×800 workspace), the event table remains above two
plots and Done/Cancel remain fixed below them. The minimum stays 820×600.

```text
Marker correction — current capture
Event (s)       Recommendation        Apply        Local axis
...
Original motion [Marker / rigid body v] [Around event]
[pan / zoom / home toolbar]
Original observed XYZ                    Local-axis preview
             | selected event             relative rotation
             | actual time                time from event
> Details
                                               [Done] [Cancel]
```

The left plot shows unmodified position samples with their actual times and
units; missing values remain gaps. It opens around the selected event and
allows pan/zoom across the full capture. Selecting another event recentres the
context; changing the preview axis or Apply retains the current viewport and
all pending event choices. Marker selection is independent of Apply. Source
labels use a short filename with the full path in a tooltip.

The source data is the same original observation snapshot used by review,
including when a corrected source has been reopened. No truth, manifest,
new pose fitting or resampling is used for plotting. Existing source/revision,
dimensions and asynchronous byte-verification gates remain in force before
committing decisions. Cancel discards local choices. Save is the existing
separate validated corrected-source flow. A source switch while a modal loop
is active must invalidate all old choices; tests cover the real dialog and
asynchronous completion separately.

The implementation shows three event rows at once and scrolls additional
events. A five-event, expanded-Details case was exercised at 820×600. The
production MainApp/worker/dialog was exercised with a newly declared 54-row
public capture (held motion, partial missing observations, X then Z half-turns,
and an independent raw rigid-body block). Expected plotted positions were
computed from the declared coordinates, never copied from fitted poses.
Actual mouse pan, event recentring, preview without approval, cancel, save
cancel/error/retry, corrected-source reopen and replacing the source inside
the modal loop passed. The source switch rejected old choices. Screenshots
measure MainApp 1510×800 and dialog 1280×740 at DPR 1.25. These are GUI/state
checks, not evidence that every previewed correction reflects physical truth.

Preimplementation review: this adds one observation panel to the existing
dialog and avoids introducing a modeless editing lifecycle. At small sizes the
event table scrolls and Details collapses; both plots and primary actions stay
visible. Empty/unavailable observations display an explicit empty plot. The
runtime screenshots and independent review are recorded with the #121 PR.

Final related validation passed 40 tests and three subtests. Independent
read-only review passed 13 targeted tests (one integration case deliberately
deselected to avoid duplicating the supplied actual execution); no important
findings remained. Required CI also runs the full context test at DPR 1.25 and
retains screenshots/JUnit. Final CI/merge status belongs to the PR.
The final minimum-size screenshot exposed clipped context-axis labels after a
resize. A constrained figure layout and rendered-label bounds checks corrected
that issue; independent visual re-review approved the resulting 820×600 view.
The final four-case run also blocks evaluator-file reads and records the
original source hash.
