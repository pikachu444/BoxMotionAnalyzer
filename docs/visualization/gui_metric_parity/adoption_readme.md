# Same-source adoption

Last Reviewed: 2026-11-12

Use `adoption_manifest.json` to select the fixed public source commit and verify every listed file's SHA-256. `sha256` covers committed Git blob bytes; `validated_checkout_sha256` records the tested Windows checkout bytes. Account explicitly for Git newline conversion when comparing another checkout. The listed revision identifies the implementation; later evidence-only commits need not change that source. No separate GUI package is invented by this delivery.

1. Check out the fixed public commit in an isolated checkout. Install the existing `requirements.txt` dependencies; the manifest records the versions actually used in public verification.
2. Keep the listed `src/analysis`, `src/config` and `src/utils` files together. Keep the existing `bma_shared_core` connection and its ROW/FRAME/TIME-KERNEL contracts. Prefer importing the same public source. If a transitional copy is necessary, compare its bytes with the manifest and assign an owner to source drift.
3. Retain the existing `PipelineController`, `ComparisonModel`, loader and serializer bindings. Processing requests and successfully saved result paths keep their existing signals. `metric_context_changed` transfers typed owner results for presentation; diagnostics strings do not decide eligibility.
4. Keep Single/Raw/resampling-OFF/overwrite-OFF defaults. Use the same persistent settings binding and default language initialization. Do not infer approval from a filename, synthetic input, baseline, small spread or successful import.
5. Reopen representative existing `.slice` and three-level `.proc` files. New postprocessing adds `FinalFace`; missing legacy fields remain unavailable. Snapshot/target/path display adapters do not add target records or thirty new CSV fields. Point CSV keeps all original row columns and precision.
6. Run the manifest verification commands. Reproduce the original-size Guide figures with `scripts/generate_metric_guide_diagrams.py`; reproduce product widget evidence with `scripts/gui_metric_parity_product_check.py`. Qt/QTest and VTK renders are separate from external native input, actual OS125 and human acceptance.
7. The consumer owner then checks private bindings, real representative captures, existing saves and CAE results, operator workflow and rollback. Those private checks were not performed in this public repository and are not replaced by source hashes or public analytic fixtures.

The geometric-centre saved snapshot and registered inertial-COM quadratic fit stay separate. Their time, estimator, reference point and gravity constants differ. Detector onset, accepted persistent contact, ReferenceFace, FinalFace and net contact-path sweep also remain separate quantities.

CAE export keeps the seven-line legacy grammar, runtime encoding and newline policy. Manual heights default to declared rest initial conditions; the explicit selected-time option produces mixed initial conditions. Measured paths require all six finite analysis-frame components. Names containing delimiters, quotes, CR, LF or NUL are rejected before a destination change. A complete same-directory temporary file is replaced atomically.

Rollback by restoring the previous public source commit and bindings together, or reverting the integration merge. Retain original input/output files and prior settings for comparison. This change does not rewrite loaded CSV files or upgrade legacy evidence into approved measurements.

Repository and dependency license information is recorded in the manifest. No paid service or new external provider is introduced.

The approved small real Raw hop uses11 actual fits per generated input; the successful run records22 calls and saved result errors. See `validation_report.md`, `pipeline_fixture_manifest.json` and `pipeline_hop_receipt.json`. A generated integration run does not replace consumer experimental/CAE regression.
