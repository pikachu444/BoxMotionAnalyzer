"""Public handcrafted fixture. No capture-derived geometry or production oracle."""
import csv
import json
import numpy as np
import pandas as pd
from scipy.spatial.transform import Rotation as R
from src.config.data_columns import TimeCols

DIMS = (200., 120., 80.)
LAYOUT = {
    "F1": (21, 12, 40), "F2": (-51, 19, 40), "F3": (30, -35, 40), "F4": (-9, -8, 40),
    "B1": (17, -31, -40), "B2": (-39, 23, -40), "B3": (42, 28, -40),
    "R1": (100, 12, 8), "R2": (100, -28, 19), "R3": (100, 31, -18),
    "L1": (-100, -18, 7), "L2": (-100, 25, 21), "L3": (-100, 19, -25),
    "T1": (7, 60, -9), "T2": (-45, 60, 23), "T3": (51, 60, 18),
    "M1": (-12, -60, 25), "M2": (38, -60, -18),
}
ORACLE = {"X": np.diag([1., -1., -1.]), "Y": np.diag([-1., 1., -1.]), "Z": np.diag([-1., -1., 1.])}
BASE_FACES = {name: {"F": "FRONT", "B": "BACK", "L": "LEFT", "R": "RIGHT", "T": "TOP", "M": "BOTTOM"}[name[0]] for name in LAYOUT}


def raw_bundle(axis="X", boundary=30, samples=80):
    header = {k: ["", ""] for k in ("type", "name", "id", "parent", "category", "component")}
    header["component"] = [TimeCols.FRAME, TimeCols.TIME]
    metadata = ["Format Version", "1.25", "Length Units", "Millimeters", "Coordinate Space", "Global"]
    header["export_metadata"] = dict(zip(metadata[::2], metadata[1::2]))
    header["source_rows"] = [metadata, []]
    for name in LAYOUT:
        for key, value in (("type", "Rigid Body Marker"), ("name", f"Example:{name}"),
                           ("id", name), ("parent", "Example"), ("category", "Position")):
            header[key].extend([value] * 3)
        header["component"].extend(["X", "Y", "Z"])
    rotation = R.from_euler("xyz", [15, 20, 10], degrees=True).as_matrix()
    rows = []
    truth = []
    for i in range(samples):
        origin = np.array([i * .2, 200., 10.])
        pose = rotation if axis is None or i < boundary else rotation @ ORACLE[axis]
        rows.append([i, i * .01, *(np.array(list(LAYOUT.values())) @ pose.T + origin).ravel()])
        truth.append([*origin, *R.from_matrix(rotation).as_rotvec()])
    return header, pd.DataFrame(rows, columns=header["component"]), np.asarray(truth)


def write_raw(path, header, raw):
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerows(header["source_rows"])
        for key in ("type", "name", "id", "parent", "category", "component"):
            writer.writerow(header[key])
        writer.writerows(raw.fillna("").values)


def context_json(source_hash=""):
    return json.dumps({"box_dims_mm": DIMS, "base_faces": BASE_FACES,
        "coordinate_policy": "global-y-up-box-xyz-mm", "source_sha256": source_hash,
        "export_metadata": {"Length Units": "Millimeters", "Coordinate Space": "Global"}}, sort_keys=True)
