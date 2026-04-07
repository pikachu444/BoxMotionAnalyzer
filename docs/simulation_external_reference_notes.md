# Simulation External Reference Notes

This note records the external sources used to verify the current simulation
implementation and the exact local paths where the derived rules are applied.

## Local Paths

- Source rules:
  - `/root/BoxMotionAnalyzer/src/simulation/scenarios.py`
- User-facing simulation guide:
  - `/root/BoxMotionAnalyzer/docs/simulation.md`
- Type G / Type H face-numbering and sequence reference:
  - `/root/BoxMotionAnalyzer/docs/ISTA_6_AMAZON_SIOC_REFERENCE.md`
- This traceability note:
  - `/root/BoxMotionAnalyzer/docs/simulation_external_reference_notes.md`

## Sources

- ANSI storefront entry for the official standard:
  - https://webstore.ansi.org/standards/ansi/istaprojectamazonsioc2018
- Publicly accessible excerpt used for implementation cross-checks:
  - https://d39w7f4ix9f5s9.cloudfront.net/32/98/c52dd6b841f18bcb8af679b1f1ac/9.TESTING_thumbnail_ISTA%20Project%206-Amazon.com-SIOC%2018-18.pdf

## What Was Checked Against These Sources

- Type G face numbering
- Type G 17-drop sequence order
- Type G standard/high drop-height rules
- Type G face / edge / corner orientation interpretation
- Type H public caution notes for tip angle and rotational drop handling

## Type G Rules Confirmed From Public Excerpts

- Face numbering for TV/Monitor Type G:
  - Face 1 = Rear
  - Face 2 = Bottom
  - Face 3 = Screen
  - Face 4 = Top
  - Face 5 = Right
  - Face 6 = Left
- Free-fall drop heights:
  - less than 32 kg: 460 mm standard, 910 mm high
  - 32 kg to 68 kg: 300 mm standard, 610 mm high
- Type G sequence includes:
  - first sequence: Edge 3-4, Edge 3-6, Edge 4-6, Corner 3-4-6, Corner 2-3-5, Edge 2-3, Edge 1-2, Face 3 (high), Face 3
  - second sequence: Edge 3-4, Edge 3-6, Edge 1-5, Corner 3-4-6, Corner 1-2-6, Corner 1-4-5, most critical flat orientation (default Face 6 when unknown), hazard impact orientation

## Type G Angle Interpretation

- The standard defines Type G orientation by contact condition, not by explicit Euler angles.
- Therefore the implementation should derive tilt from the package geometry:
  - Face = face-center vector
  - Edge = edge-center vector
  - Corner = corner vector
- With Box Motion Analyzer local axes:
  - X = Width
  - Y = Height
  - Z = Depth

Example target vectors:

- Edge 3-4 -> (0, +H, +D)
- Edge 3-6 -> (-W, 0, +D)
- Corner 3-4-6 -> (-W, +H, +D)

## Type H Caution

- Public excerpts indicate:
  - Tip/Tip Over uses a 22 degree tip angle
  - Rotational Flat/Edge/Corner drops use 230 mm
- The current repository still treats Type H as simplified logic and needs a separate follow-up against the full protocol.
