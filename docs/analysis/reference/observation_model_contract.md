# Virtual observation model (PUB10)

Last Reviewed: 2026-10-10

## Scope and use

Issue #143 adds optional camera/assigned-face visibility, common-cause group
occlusions and stationary timestamp-correlated noise after the existing physical
trajectory. `virtual-box-observation-v1` is an uncalibrated cuboid stress model.
It does not reproduce optics, an OptiTrack camera, or the Motive rigid-body solver.
Existing Gaussian, missing, freeze, reconnect jump, physical label routing and
cumulative solved local X/Y/Z half turns remain available. With the new profile
absent, their observation arrays and legacy RNG draws are unchanged.

The API is `observation_profile(marker_profile, camera=..., groups=...,
occlusions=..., noise=..., adapter=...)`. A sealed `VirtualObservationProfile`
has schema1 and the existing Plan Spec. Its hash binds the exact declared marker
profile. Unsupported versions/keys, stale hashes, boolean/text numeric values,
nonfinite parameters and malformed nested payloads are rejected.

Create a profile from the selected settings' marker profile, then select/export:

```python
import json
from pathlib import Path
from src.simulation.mode_profiles import read_profiles
from src.simulation.observation_profile import observation_profile, orthographic_camera

state = read_profiles('settings.json')
marker = state.configs[state.mode]['observation_profile']['marker']['profile']
profile = observation_profile(marker, profile_id='front-camera',
    camera=orthographic_camera([0., 1000., 5000.],
        [[-1., 0., 0.], [0., 1., 0.], [0., 0., -1.]]),
    adapter='physical_only')
Path('observation.json').write_text(json.dumps(profile, allow_nan=False), encoding='utf-8')
```

```powershell
python -m src.simulation.observation_cli --settings settings.json --profile observation.json --output new-capture --save-settings selected-settings.json
```

`--save-settings` is optional. Output must be a new directory. Settings writes
are atomic. The exporter uses the captured mode, initial seed/contact profile
and actual MuJoCo history; continuous robot state/clock/release is unchanged.
The saved settings can also use existing Open settings → Save settings → Use in
Simulation → Marker CSV → Open in Step1 controls. There is no new GUI editor or
default selection. Changing the marker profile requires a matching observation
profile; a stale binding blocks execution instead of discarding the setting.

## Frames, camera and geometry

Engine coordinates are Z-up meters. Existing output transforms them to Y-up mm
with `A=[[1,0,0],[0,0,1],[0,-1,0]]`; `p_out=1000 A p_engine` and
`R_out=A R_engine`. Local marker coordinates and outward face normals remain
box-local XYZ, fixed geometric centre. This is not rotation conjugation.
Camera position is output-world mm. A proper `camera_to_world` rotation Q has
camera +Z forward and +X/+Y image axes. For a world marker p, camera coordinates
are `(p-C) @ Q` in row notation. Camera, box and profile rotations are validated;
invalid rotations are not normalized into a supported pose.

The one supported camera is static finite orthographic projection. A marker
must lie inclusively within `abs(qx/qy)<=half_extent_mm`,
`near_mm<=qz<=far_mm` and its declared face must satisfy
`dot(R_out*n_face,-Q[:,2]) > grazing_cos + 1e-12`.
Half extents are positive, `0<=near<far` and `0<=grazing_cos<1`.
The fixed dimensionless 1e-12 band excludes tangency/representation residue;
it is an arithmetic boundary policy, not measured optical tolerance. Very near
cosine1 it conservatively excludes even aligned normals. View boundaries retain
inclusive comparisons without this facing guard.

Normals come from declared face semantics and validated local geometry, never
marker ID spelling. A convex box's back-facing surface is self-occluded under
this orthographic assigned-face model. An edge/corner marker belongs exclusively
to its declared face; adjacent faces do not rescue a grazing marker. Marker
coordinates must satisfy the existing box-face geometry checks. Unsupported
unknown geometry/faces are not invented. Perspective, moving cameras, lens and
pixel effects, gripper/environment ray tracing, reflective behavior and a
multi-camera optical solver are outside this version.

Independent literal expectations include Q=I at negative Z seeing BACK;
camera Ry(+90°) at negative X seeing LEFT; a box Ry(+90°) and camera on positive X
seeing FRONT. A moved box origin(10,20,30), local front(0,0,1), Ry(+90°) yields
world(11,20,30); camera(15,20,30), Ry(-90°) yields camera(0,0,4).
Z-up history Rz(+90°), origin(10,20,30)mm, local(1,2,3)mm yields output(8,33,-21)mm.
Actual engine Rx90→output identity leaves a tiny TOP tangent residue; the
independently reproduced false visibility is rejected by the fixed guard.

## Common masks and noise

`groups` declare unique group IDs and explicit distinct stable marker IDs.
Each `occlusions` entry references a group and an actual-time `[start_s,end_s)`
window. Different groups/overlaps combine by union; every selected member shares
that group's cause. Evidence records group members, original sample positions
and actual selected times. Empty selected windows or windows outside the recorded
clock are rejected. An exclusive boundary beyond the final sample is permitted
only within one final actual Δt; it never represents a fabricated sample.

Noise entries declare unique `noise_id`, channel, stable marker IDs, time window,
`std_mm` and `tau_s`. Coordinates are independent additive output-world XYZ mm
around each channel's noiseless marker position, not rigid-pose error. Solved
coordinate noise can intentionally stress the rigid constraint fit. No general
covariance schema is supported. `std_mm>=0` is stationary per-coordinate standard
deviation and `tau_s>0` is the exponential correlation time in seconds.

The exact sampled OU recurrence is:

```
x0 = std_mm * z0
a = exp(-actual_delta_t / tau_s)
xk = a*x_previous + std_mm*sqrt(-expm1(-2*actual_delta_t/tau_s))*zk
```

Each z is independent standard Gaussian. Initialization is stationary, with no
zero start/burn-in/normalization. Latent state evolves across missing, freeze and
reconnect, and resets only at an independent noise entry's first actual sample.
Disjoint windows use distinct noise IDs. Overlapping noise entries add.
Irregular intervals use actual timestamps without resampling. This is stationary
noise, not accumulated position drift. sigma2, tau1, Δt ln2/ln4 and literal
innovations1,-1,.5 yield `[2,1-sqrt(3),(1-sqrt(3)+sqrt(15))/4]`.

New streams use PCG64 with `SeedSequence(seed,spawn_key=(143,channel_index,
sha256(noise_id) as little-endian uint32 words))`. Old `SeedSequence(seed).spawn(2)`
streams/draw shapes are unchanged. Marker draws follow declared profile order;
membership-list order does not change stream order. Reordering the marker profile
is a new input identity, without a marker-order invariance promise. Reproducibility
is for identical input/settings/seed/runtime dependencies; reports capture versions.

Order: true geometry/camera/group masks → cumulative solved half turns → legacy
stable-ID Gaussian/world offsets → OU → freeze previous final pre-label observation
→ union missing masks → physical output label routing. Masks are also present
before freeze, so a previously missing observation cannot be resurrected. Noise
cannot make missing coordinates finite. Physical IDs remain distinct from routed
output labels. Visibility always uses the true current physical pose, including
when the solved channel has an artificial half turn.

## Channels and production boundary

`physical_only` is the default: camera/groups mask Marker physical positions;
these visibility masks leave production-consumed Rigid Body Marker constraints
unchanged. A visibility-only case with this adapter is reference-only and cannot
establish tracking-failure recovery. Explicit solved-channel OU still changes
the analysis input independently of this mask adapter.
Explicit `visibility-mask-to-solved-v1` copies only the new masks to the solved
channel. It is a virtual observed-input adapter, not a Motive response model.
Legacy physical-only missing/routing do not implicitly propagate. OU explicitly
names each channel independently.

Observed Raw → DataLoader/Parser → observed-only review → explicit operator
approval (default OFF) → corrected source/slice → PipelineController → PROC →
reopen uses existing production APIs. Declared insufficient/ambiguous geometry
retains explicit unavailable/ambiguous pose sources and NaN poses. Raw missing
coordinates are blank cells; JSON NaN/Infinity and infinite coordinates are errors.

Evaluation-only manifest contains camera/noise definitions, masks and fault
labels. Public `ObservationMetadataJson` carries opaque model/profile/settings
hashes, seed, adapter, uncalibrated status and original time/frame record hashes;
it contains no camera solution, mask, fault window or expected correction. Public
SimulationMetadata additionally binds the captured configuration projection.
Raw/full clocks and slice/result retained record pairs are checked. Constant
identity, atomic result save/reopen and Compare compatibility reject corruption
instead of weakening existing source checks. Absent optional metadata preserves
legacy support. A sealed source declaration establishes integrity, not authenticity
against an actor who can replace an entire source and all of its hashes.
The PUB10 generator requires its declaration even when both optional declaration
columns are removed from PROC. Declared empty Raw/Parser inputs are corruption;
complete captures require exact first/last times, while subsets retain original
time/frame pairs. Shared simulation/observation profile fields must agree.

The current PROC format repeats the opaque original-record hash list in every
row. The independently measured two-release robot file is143,762,357bytes for1295
rows and reopened in1.73s on the recorded local environment. This is a known
storage overhead; long-capture scaling and memory were not benchmarked. A later
storage representation change needs version/compatibility verification. This
work does not claim a validated long-capture performance envelope.

## Fixed execution and limits

`python -m src.simulation.observation_validation --output <new-directory>` freezes
16 cases and5 required endpoints before execution. Cases cover OFF, physical-only
reference, recoverable camera, face loss, one/multiple flips, all gaps, all-pose
loss, one-face rank, irregular OU, combined faults, PUB09 seed/profile, genuine
spin, ambiguity, declared rank and continuous robot sequence. The source/motion
groups, seed74082, windows, expected statuses and proposed numerical diagnostics
are in `protocol.json`; partial execution cannot pass.

Eight fresh physics runs include separate observation OFF/ON comparisons for
single_drop, seeded drop and robot sequence. Sixteen fresh observation variants
reuse those motions; eighteen fresh production runs include changed-label and
deleted-sidecar controls. These are not16 independent physics trials or a
fit/holdout split. RunReport separates attempts, completed runs, failures, reused
physics, unexecuted cases, required/evaluable/pass/unavailable/ambiguous counts,
code/dirty/source hashes, UTC/KST, environment and commands. Unmeasured memory and
whole optimizer counts are unavailable with reasons. Source edits during execution
or required functional/data failures return nonzero.

Position0.1mm/rotation0.1deg and finite-sample OU diagnostics are proposed,
needs_review, with effective sample count reported; they do not approve ranges,
baselines, measured accuracy or camera/noise calibration. Composite freeze/jump
poses need not match physical truth and are not claimed corrected. PUB09's
production-observed holdout remains4required/0evaluable/4not_detected in its own
unchanged evaluation. #104 requires measured references and independent labels.
Local failures, fixes, independent reviews and final-source hosted CI are recorded
separately in `observation_model_evidence_v1.json` and the linked issue/PR.
