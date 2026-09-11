"""Public scene observations and a separate, detector-independent event oracle.

Prescribed handling is kinematic, not an ISTA apparatus model. Dynamic drops
are recorded from MuJoCo; neither lane is a calibrated packaging experiment.
"""
from __future__ import annotations

import argparse
import copy
import csv
import hashlib
import json
from itertools import product
from pathlib import Path

import mujoco
import numpy as np
from scipy.spatial.transform import Rotation

from .engine.mujoco_engine import MuJoCoEngine
from .marker_fixtures import WORLD_TO_ANALYSIS, validate_profile, virtual_profile_32
from src.utils.artifact_metadata import RAW_KEY, metadata_json

VERSION = "1.0"
DT = 0.008
CASES = ("drops", "handling", "tracking", "partial")


def _steps(duration):
    count = int(round(duration / DT))
    if count < 1 or not np.isclose(count * DT, duration, atol=1e-12, rtol=0):
        raise ValueError("Stage duration must be a positive multiple of 0.008 s.")
    return count


def _ease(count):
    u = np.linspace(0.0, 1.0, count + 1)
    return 10 * u**3 - 15 * u**4 + 6 * u**5


class _Sequence:
    def __init__(self, origin):
        self.times = [0.0]
        self.origins = [np.asarray(origin, dtype=float)]
        self.rotations = [np.eye(3)]
        self.forces = [None]
        self.stages = []
        self.events = []

    def append(self, times, origins, rotations, label, source, *, forces=None, parameters=None):
        times, origins, rotations = map(np.asarray, (times, origins, rotations))
        if not np.allclose(origins[0], self.origins[-1], atol=1e-9, rtol=0):
            raise ValueError("A stage would teleport the body origin.")
        if not np.allclose(rotations[0], self.rotations[-1], atol=1e-12, rtol=0):
            raise ValueError("A stage would jump the body orientation.")
        if times[0] != 0 or not np.allclose(np.diff(times), DT, atol=1e-12, rtol=0):
            raise ValueError("Every stage must preserve the actual 0.008 s clock.")
        start_frame, start_time = len(self.times) - 1, self.times[-1]
        self.times.extend((start_time + times[1:]).tolist())
        self.origins.extend(origins[1:].copy())
        self.rotations.extend(rotations[1:].copy())
        if forces is None:
            self.forces.extend([None] * (len(times) - 1))
        else:
            self.forces[-1] = float(forces[0])
            self.forces.extend(map(float, forces[1:]))
        stage = {"label": label, "source": source, "start_frame": start_frame,
                 "end_frame": len(self.times) - 1, "start_time_s": start_time,
                 "end_time_s": self.times[-1], "parameters": parameters or {}}
        self.stages.append(stage)
        return stage

    def move(self, duration, label, origin=None, rotation=None):
        count = _steps(duration)
        target = self.origins[-1] if origin is None else np.asarray(origin, dtype=float)
        target_r = self.rotations[-1] if rotation is None else np.asarray(rotation, dtype=float)
        s = _ease(count)
        origins = self.origins[-1] + s[:, None] * (target - self.origins[-1])
        start = Rotation.from_matrix(self.rotations[-1])
        delta = (start.inv() * Rotation.from_matrix(target_r)).as_rotvec()
        rotations = (start * Rotation.from_rotvec(s[:, None] * delta)).as_matrix()
        origins[-1], rotations[-1] = target.copy(), target_r.copy()
        return self.append(np.arange(count + 1) * DT, origins, rotations, label,
                           "prescribed_kinematic", parameters={
                               "interpolation": "quintic smoothstep; zero endpoint speed/acceleration",
                               "support": "externally prescribed; contact force unavailable"})

    def tilt(self, duration, start_degrees, end_degrees):
        count = _steps(duration)
        angle = start_degrees + _ease(count) * (end_degrees - start_degrees)
        rotations = Rotation.from_euler("z", angle[:, None], degrees=True).as_matrix()
        # The complete local bottom-left edge lies on the stationary floor line.
        local_edge_point = np.array([-150.0, -90.0, 0.0])
        world_edge_point = np.array([-150.0, 0.0, 0.0])
        origins = world_edge_point - np.einsum("nij,j->ni", rotations, local_edge_point)
        return self.append(np.arange(count + 1) * DT, origins, rotations, "supported_tilt",
                           "prescribed_kinematic", parameters={
                               "start_degrees": start_degrees, "end_degrees": end_degrees,
                               "local_edge_point_mm": local_edge_point.tolist(),
                               "world_edge_point_mm": world_edge_point.tolist(),
                               "edge_direction": [0, 0, 1],
                               "note": "Prescribed support; not a Type H test or release model."})

    def drop(self, duration=1.2):
        engine = MuJoCoEngine(size=(300.0, 180.0, 90.0), mass=1.0,
                              elasticity=0.5, friction=0.7, com_offset=(0, 0, 0))
        engine.init_pos = (WORLD_TO_ANALYSIS.T @ self.origins[-1] / 1000).tolist()
        engine.init_quat = Rotation.from_matrix(
            WORLD_TO_ANALYSIS.T @ self.rotations[-1]).as_quat()[[3, 0, 1, 2]].tolist()
        engine.build()
        # A zero margin makes the explicit geometric floor and contact surface
        # coincide. Soft penetration is recorded rather than projected away.
        engine.model.geom_margin[:] = 0.0
        history = engine.record_samples(_steps(duration) + 1, substeps=4)
        times = np.array([row["time"] for row in history])
        origins = np.array([WORLD_TO_ANALYSIS @ row["BodyOrigin"] for row in history])
        rotations = np.array([WORLD_TO_ANALYSIS @ row["RotationMatrix"] for row in history])
        forces = np.array([row["ContactNormalForceN"] for row in history])
        parameters = {
            "engine": "MuJoCo", "engine_version": mujoco.__version__,
            "timestep_s": float(engine.model.opt.timestep), "substeps": 4,
            "actual_engine_time_s": times.tolist(), "gravity_m_s2": [0, 0, -9.81],
            "mass_kg": 1.0, "com_offset_mm": [0, 0, 0],
            "initial_position_m": engine.init_pos, "initial_quaternion_wxyz": engine.init_quat,
            "initial_velocity": [0.0] * 6, "final_velocity": engine.data.qvel.tolist(),
            "body_inertia_kg_m2": engine.model.body_inertia[1].tolist(),
            "contact_model": [{"name": mujoco.mj_id2name(engine.model, mujoco.mjtObj.mjOBJ_GEOM, i),
                               "margin_m": float(engine.model.geom_margin[i]),
                               "friction": engine.model.geom_friction[i].tolist(),
                               "condim": int(engine.model.geom_condim[i]),
                               "solref": engine.model.geom_solref[i].tolist(),
                               "solimp": engine.model.geom_solimp[i].tolist()}
                              for i in range(engine.model.ngeom)],
            "note": "Uncalibrated soft rigid contact. Later prescribed hold captures residual motion; solref damping is not restitution.",
        }
        stage = self.append(times, origins, rotations, "released_body", "mujoco_dynamic",
                            forces=forces, parameters=parameters)
        active = forces > 1e-8  # Numeric force-presence oracle, not detector input.
        starts = np.flatnonzero(active & ~np.r_[False, active[:-1]])
        if not len(starts) or starts[0] == 0:
            raise RuntimeError("Expected an initially airborne drop followed by engine contact.")
        first = int(starts[0])
        event = {"kind": "drop", "start_frame": stage["start_frame"], "end_frame": stage["end_frame"],
                 "start_time_s": stage["start_time_s"], "end_time_s": stage["end_time_s"],
                 "release_frame": stage["start_frame"], "release_time_s": stage["start_time_s"],
                 "release_clearance_mm": 100.0, "target_feature": "BOTTOM face",
                 "first_contact_frame": stage["start_frame"] + first,
                 "first_contact_time_s": stage["start_time_s"] + times[first],
                 "contact_onset_bracket_s": [stage["start_time_s"] + times[first - 1],
                                             stage["start_time_s"] + times[first]],
                 "contact_episode_start_frames": (stage["start_frame"] + starts).tolist(),
                 "start_censored": False, "end_censored": False,
                 "note": "One release event; bounce/recontacts do not create additional drops."}
        self.events.append(event)


def _build(case):
    seq = _Sequence([0, 400 if case == "tracking" else 90, 0])
    seq.move(0.4, "idle")
    if case == "drops":
        for x in (180.0, 360.0):
            seq.move(0.8, "supported_lift_translate", [x, 190, 0], np.eye(3))
            seq.move(0.4, "held")
            seq.drop()
            seq.move(0.4, "prescribed_idle_capture")
    elif case == "handling":
        up = seq.tilt(0.8, 0, 15)
        down = seq.tilt(0.8, 15, 0)
        seq.events.append({"kind": "supported_tilt_return", "start_time_s": up["start_time_s"],
                           "end_time_s": down["end_time_s"], "maximum_angle_deg": 15.0,
                           "expected_drop": False})
        seq.move(0.4, "idle")
        seq.move(0.8, "supported_lift_translate", [150, 400, 80])
        out = seq.move(0.8, "airborne_reorientation", rotation=Rotation.from_euler("x", 90, degrees=True).as_matrix())
        back = seq.move(0.8, "airborne_reorientation_return", rotation=np.eye(3))
        seq.events.append({"kind": "airborne_reorientation", "start_time_s": out["start_time_s"],
                           "end_time_s": back["end_time_s"], "maximum_angle_deg": 90.0,
                           "expected_drop": False})
        seq.move(0.8, "supported_lowering", [150, 90, 80])
        seq.move(0.4, "idle")
        drag = seq.move(0.8, "floor_horizontal_drag", [450, 90, 80])
        seq.events.append({"kind": "floor_horizontal_drag", "start_time_s": drag["start_time_s"],
                           "end_time_s": drag["end_time_s"], "expected_drop": False})
        seq.move(0.4, "idle")
    elif case == "tracking":
        seq.move(0.8, "supported_translate", [240, 400, 0])
        seq.move(0.4, "held")
        turn = seq.move(1.2, "genuine_smooth_rotation", rotation=Rotation.from_euler("y", 180, degrees=True).as_matrix())
        seq.events.append({"kind": "genuine_rotation", "start_time_s": turn["start_time_s"],
                           "end_time_s": turn["end_time_s"], "angle_deg": 180.0,
                           "expected_drop": False, "expected_tracking_jump": False})
        seq.move(2.0, "held")
    return seq


def make_sequence(case="drops", seed=75001, *, noise_std_mm=0.0):
    """Return observation arrays, static registration, and separate truth.

    Partial captures retain their original frame numbers and absolute times.
    Seed affects only explicitly requested Gaussian observation noise.
    """
    if case not in CASES:
        raise ValueError(f"Unknown sequence case: {case}")
    if not np.isfinite(noise_std_mm) or noise_std_mm < 0:
        raise ValueError("Noise standard deviation must be finite and nonnegative.")
    profile = virtual_profile_32()
    seq = _build("drops" if case == "partial" else case)
    times, origins, rotations = map(np.asarray, (seq.times, seq.origins, seq.rotations))
    frames = np.arange(len(times))
    local = np.array([m["xyz_mm"] for m in profile["markers"]])
    truth = np.einsum("nij,mj->nmi", rotations, local) + origins[:, None, :]
    observed = truth.copy()
    corruptions = []
    if case == "tracking":
        # Disjoint observed subsets retain the same fixed registered marker IDs.
        for start, end, visible in [(60, 100, np.arange(0, 32, 2)), (100, 140, np.arange(1, 32, 2))]:
            hidden = np.setdiff1d(np.arange(32), visible)
            observed[start:end, hidden] = np.nan
            corruptions.append({"kind": "constraint_subset", "start_frame": start, "end_frame_exclusive": end,
                                "visible_ids": [profile["markers"][i]["id"] for i in visible]})
        observed[160:170] = np.nan
        corruptions.append({"kind": "constraint_gap", "start_frame": 160, "end_frame_exclusive": 170})
        half_turn = np.diag([1.0, -1.0, -1.0])
        observed[400:450] = np.einsum("nij,mj->nmi", rotations[400:450] @ half_turn, local) + origins[400:450, None, :]
        corruptions.append({"kind": "solver_pose_half_turn_interval", "start_frame": 400,
                            "end_frame_exclusive": 450, "axis": "X", "matrix": half_turn.tolist()})
        observed[490:520] += [120, 0, -60]
        corruptions.append({"kind": "solver_translation_jump_interval", "start_frame": 490,
                            "end_frame_exclusive": 520, "offset_mm": [120, 0, -60]})
    if noise_std_mm:
        observed += np.random.default_rng(seed).normal(0.0, noise_std_mm, observed.shape)
        corruptions.append({"kind": "independent_constraint_noise", "std_mm": float(noise_std_mm),
                            "note": "Synthetic stress only; not calibrated camera noise."})
    manifest = {"schema_version": 1, "generator_version": VERSION, "case": case, "seed": seed,
                "source_kind": "mujoco_synthetic" if case in ("drops", "partial") else "handcrafted_dummy",
                "evidence_level": "synthetic_integration", "sample_interval_s": DT,
                "coordinate_policy": "world-y-up; fixed box-local XYZ; geometric-center origin; mm/s",
                "generation_assumptions": "Prescribed support/motion and real MuJoCo releases are separate stages. No physical apparatus, packaging deformation, or ISTA conformity is claimed.",
                "stages": seq.stages, "events": seq.events, "corruptions": corruptions,
                "contact_force_n": seq.forces, "layout_hash": validate_profile(profile),
                "truth_policy": "Captured before observation corruption. Detector consumes only observed.csv and registration.json."}
    if case == "partial":
        # First release is outside the recording; final contact has not occurred.
        first, stop = 208, 563
        selection = slice(first, stop)
        times, origins, rotations, frames, truth, observed = [a[selection].copy() for a in
                                                            (times, origins, rotations, frames, truth, observed)]
        manifest["contact_force_n"] = manifest["contact_force_n"][selection]
        manifest["capture_source_frame_range"] = [first, stop - 1]
        manifest["stages"] = [s for s in manifest["stages"] if s["end_frame"] >= first and s["start_frame"] < stop]
        for event in manifest["events"]:
            event["start_censored"] = event["release_frame"] < first
            event["end_censored"] = event["first_contact_frame"] >= stop
            event["observed_start_frame"] = max(first, event["start_frame"])
            event["observed_end_frame"] = min(stop - 1, event["end_frame"])
    registration = {"version": 1, "profile": profile, "floor_y_mm": 0.0,
                    "position_tolerance_mm": 1.0, "com_offset_mm": [0, 0, 0]}
    return {"time_s": times, "frame": frames, "origin_mm": origins, "com_mm": origins.copy(),
            "rotation_matrix": rotations, "truth_markers_mm": truth, "observed_markers_mm": observed,
            "registration": registration, "manifest": manifest}


def write_sequence(outputdir, case="drops", seed=75001, *, noise_std_mm=0.0):
    """Write neutral input names in outputdir; truth is never input metadata."""
    data = make_sequence(case, seed, noise_std_mm=noise_std_mm)
    root = Path(outputdir)
    root.mkdir(parents=True, exist_ok=True)
    profile = data["registration"]["profile"]
    artifact = {"SourceKind": data["manifest"]["source_kind"], "ModelId": "public-virtual-box-300x180x90-mm",
                **dict(zip(("BoxLengthMm", "BoxWidthMm", "BoxHeightMm"), profile["box_dims_mm"])),
                "MarkerLayoutId": profile["profile_id"], "MarkerLayoutHash": validate_profile(profile),
                "CoordinatePolicy": "world-y-up-box-local-fixed-center-v1",
                "UnitsPolicy": "bma-mm-s-rotvec-rad-summary-deg-v1", "GeneratorVersion": VERSION}
    with (root / "observed.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Format Version", "1.25", "Length Units", "Millimeters", "Coordinate Space", "Global",
                         "Source Kind", artifact["SourceKind"], RAW_KEY, metadata_json(artifact)])
        writer.writerow([])
        header = {key: ["", ""] for key in ("type", "name", "id", "parent", "category", "component")}
        header["component"] = ["Frame", "Time"]
        for marker in profile["markers"]:
            for key, value in (("type", "Rigid Body Marker"), ("name", "Object:" + marker["id"]),
                               ("id", marker["id"]), ("parent", "Object"), ("category", "Position")):
                header[key].extend([value] * 3)
            header["component"].extend(["X", "Y", "Z"])
        writer.writerows(header.values())
        for frame, time, points in zip(data["frame"], data["time_s"], data["observed_markers_mm"]):
            writer.writerow([frame, time, *[float(x) if np.isfinite(x) else "" for x in points.ravel()]])
    (root / "registration.json").write_text(json.dumps(data["registration"], indent=2, allow_nan=False), encoding="utf-8")
    q = Rotation.from_matrix(data["rotation_matrix"]).as_quat()[:, [3, 0, 1, 2]]
    for i in range(1, len(q)):
        if q[i] @ q[i - 1] < 0:
            q[i] *= -1
    corners = np.asarray(list(product((-1, 1), repeat=3))) * np.asarray(profile["box_dims_mm"]) / 2
    heights = (np.einsum("nij,mj->nmi", data["rotation_matrix"], corners) + data["origin_mm"][:, None, :])[:, :, 1].min(axis=1)
    with (root / "truth_pose.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["frame", "time_s", *[f"body_{a}_mm" for a in "xyz"], *[f"com_{a}_mm" for a in "xyz"],
                         *[f"q_{a}" for a in "wxyz"], *[f"r{i}{j}" for i in range(3) for j in range(3)],
                         "min_corner_y_mm", "contact_force_n"])
        for i, time in enumerate(data["time_s"]):
            writer.writerow([data["frame"][i], time, *data["origin_mm"][i], *data["com_mm"][i],
                             *q[i], *data["rotation_matrix"][i].ravel(), heights[i], data["manifest"]["contact_force_n"][i]])
    manifest = copy.deepcopy(data["manifest"])
    manifest["files"] = {name: hashlib.sha256((root / name).read_bytes()).hexdigest()
                         for name in ("observed.csv", "registration.json", "truth_pose.csv")}
    manifest["generator_source_sha256"] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    manifest["engine_source_sha256"] = hashlib.sha256((Path(__file__).parent / "engine" / "mujoco_engine.py").read_bytes()).hexdigest()
    (root / "truth_events.json").write_text(json.dumps(manifest, indent=2, allow_nan=False), encoding="utf-8")
    return root


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default="tmp/scene_recording")
    parser.add_argument("--case", choices=CASES, default="drops")
    parser.add_argument("--seed", type=int, default=75001)
    parser.add_argument("--noise-std-mm", type=float, default=0.0)
    args = parser.parse_args()
    print(write_sequence(args.output, args.case, args.seed, noise_std_mm=args.noise_std_mm))


if __name__ == "__main__":
    main()
