# FinalFace tail support decision record (#200)

Last Reviewed: 2026-11-12

Status: **Awaiting user policy decision.** This record characterizes current
behavior; it does not approve a new numerical policy or close #200.

The existing pipeline resamples before postprocessing. `final_face` uses the
processed row interval `[int(.65 * N), N)` and requires five usable rows. Its
stable-height gates and quaternion rotation mean describe the processed tail,
not independent observations, rotational rest, or experimental acceptance.
FinalFace remains distinct from ReferenceFace and intended first contact.

## Reproduction and compatibility

`tests/test_final_face_resampling_contract.py` calls the actual UniformResampler,
postprocessor and reducer on a literal 200 × 120 × 80 mm identity-oriented box
with centre Y=60 mm and floor=0. Six original times `[0,.1,.2,.3,.4,.5]` give
three tail rows, so the producer stores an empty FinalFace. Factor three gives
`(6-1)*3+1=16` processed rows and six tail rows starting at row10 (1/3 s).
Only .4 and .5 s are original observations in that processed interval, yet the
current producer stores BOTTOM. A nonuniform-time control has the same row-count
and original-support distinction. Neither example adds physical information.

These are characterization assertions, not an oracle approving interpolation as
additional observation support. No solver, optimizer, measured input or source
CSV rewrite is involved.

## Options requiring a decision

1. **Original observation support (recommended for an evidence requirement).**
   Count distinct original samples in the final processed tail's closed time
   interval, requiring at least five supported usable observations; retain the
   current tail geometry/mean and numerical thresholds. This would make the
   six-to-sixteen case unavailable. Full and limited resampling must preserve
   original sample identity and time through subsetting, processing, save and
   reload. Identity must be captured before interpolation; regenerated Frame or
   forward-filled `Pose.Source=Optimized` cannot prove original observations.
   Count only originals inside the closed final-tail interval, excluding the
   interpolation parent immediately before its boundary. Missing original-support
   provenance in legacy resampled results needs
   an explicit unavailable reason; an enabled flag alone cannot establish support.
   This is a behavior/schema change requiring producer/loader/Guide alignment
   and compatibility tests before delivery. Computing on a separate original-row
   tail would define a different window and is not interchangeable with this option.
   This is a support gate, not a resampling-invariant estimate: the processed
   boundary, row-based smoothing, gradients and equal-weight rotation mean can
   still change with inserted rows, including limited resampling.
2. **Processed rows (preserve current behavior).** Keep the existing processed
   tail and minimum five usable rows. Clarify registry/Guide/contract wording that
   rows can be interpolated, are not five independent observations and do not
   establish physical settling. Ordinary and limited resampling follow their
   resulting processed time interval. Legacy results keep the current recorded
   FinalFace and geometry validation; absent fields remain unavailable. Repeat
   eligibility and observed-evidence gates remain unchanged.

Until the user selects a contract, no new resampling-OFF gate, original-support
gate, time threshold or angular-velocity threshold is introduced. Both options
retain finite geometry/floor checks, quaternion-sign invariance, ambiguous-mean
rejection and the existing fixed face tie order. Independent real validation and
consumer adoption are outside this decision.

Independent CAE review reproduced both automatic tests (2 passed), independently
reconstructed the uniform input through the actual resampler/postprocessor, and
confirmed the support/window/weighting distinction. The policy remains unapproved.

The interpretation uses NumPy's [piecewise-linear interpolation definition](https://numpy.org/doc/2.3/reference/generated/numpy.interp.html)
and SciPy's [equal-default-weight chordal rotation mean](https://docs.scipy.org/doc/scipy/reference/generated/scipy.spatial.transform.Rotation.mean.html),
together with the current producer source. The conclusion that inserted
evaluation points are not independent observations is an inference from those
definitions and the reproduced input, not a solver qualification claim.
