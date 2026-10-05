# Marker profile interpretation and compatibility — PUB05

Last Reviewed: 2026-10-06

Plan Spec: ISTA6A-PLAN-20261001-v1

The existing author `profile_version` and canonical whole-JSON SHA-256 remain
unchanged. Public example18 and32 hashes remain respectively
`66ac8c6d2bcd9b531d532a23c2af7b04e72a7ae1ab1ae8aa8c0c8ec7ef77bafb` and
`d5405f1cf434c924070033748b4ca1e4661f10e190369d8f0bb0aac75fc97ff0`.
These are public synthetic examples, not measured attachment standards.

## Identity and meaning

`src/utils/marker_profile_identity.py` binds actual shared producer/consumer
constants. New envelopes require integer schema_version1, this plan_spec and
object_type. Nonfinite JSON, missing source, stale hashes or unsupported policy
are rejected. Profile identity retains the declared source profile and full
interpretation policy for audit. No simulator truth enters this contract.

| Identity | Content and effect |
|---|---|
| profile_hash | Existing complete author JSON; includes author version/provenance and marker order |
| geometry_hash | Absolute mm dimensions, origin/dimension policy and sorted point set; excludes names/faces/order/author metadata |
| observation_mapping_hash | Sorted label-to-XYZ correspondence; catches exchanging two existing positions without moving the point set |
| semantic_hash | Sorted label/face bindings plus fixed normals, label prefixes, local/world axes/frame, corner basis, units/time, world conversion and simulation/analysis half-turn maps/operation |
| semantic_version | Declared policy version plus full semantic_hash; changes with marker meaning rather than arbitrary author revision |

The current policy is `marker-interpretation-v1`: box geometric centre, right
handed local XYZ (+Right,+Top,+Front), mm/seconds, world +Y vertical, local-to-world
rotation. Normals, half-turn matrices, local-axis rotation indices and analysis
face maps live in `src/config/marker_semantics.py`; the identity also reads the
actual config_app face/corner definitions and reader label prefixes. Half-turn
face assignment preserves observed XYZ and IDs; correction remains OFF until
explicit analysis Apply. Display-only camera/face offsets are not physical
geometry and never change these identities.

## Compatibility and limits

`MarkerProfileCompatibility` records status/reasons and previous/current author
hashes; approval remains `not_evaluated`. Matching geometry/meaning/correspondence
is compatible despite author/order-only changes. Geometry or interpretation
changes are incompatible. A correspondence-only change is `review_required`:
numerical pose change is **not inferred**. Unknown legacy, invalid/stale records
and unsupported policies remain unknown/invalid/unsupported, never approved.

Same-face label swaps preserve centroid and the current Raw face-surface
objective/rank. That solver does not fit each point to its declared profile XYZ.
Existing static-template fitting in #135 does use label-to-coordinate matching:
the independent example swap keeps the centre but raises correspondence RMSE
above its existing guard. Missing-marker/time-series correspondence may also be
affected. Preserve old results with their original declaration; request scoped
review for reuse rather than rewriting stored numbers or asserting every pose
changed. No migration or baseline/tolerance promotion is performed.

`MarkerLayoutSupport` uses the existing optimizer's complete assigned-face
six-DOF rank guard, with dimensionless relative singular-value tolerance1e-6.
One collinear face is allowed when other faces constrain the full layout.
Rank-deficient layouts can be imported/inspected but cannot Apply/generate as a
supported pose layout. A bounded check of23 other proper signed-axis rotations
at the declared centre detects explicit alternative assigned-face solutions.
An independent cube-edge fixture admits both I and Ry(+90°) despite rank6;
its status is ambiguous, Apply/generation and comparison aggregation are blocked,
and the observed-only Raw pose consumer preserves records with AmbiguousGeometry
and NaN poses/corners. A declared source that fails the current solver's local
rank guard is likewise gated before fitting (existing UnidentifiableGeometry
status), even if observation noise would raise the numerical rank. Both
unavailable and ambiguous declarations are excluded from aggregation. Six face
centres give an independent rank3 fixture for this local method limitation;
rank3 alone does not prove global nonidentifiability, and exact face centres can
constrain a unique orientation through higher-order constraints. Literal lateral
offsets of0.01mm can give observed rank6 but cannot certify support for the
declared source. This is a software boundary check, not physical tolerance.
This witness search is not exhaustive: absence of a
witness leaves global_uniqueness_status unavailable; frame coverage and other
ambiguity remain runtime limits. Geometry names do not certify measured face/contact.
Existing face-plane tolerance1e-8mm and minimum separation1mm are preserved;
these numerical/import checks are not measured accuracy tolerances.

## Editing, persistence and propagation

Copy/Edit reuses public18/32 and custom import. Preset Edit makes a custom copy.
The source snapshot is immutable. Edits invalidate Preview; Preview publishes
only valid draft geometry; Apply requires a current supported preview. Reset to
source resets the draft while retaining its custom ID, and requires renewed
Preview/Apply. Cancel leaves the parent unchanged. Save writes the source,
draft, preview, applied identities/revisions and UTC edit events atomically;
failure/retry preserves previous file and decisions. Reopen uses the saved
applied profile and offers pending draft edits through Edit. View gestures are
transient display choices, not edit history or trial approval.

New observations preserve Artifact SchemaVersion1 and add
`MarkerProfileIdentityJson`, `MarkerGeometryHash`, `MarkerSemanticsVersion` and
`MarkerSemanticsHash`. The nested `MarkerArtifactIdentity` envelope includes
the source profile and recomputable identities, resolving fixed constants by
policy version/hash instead of repeating the full policy. Raw/corrected/slice
headers and proc `Info/Artifact` columns carry this same declaration. Readers
check dimensions, units/frame/time/source class, hashes, reader face-prefix rules
and channel IDs. Step2 refuses declared unsupported/stale marker identity while
retaining prior display; legacy remains individually viewable with unknown
meaning. Compare aggregation rejects missing/invalid/incompatible identity.
Direct simulation `.proc` without a marker profile remains unknown.

Generation captures a deep source/profile snapshot. Matching worker+generation,
cancellation and current semantic identity guard callbacks; obsolete success,
failure/progress or finish cannot overwrite the current job or previous output.
Profile changes cancel in-flight work and record previous-output compatibility.
Opening an older output uses its own dimensions/profile; it cannot inherit
current profile approvals. Existing Raw SHA/source guards in #136/#137 bind
metadata bytes and retain their approval invalidation behavior.

#135's older partial `legacy-face-assignment-v3` digest remains a historical
replay contract, never promoted to complete semantics. New corpus declarations
also bind full profile identity to observed metadata; old approved fixture/baseline
assets are not rewritten. #113 registration UI/integration is excluded by the
user's decision; its name does not exclude the already delivered static #135
adapter/source lineage. #104 is separate. #139/#143 are not implemented.

## Evidence state

Human approved the final interactive mockup on2026-10-06. Production automatic
checks, final independent review and CI/publication are recorded in
[delivery](../../visualization/marker_profile_138.md). Native external input and
actual Windows OS125% remain unexecuted after capture/activation errors; Qt
process125% and widget/QTest success do not certify them. No validated measured
experimental dataset or real accuracy acceptance is claimed.
